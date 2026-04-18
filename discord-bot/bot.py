# discord-bot/bot.py — v3.0

import asyncio
import json
import os
import time
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from ui_helpers import (
    make_thinking_embed,
    make_response_embed,
    make_tool_log_embed,
    make_error_embed,
    make_kilo_embed,
    COLORS,
    ResponseView,
    AgentSelectView,
    KiloControlView,
)
from project_manager import ProjectManager
from kilo_bridge import KiloBridge

# ─── Config ───────────────────────────────────────────────────────
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:4001")

# ערוצים עם טיפול מיוחד (לא נשלחים ל-agentic loop הרגיל)
SPECIAL_CHANNELS = {"ai-admin", "kilo-code"}

# מילות מפתח בשם ערוץ → agent
CHANNEL_AGENTS = {
    "code": "coder",
    "coding": "coder",
    "backend": "coder",
    "frontend": "coder",
    "research": "researcher",
    "knowledge": "researcher",
    "analyze": "analyzer",
    "analysis": "analyzer",
}

# ─── Setup ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.dm_messages = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
pm = ProjectManager()
kb = KiloBridge()


# ─── Helpers ──────────────────────────────────────────────────────


async def call_gateway(endpoint: str, payload: dict) -> dict:
    """POST to gateway and return JSON response."""
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{GATEWAY_URL}{endpoint}",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            raise Exception(f"Gateway {resp.status}: {text[:300]}")


def get_agent_for_channel(channel) -> str:
    """Determines which agent to use based on channel name."""
    name = getattr(channel, "name", "").lower()
    for keyword, agent in CHANNEL_AGENTS.items():
        if keyword in name:
            return agent
    return "main"


def get_project_for_channel(channel) -> Optional[str]:
    """Returns project name from category, or None."""
    if hasattr(channel, "category") and channel.category:
        cat = channel.category.name.lower()
        if cat not in ("tools", "general", "text channels", "voice channels"):
            return channel.category.name
    return None


# ─── Core: agentic message processing ─────────────────────────────


async def process_message(message: discord.Message, override_agent: str = None):
    """
    Full agentic pipeline:
    1. Show animated thinking embed
    2. Call gateway agentic loop
    3. Render response + tool log
    """
    channel = message.channel
    uid = str(message.author.id)
    cid = str(channel.id)
    agent = override_agent or get_agent_for_channel(channel)
    project = get_project_for_channel(channel)

    # 1. Show thinking embed
    status_msg = await channel.send(embed=make_thinking_embed(agent))

    # 2. Animated progress bar while waiting
    stop_evt = asyncio.Event()
    frame_idx = [0]

    async def animate():
        import ui_helpers

        while not stop_evt.is_set():
            await asyncio.sleep(2.5)
            if stop_evt.is_set():
                break
            frame_idx[0] = (frame_idx[0] + 1) % len(ui_helpers.FRAMES)
            try:
                await status_msg.edit(
                    embed=make_thinking_embed(agent, ui_helpers.FRAMES[frame_idx[0]])
                )
            except Exception:
                break

    anim_task = asyncio.create_task(animate())

    # 3. Call gateway
    t0 = time.time()
    result = None
    error = None
    try:
        result = await call_gateway(
            "/chat",
            {
                "user_id": uid,
                "message": message.content,
                "agent": agent,
                "task_type": "code" if agent == "coder" else "default",
                "channel_id": cid,
                "username": message.author.display_name,
                "project": project,
            },
        )
    except Exception as e:
        error = str(e)
    finally:
        stop_evt.set()
        anim_task.cancel()

    # 4. Render result
    if error:
        await status_msg.edit(embed=make_error_embed(error))
        return

    response = result.get("response", "")
    model = result.get("model", "?")
    iterations = result.get("iterations", 1)
    tool_log = result.get("tool_log", [])
    elapsed = round(time.time() - t0, 2)

    resp_embed = make_response_embed(
        response, agent, model, elapsed, iterations, project
    )
    view = ResponseView(
        original_message=message.content,
        agent=agent,
        channel_id=cid,
        user_id=uid,
    )
    await status_msg.edit(embed=resp_embed, view=view)

    if tool_log:
        await channel.send(embed=make_tool_log_embed(tool_log))


# ─── on_message ───────────────────────────────────────────────────


@bot.event
async def on_message(message: discord.Message):
    # Ignore bots
    if message.author.bot:
        return

    # Let commands through
    if message.content.startswith("/") or message.content.startswith("!"):
        await bot.process_commands(message)
        return

    channel_name = getattr(message.channel, "name", "dm")

    # DM
    if isinstance(message.channel, discord.DMChannel):
        await process_message(message)
        return

    # Special channels
    if channel_name == "kilo-code":
        await _handle_kilo(message)
        return

    if channel_name == "ai-admin":
        await _handle_admin(message)
        return

    if channel_name == "terminal":
        await _handle_terminal(message)
        return

    # All other channels → full agentic loop
    await process_message(message)


# ─── Special channel handlers ─────────────────────────────────────


async def _handle_kilo(message: discord.Message):
    """Sends message to Kilo CLI and streams output back."""
    task = message.content.strip()
    if not task:
        return
    channel = message.channel
    status = await channel.send(embed=make_kilo_embed("🔄 מפעיל Kilo CLI...", task))
    last_text = [""]

    async def on_event(event_type: str, data: str):
        try:
            if event_type == "text":
                last_text[0] = data
                preview = data[-600:] if len(data) > 600 else data
                e = make_kilo_embed(f"⚙️ **מעבד...**\n```\n{preview}\n```", task)
                await status.edit(embed=e)
            elif event_type == "done":
                summary = data[-1500:] if len(data) > 1500 else data
                e = make_kilo_embed(f"✅ **הושלם**\n```\n{summary}\n```", task)
                await status.edit(embed=e, view=KiloControlView())
            elif event_type == "error":
                await status.edit(embed=make_error_embed(data))
        except discord.HTTPException:
            pass

    asyncio.create_task(kb.run_task(task, callback=on_event))


async def _handle_terminal(message: discord.Message):
    """Direct bash execution in #terminal channel."""
    cmd = message.content.strip()
    if not cmd:
        return
    wait = await message.channel.send(f"```\n$ {cmd[:100]}\n⏳ מריץ...\n```")
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = (out.decode(errors="replace") + err.decode(errors="replace")).strip()
        await wait.edit(content=f"```\n$ {cmd[:100]}\n{output[:1800]}\n```")
    except asyncio.TimeoutError:
        proc.kill()
        await wait.edit(content=f"```\n$ {cmd[:100]}\n[TIMEOUT after 30s]\n```")


async def _handle_admin(message: discord.Message):
    """Admin commands + regular agentic chat."""
    text = message.content.strip()
    uid = str(message.author.id)

    if text.startswith("!reset"):
        async with aiohttp.ClientSession() as s:
            await s.delete(f"{GATEWAY_URL}/memory/{uid}")
        await message.channel.send(
            f"✅ Context נמחק עבור {message.author.display_name}"
        )
    elif text.startswith("!stats"):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{GATEWAY_URL}/memory/{uid}") as resp:
                data = await resp.json()
        await message.channel.send(
            f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:1500]}\n```"
        )
    elif text.startswith("!health"):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{GATEWAY_URL}/health") as resp:
                data = await resp.json()
        await message.channel.send(f"```json\n{json.dumps(data, indent=2)}\n```")
    else:
        await process_message(message)


# ─── Slash Commands ────────────────────────────────────────────────


@tree.command(
    name="main", description="שיחה כללית עם OpenClaw", guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(prompt="מה לשאול")
async def cmd_main(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, prompt, "main")


@tree.command(
    name="coder",
    description="קוד — כתיבה, דיבוג, הסבר",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(prompt="משימת קוד")
async def cmd_coder(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, prompt, "coder", "code")


@tree.command(
    name="research", description="חקר עמו��", guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(prompt="מה לחקור")
async def cmd_research(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, prompt, "researcher")


@tree.command(
    name="analyze", description="ניתוח אסטרטגי", guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(prompt="מה לנתח")
async def cmd_analyze(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, prompt, "analyzer", "analysis")


@tree.command(
    name="orchestrate",
    description="מרובת-סוכנים: auto-select → parallel → critic → synthesis",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(task="המשימה")
async def cmd_orchestrate(interaction: discord.Interaction, task: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await call_gateway(
            "/orchestrate",
            {
                "user_id": str(interaction.user.id),
                "task": task,
                "channel_id": str(interaction.channel_id),
            },
        )
        embed = make_response_embed(
            result["synthesis"],
            "orchestrator",
            result.get("synthesis_model", "?"),
            result.get("duration", 0),
            1,
            get_project_for_channel(interaction.channel),
        )
        embed.add_field(
            name="סוכנים ששימשו",
            value=", ".join(result.get("agents_used", [])),
            inline=True,
        )
        await interaction.followup.send(embed=embed)

        for agent_id, data in result.get("agent_responses", {}).items():
            sub_embed = make_response_embed(data["response"], agent_id, "?", 0, 1, None)
            await _send_persona(interaction.channel, agent_id, sub_embed)

    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(
    name="debate", description="דיון: בעד vs נגד", guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(topic="נושא הדיון")
async def cmd_debate(interaction: discord.Interaction, topic: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await call_gateway(
            "/debate",
            {
                "user_id": str(interaction.user.id),
                "task": topic,
            },
        )
        embed = discord.Embed(title=f"⚖️ דיון: {topic[:60]}", color=COLORS["critic"])
        embed.add_field(
            name="✅ בעד", value=result["pro"]["response"][:500], inline=False
        )
        embed.add_field(
            name="❌ נגד", value=result["con"]["response"][:500], inline=False
        )
        embed.add_field(
            name="⚖️ פסיקה", value=result["verdict"]["response"][:500], inline=False
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(
    name="swarm",
    description="4 סוכנים מקביל + Critic + synthesis",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(task="המשימה")
async def cmd_swarm(interaction: discord.Interaction, task: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await call_gateway(
            "/swarm",
            {
                "user_id": str(interaction.user.id),
                "task": task,
            },
        )
        embed = make_response_embed(
            result["synthesis"],
            "orchestrator",
            "?",
            result.get("duration", 0),
            1,
            None,
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(
    name="kilo", description="הרץ משימה ב-Kilo CLI", guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(task="המשימה")
async def cmd_kilo(interaction: discord.Interaction, task: str):
    await interaction.response.defer(thinking=True)
    status = await interaction.followup.send(
        embed=make_kilo_embed("🔄 מפעיל Kilo CLI...", task)
    )

    async def on_event(etype: str, data: str):
        try:
            if etype == "done":
                summary = data[-1500:] if len(data) > 1500 else data
                e = make_kilo_embed(f"✅ **הושלם**\n```\n{summary}\n```", task)
                await status.edit(embed=e)
            elif etype == "error":
                await status.edit(embed=make_error_embed(data))
        except Exception:
            pass

    asyncio.create_task(kb.run_task(task, callback=on_event))


@tree.command(
    name="search", description="חיפוש ברשת", guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(query="שאילתת חיפוש")
async def cmd_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"חפש ברשת: {query}", "researcher")


@tree.command(
    name="run", description="הרץ קוד Python", guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(code="קוד Python")
async def cmd_run(interaction: discord.Interaction, code: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"הרץ:\n```python\n{code}\n```", "coder", "code")


@tree.command(
    name="recall",
    description="חפש בזיכרון הארוך-טווח",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(query="מה לחפש")
async def cmd_recall(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await call_gateway(
            "/recall",
            {
                "user_id": str(interaction.user.id),
                "query": query,
                "top_k": 5,
            },
        )
        memories = result.get("memories", [])
        if not memories:
            await interaction.followup.send("❌ לא נמצאו זיכרונות רלוונטיים.")
            return
        embed = discord.Embed(title=f"🧠 זיכרונות: {query}", color=COLORS["memory"])
        for m in memories:
            embed.add_field(
                name=f"Score: {m['score']} | {m['agent']}",
                value=m["text"][:300],
                inline=False,
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(
    name="store-memory",
    description="שמור מידע לזיכרון ארוך-טווח",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(text="מה לשמור")
async def cmd_store(interaction: discord.Interaction, text: str):
    try:
        await call_gateway(
            "/store-memory",
            {
                "user_id": str(interaction.user.id),
                "text": text,
                "agent": "user",
            },
        )
        await interaction.response.send_message(
            f"✅ נשמר בזיכרון: `{text[:100]}`", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            embed=make_error_embed(str(e)), ephemeral=True
        )


@tree.command(
    name="memory", description="סטטיסטיקות שימוש", guild=discord.Object(id=GUILD_ID)
)
async def cmd_memory(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{GATEWAY_URL}/memory/{interaction.user.id}") as resp:
                data = await resp.json()
        await interaction.followup.send(
            f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:1500]}\n```",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)), ephemeral=True)


@tree.command(
    name="project-new",
    description="צור פרויקט חדש (Category + 3 ערוצים)",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(name="שם הפרויקט")
async def cmd_project_new(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await pm.create_project(interaction.guild, name)
        embed = discord.Embed(
            title=f"📁 פרויקט נוצר: {name}",
            description="\n".join([f"<#{cid}>" for cid in result["channel_ids"]]),
            color=COLORS["success"],
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(
    name="project-add-channel",
    description="הוסף ערוץ לפרויקט קיים",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(
    project="שם הפרויקט",
    channel_name="שם הערוץ החדש",
    agent="סוכן: main / coder / researcher / analyzer",
)
async def cmd_add_ch(
    interaction: discord.Interaction,
    project: str,
    channel_name: str,
    agent: str = "main",
):
    await interaction.response.defer(thinking=True)
    try:
        result = await pm.add_channel_to_project(
            interaction.guild, project, channel_name, agent
        )
        await interaction.followup.send(
            f"✅ ערוץ <#{result['channel_id']}> נוסף לפרויקט **{project}** (agent: {agent})"
        )
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(
    name="help", description="רשימת כל הפקודות", guild=discord.Object(id=GUILD_ID)
)
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 OpenClaw v3 — פקודות", color=COLORS["main"])
    embed.add_field(
        name="🤖 Agents", value="/main  /coder  /research  /analyze", inline=False
    )
    embed.add_field(
        name="🧭 Multi-Agent", value="/orchestrate  /debate  /swarm", inline=False
    )
    embed.add_field(
        name="🔧 Tools",
        value="/search  /run  /kilo  /recall  /store-memory  /memory",
        inline=False,
    )
    embed.add_field(
        name="📁 Projects", value="/project-new  /project-add-channel", inline=False
    )
    embed.add_field(
        name="💬 ללא פקודה",
        value="כתוב בכל ערוץ — הסוכן יגיב ויפעיל tools אוטומטית",
        inline=False,
    )
    embed.add_field(
        name="⚡ Kilo", value="כתוב בערוץ **#kilo-code** → Kilo CLI", inline=False
    )
    embed.add_field(
        name="💻 Terminal", value="כתוב בערוץ **#terminal** → bash ישיר", inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── Context Menus ─────────────────────────────────────────────────


@tree.context_menu(name="🔍 Analyze Message", guild=discord.Object(id=GUILD_ID))
async def ctx_analyze(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"נתח: {message.content}", "analyzer", "analysis")


@tree.context_menu(name="🌐 Translate", guild=discord.Object(id=GUILD_ID))
async def ctx_translate(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"תרגם לעברית ולאנגלית: {message.content}", "main")


@tree.context_menu(name="📝 Summarize", guild=discord.Object(id=GUILD_ID))
async def ctx_summarize(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"סכם: {message.content}", "main")


@tree.context_menu(name="💡 Explain Code", guild=discord.Object(id=GUILD_ID))
async def ctx_explain(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)
    await _slash_agent(
        interaction, f"הסבר קוד שורה-שורה: {message.content}", "coder", "code"
    )


# ─── Helpers ──────────────────────────────────────────────────────


async def _slash_agent(
    interaction: discord.Interaction,
    prompt: str,
    agent: str,
    task_type: str = "default",
):
    """Common handler for all slash command agent calls."""
    try:
        result = await call_gateway(
            "/chat",
            {
                "user_id": str(interaction.user.id),
                "message": prompt,
                "agent": agent,
                "task_type": task_type,
                "channel_id": str(interaction.channel_id),
                "username": interaction.user.display_name,
                "project": get_project_for_channel(interaction.channel),
            },
        )
        embed = make_response_embed(
            result["response"],
            agent,
            result.get("model", "?"),
            result.get("duration", 0),
            result.get("iterations", 1),
            get_project_for_channel(interaction.channel),
        )
        view = ResponseView(
            original_message=prompt,
            agent=agent,
            channel_id=str(interaction.channel_id),
            user_id=str(interaction.user.id),
        )
        await interaction.followup.send(embed=embed, view=view)
        if result.get("plan"):
            from ui_helpers import make_plan_embed

            await interaction.channel.send(embed=make_plan_embed(result["plan"]))
        if result.get("tool_log"):
            await interaction.channel.send(
                embed=make_tool_log_embed(result["tool_log"])
            )
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


AGENT_PERSONA_NAMES = {
    "orchestrator": "🧭 Orchestrator",
    "coder": "💻 Coder",
    "researcher": "🔍 Researcher",
    "analyzer": "📊 Analyzer",
    "critic": "⚖️ Critic",
    "main": "🤖 OpenClaw",
}


async def _send_persona(channel: discord.TextChannel, agent: str, embed: discord.Embed):
    """Send a message as a named webhook persona."""
    name = AGENT_PERSONA_NAMES.get(agent, "🤖 OpenClaw")
    try:
        webhooks = await channel.webhooks()
        wh = next((w for w in webhooks if w.name == "OpenClaw"), None)
        if not wh:
            wh = await channel.create_webhook(name="OpenClaw")
        await wh.send(username=name, embed=embed)
    except Exception:
        await channel.send(embed=embed)


# ─── Bot lifecycle ─────────────────────────────────────────────────


@bot.event
async def on_ready():
    synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(
        f"✅ OpenClaw v3 | {bot.user} | Synced {len(synced)} commands to guild {GUILD_ID}"
    )


@bot.event
async def on_guild_available(guild: discord.Guild):
    if guild.id == GUILD_ID:
        await pm.init(guild)
        await kb.init()
        print(f"[INFO] Guild ready: {guild.name} ({guild.id})")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

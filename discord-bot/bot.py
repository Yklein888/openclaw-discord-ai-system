"""
OpenClaw Discord Bot v2.0
━━━━━━━━━━━━━━━━━━━━━━━━
Features:
  • Webhook Personas — each agent sends as its own Discord identity
  • Modals — multi-field pop-up forms
  • Context menus — right-click → AI actions
  • Autocomplete — /github & /clawhub with live suggestions
  • Progress bars — animated thinking embeds
  • Select menus — agent/model switcher after each response
  • 22 slash commands (20 original + /orchestrate + /debate)
  • All 4 channel handlers (#terminal #ai-admin #knowledge #clawhub)
"""

import os
import asyncio
import aiohttp
import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime
import time

# ─── Config ──────────────────────────────────────────────────────────────────
DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN", "")
GUILD_ID        = 1492111780934320138
ADMIN_ID        = "1488848655594295366"

BASE_URL        = "http://127.0.0.1:4001"
GATEWAY_URL     = f"{BASE_URL}/chat"
MEMORY_URL      = f"{BASE_URL}/memory"
SEARCH_URL      = f"{BASE_URL}/search"
CODE_URL        = f"{BASE_URL}/run-code"
GITHUB_URL      = f"{BASE_URL}/github"
NOTION_URL      = f"{BASE_URL}/notion"
VISION_URL      = f"{BASE_URL}/vision"
RECALL_URL      = f"{BASE_URL}/recall"
STORE_MEMORY_URL= f"{BASE_URL}/store-memory"
SWARM_URL       = f"{BASE_URL}/swarm"
ORCHESTRATE_URL = f"{BASE_URL}/orchestrate"
DEBATE_URL      = f"{BASE_URL}/debate"

LOGS_CHANNEL_ID   = 1493685126285234240
STATUS_CHANNEL_ID = 1493685127786663959

CLAWHUB_CHANNEL_NAME   = "clawhub"
AI_ADMIN_CHANNEL_NAME  = "ai-admin"
KNOWLEDGE_CHANNEL_NAME = "knowledge"
TERMINAL_CHANNEL_NAME  = "terminal"

# ערוצים שבהם הבוט עונה לכל הודעה ללא תיוג (ברירת מחדל = main)
# הוסף שמות ערוצים נוספים לפי הצורך
AUTO_RESPOND_CHANNELS = {
    "main", "chat", "general", "ai", "openclaw",
    AI_ADMIN_CHANNEL_NAME,    # #ai-admin כבר היה, עכשיו גם דרך הלוגיקה החדשה
    KNOWLEDGE_CHANNEL_NAME,
    CLAWHUB_CHANNEL_NAME,
}

# ─── Agent Config (colors, emojis, task_type) ─────────────────────────────────
AGENT_CONFIG = {
    "main":         {"color": 0x5865F2, "emoji": "🤖", "task_type": "default"},
    "coder":        {"color": 0x57F287, "emoji": "💻", "task_type": "code"},
    "research":     {"color": 0xFEE75C, "emoji": "🔍", "task_type": "default"},
    "analyze":      {"color": 0xED4245, "emoji": "📊", "task_type": "analysis"},
    "orchestrator": {"color": 0xFF6B6B, "emoji": "🧭", "task_type": "default"},
    "researcher":   {"color": 0xFEE75C, "emoji": "🔍", "task_type": "default"},
    "analyzer":     {"color": 0xED4245, "emoji": "📊", "task_type": "analysis"},
    "critic":       {"color": 0xFF9F43, "emoji": "⚖️", "task_type": "analysis"},
}

# ─── Webhook Personas ─────────────────────────────────────────────────────────
# Map agent name → (display name, avatar URL)
AGENT_PERSONAS = {
    "orchestrator": ("🧭 Orchestrator",   "https://i.imgur.com/4M34hi2.png"),
    "coder":        ("💻 Coder",           "https://i.imgur.com/OB0y6MR.png"),
    "researcher":   ("🔍 Researcher",      "https://i.imgur.com/LiXpkPZ.png"),
    "analyzer":     ("📊 Analyzer",        "https://i.imgur.com/Wsx2gxk.png"),
    "critic":       ("⚖️ Critic",          "https://i.imgur.com/7Xy3Cun.png"),
}

# ─── ClawHub Skills ───────────────────────────────────────────────────────────
ALL_SKILLS = [
    ("hebrew",      "עברית",            "שיחה בעברית"),
    ("code",        "קוד",              "כתיבת קוד"),
    ("research",    "מחקר",             "מחקר מעמיק"),
    ("analyze",     "ניתוח",            "ניתוח נתונים"),
    ("translate",   "תרגום",            "תרגום טקסטים"),
    ("summarize",   "סיכום",            "סיכום מסמכים"),
    ("explain",     "הסבר",             "הסבר מושגים"),
    ("debug",       "דיבוג",            "מציאת באגים"),
    ("refactor",    "ריפקטור",          "שיפור קוד"),
    ("review",      "ביקורת קוד",       "ביקורת קוד"),
    ("plan",        "תכנון",            "תכנון פרויקט"),
    ("brainstorm",  "סיעור מוחות",      "יצירת רעיונות"),
    ("math",        "מתמטיקה",          "פתרון בעיות מתמטיות"),
    ("story",       "סיפור",            "כתיבת סיפורים"),
    ("marketing",   "שיווק",            "כתיבת תוכן שיווקי"),
    ("email",       "אימייל",           "כתיבת מיילים"),
    ("social",      "רשתות חברתיות",   "תוכן לרשתות"),
    ("security",    "אבטחה",            "ניתוח אבטחה"),
    ("devops",      "דבאופס",           "תשתית וענן"),
    ("data",        "דאטה",             "ניתוח דאטה"),
    ("api",         "API",              "עיצוב ממשקים"),
    ("database",    "מסד נתונים",       "עיצוב DB"),
    ("mobile",      "מובייל",           "פיתוח מובייל"),
    ("web",         "Web",              "פיתוח Web"),
    ("ai",          "AI",               "מוצרי AI"),
]

PROGRESS_FRAMES = [
    "⬜⬜⬜⬜⬜",
    "🟦⬜⬜⬜⬜",
    "🟦🟦⬜⬜⬜",
    "🟦🟦🟦⬜⬜",
    "🟦🟦🟦🟦⬜",
    "🟦🟦🟦🟦🟦",
]

# ─── Bot Setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ─── Helpers ──────────────────────────────────────────────────────────────────

def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."

def agent_embed(agent: str, content: str, username: str = "", model: str = "", duration: float = 0) -> discord.Embed:
    cfg = AGENT_CONFIG.get(agent, AGENT_CONFIG["main"])
    embed = discord.Embed(
        description=truncate(content),
        color=cfg["color"],
        timestamp=datetime.utcnow()
    )
    footer_parts = []
    if username:
        footer_parts.append(f"👤 {username}")
    if model:
        footer_parts.append(f"🤖 {model}")
    if duration:
        footer_parts.append(f"⏱ {duration}s")
    embed.set_footer(text=" • ".join(footer_parts) if footer_parts else "OpenClaw v2.0")
    return embed

def thinking_embed(agent: str, frame: int = 0) -> discord.Embed:
    cfg = AGENT_CONFIG.get(agent, AGENT_CONFIG["main"])
    bar = PROGRESS_FRAMES[frame % len(PROGRESS_FRAMES)]
    embed = discord.Embed(
        title=f"{cfg['emoji']} {agent.capitalize()} חושב...",
        description=f"{bar}\n*מעבד את הבקשה...*",
        color=cfg["color"]
    )
    return embed

async def post_json(url: str, data: dict, timeout: int = 60) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            return await resp.json()

async def get_json(url: str, timeout: int = 30) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            return await resp.json()

async def animate_thinking(message: discord.Message, agent: str, stop_event: asyncio.Event):
    """Animate the progress bar in the thinking embed until stop_event is set."""
    frame = 0
    elapsed = 0
    while not stop_event.is_set():
        await asyncio.sleep(1.2)
        elapsed += 1.2
        frame += 1
        cfg = AGENT_CONFIG.get(agent, AGENT_CONFIG["main"])
        bar = PROGRESS_FRAMES[frame % len(PROGRESS_FRAMES)]
        try:
            embed = discord.Embed(
                title=f"{cfg['emoji']} {agent.capitalize()} חושב...",
                description=f"{bar}\n*{elapsed:.0f}s — מעבד...*",
                color=cfg["color"]
            )
            await message.edit(embed=embed)
        except Exception:
            break

async def send_via_webhook(channel: discord.TextChannel, agent: str, content: str, embed: discord.Embed = None) -> bool:
    """Send a message as the agent's persona via webhook. Falls back to normal send."""
    persona = AGENT_PERSONAS.get(agent)
    if not persona:
        return False
    name, avatar = persona
    try:
        # Find or create webhook
        webhooks = await channel.webhooks()
        wh = next((w for w in webhooks if w.name == "OpenClaw Personas"), None)
        if not wh:
            wh = await channel.create_webhook(name="OpenClaw Personas")
        if embed:
            await wh.send(username=name, avatar_url=avatar, embed=embed)
        else:
            await wh.send(content=truncate(content, 2000), username=name, avatar_url=avatar)
        return True
    except Exception:
        return False

async def log_to_discord(bot_instance, message: str):
    try:
        ch = bot_instance.get_channel(LOGS_CHANNEL_ID)
        if ch:
            await ch.send(f"📋 {message}"[:2000])
    except Exception:
        pass

# ─── Views ────────────────────────────────────────────────────────────────────

class AgentSelectMenu(ui.Select):
    def __init__(self, original_prompt: str, user_id: str, username: str):
        self.original_prompt = original_prompt
        self.user_id = user_id
        self.username = username
        options = [
            discord.SelectOption(label="🤖 Main",       value="main",       description="סוכן כללי"),
            discord.SelectOption(label="💻 Coder",      value="coder",      description="מומחה קוד"),
            discord.SelectOption(label="🔍 Research",   value="research",   description="חוקר מידע"),
            discord.SelectOption(label="📊 Analyze",    value="analyze",    description="מנתח אסטרטגי"),
            discord.SelectOption(label="🧭 Orchestrate",value="orchestrator",description="מתאם רב-סוכנים"),
        ]
        super().__init__(placeholder="🔄 שאל שוב עם סוכן אחר...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        agent = self.values[0]
        await interaction.response.defer()
        result = await post_json(GATEWAY_URL, {
            "user_id": self.user_id,
            "message": self.original_prompt,
            "username": self.username,
            "agent": agent,
        })
        embed = agent_embed(agent, result.get("response", "שגיאה"), self.username,
                            result.get("model", ""), result.get("duration", 0))
        await interaction.followup.send(embed=embed, ephemeral=False)


class AgentSelectView(ui.View):
    def __init__(self, original_prompt: str, user_id: str, username: str):
        super().__init__(timeout=120)
        self.add_item(AgentSelectMenu(original_prompt, user_id, username))


class ResponseView(ui.View):
    """Buttons shown after every AI response."""
    def __init__(self, original_prompt: str, user_id: str, username: str, agent: str = "main"):
        super().__init__(timeout=180)
        self.original_prompt = original_prompt
        self.user_id = user_id
        self.username = username
        self.agent = agent

    @ui.button(label="🔄 שאל שוב", style=discord.ButtonStyle.secondary)
    async def ask_again(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        result = await post_json(GATEWAY_URL, {
            "user_id": self.user_id,
            "message": self.original_prompt,
            "username": self.username,
            "agent": self.agent,
        })
        embed = agent_embed(self.agent, result.get("response", "שגיאה"), self.username,
                            result.get("model", ""), result.get("duration", 0))
        view = ResponseView(self.original_prompt, self.user_id, self.username, self.agent)
        view.add_item(AgentSelectMenu(self.original_prompt, self.user_id, self.username))
        await interaction.followup.send(embed=embed, view=view)

    @ui.button(label="🔀 החלף סוכן", style=discord.ButtonStyle.primary)
    async def switch_agent(self, interaction: discord.Interaction, button: ui.Button):
        view = AgentSelectView(self.original_prompt, self.user_id, self.username)
        await interaction.response.send_message("בחר סוכן:", view=view, ephemeral=True)

    @ui.button(label="🗑️ מחק", style=discord.ButtonStyle.danger)
    async def delete_msg(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("✅ נמחק", ephemeral=True)


# ─── Modals ───────────────────────────────────────────────────────────────────

class AnalyzeModal(ui.Modal, title="📊 ניתוח מעמיק"):
    topic = ui.TextInput(label="מה לנתח?", placeholder="תאר את הנושא/קוד/בעיה...", style=discord.TextStyle.paragraph, max_length=1000)
    context_field = ui.TextInput(label="הקשר נוסף (אופציונלי)", required=False, style=discord.TextStyle.paragraph, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        prompt = str(self.topic)
        if self.context_field.value:
            prompt += f"\n\nהקשר: {self.context_field.value}"
        msg = await interaction.followup.send(embed=thinking_embed("analyze"))
        stop = asyncio.Event()
        anim = asyncio.create_task(animate_thinking(msg, "analyze", stop))
        result = await post_json(GATEWAY_URL, {
            "user_id": str(interaction.user.id),
            "message": prompt,
            "username": interaction.user.display_name,
            "agent": "analyze",
            "task_type": "analysis",
        })
        stop.set()
        anim.cancel()
        embed = agent_embed("analyze", result.get("response", "שגיאה"),
                            interaction.user.display_name, result.get("model", ""), result.get("duration", 0))
        view = ResponseView(prompt, str(interaction.user.id), interaction.user.display_name, "analyze")
        await msg.edit(embed=embed, view=view)


class ResearchModal(ui.Modal, title="🔍 מחקר מקיף"):
    query = ui.TextInput(label="מה לחקור?", placeholder="שאלה או נושא למחקר...", style=discord.TextStyle.paragraph, max_length=800)
    depth = ui.TextInput(label="עומק המחקר", placeholder="קצר / בינוני / מעמיק", required=False, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        prompt = str(self.query)
        depth_val = str(self.depth) if self.depth.value else "בינוני"
        prompt += f"\n\nרמת פירוט: {depth_val}"
        msg = await interaction.followup.send(embed=thinking_embed("research"))
        stop = asyncio.Event()
        anim = asyncio.create_task(animate_thinking(msg, "research", stop))
        result = await post_json(GATEWAY_URL, {
            "user_id": str(interaction.user.id),
            "message": prompt,
            "username": interaction.user.display_name,
            "agent": "research",
        })
        stop.set()
        anim.cancel()
        embed = agent_embed("research", result.get("response", "שגיאה"),
                            interaction.user.display_name, result.get("model", ""), result.get("duration", 0))
        view = ResponseView(prompt, str(interaction.user.id), interaction.user.display_name, "research")
        await msg.edit(embed=embed, view=view)


class OrchestrateModal(ui.Modal, title="🧭 Orchestrator — רב-סוכנים"):
    task = ui.TextInput(label="מה המשימה?", placeholder="תאר משימה מורכבת...", style=discord.TextStyle.paragraph, max_length=1000)
    agents_field = ui.TextInput(label="סוכנים (אופציונלי, מופרד בפסיקים)", placeholder="coder,researcher,analyzer", required=False, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        task = str(self.task)
        agents_raw = str(self.agents_field).strip() if self.agents_field.value else ""
        agents = [a.strip() for a in agents_raw.split(",") if a.strip()] if agents_raw else None
        msg = await interaction.followup.send(embed=thinking_embed("orchestrator"))
        stop = asyncio.Event()
        anim = asyncio.create_task(animate_thinking(msg, "orchestrator", stop))
        result = await post_json(ORCHESTRATE_URL, {
            "user_id": str(interaction.user.id),
            "username": interaction.user.display_name,
            "task": task,
            "agents": agents,
        }, timeout=90)
        stop.set()
        anim.cancel()
        await _send_orchestrate_result(msg, result, interaction.user, task)


class DebateModal(ui.Modal, title="⚔️ דיון — בעד ונגד"):
    topic = ui.TextInput(label="נושא הדיון", placeholder="לדוגמה: האם AI יחליף מפתחים?", max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        topic = str(self.topic)
        msg = await interaction.followup.send(embed=thinking_embed("orchestrator"))
        stop = asyncio.Event()
        anim = asyncio.create_task(animate_thinking(msg, "orchestrator", stop))
        result = await post_json(DEBATE_URL, {
            "user_id": str(interaction.user.id),
            "username": interaction.user.display_name,
            "topic": topic,
        }, timeout=90)
        stop.set()
        anim.cancel()
        await _send_debate_result(msg, result, interaction.user, topic)


# ─── Shared result renderers ─────────────────────────────────────────────────

async def _send_orchestrate_result(msg, result: dict, user: discord.User, task: str):
    """
    FRONT: synthesis embed — זה מה שהמשתמש רואה בצורה ברורה.
    BACKGROUND: agent responses נשלחים דרך webhook personas (פרטי מאחורי הקלעים).
    """
    agents_used = result.get("agents_used", [])
    synthesis = result.get("synthesis", "שגיאה")
    duration = result.get("duration", 0)
    critic_text = result.get("critic", {}).get("response", "")

    # ── FRONT — התשובה הגלויה והמרכזית ──────────────────────────────────────
    embed = discord.Embed(
        title="🧭 תשובה מסוכמת",
        description=truncate(synthesis),
        color=0xFF6B6B,
        timestamp=datetime.utcnow()
    )
    agents_label = " • ".join(f"`{a}`" for a in agents_used) if agents_used else "auto"
    embed.add_field(name="🔧 סוכנים", value=agents_label, inline=True)
    embed.add_field(name="⏱ זמן", value=f"{duration}s", inline=True)
    if critic_text:
        embed.add_field(name="⚖️ ביקורת קצרה", value=truncate(critic_text, 300), inline=False)
    embed.set_footer(text=f"👤 {user.display_name} | OpenClaw Orchestrator v2.0")
    await msg.edit(embed=embed)

    # ── BACKGROUND — webhook personas (מאחורי הקלעים) ──────────────────────
    # כל סוכן שולח את התוצאה שלו עם הזהות שלו, בשקט אחרי התשובה הראשית
    agent_responses = result.get("agent_responses", {})
    if isinstance(msg.channel, discord.TextChannel) and agent_responses:
        for agent_name, data in agent_responses.items():
            resp = data.get("response", "")
            model = data.get("model", "")
            if not resp:
                continue
            embed_ag = agent_embed(agent_name, resp[:1500], "", model)
            # Try webhook persona first; silently ignore failures
            await send_via_webhook(msg.channel, agent_name, resp, embed_ag)


async def _send_debate_result(msg, result: dict, user: discord.User, topic: str):
    pro = result.get("pro", {}).get("response", "")
    con = result.get("con", {}).get("response", "")
    verdict = result.get("verdict", {}).get("response", "")
    duration = result.get("duration", 0)

    embed = discord.Embed(title=f"⚔️ דיון: {topic[:80]}", color=0x9B59B6, timestamp=datetime.utcnow())
    embed.add_field(name="✅ בעד (Researcher)", value=truncate(pro, 600), inline=False)
    embed.add_field(name="❌ נגד (Analyzer)", value=truncate(con, 600), inline=False)
    embed.add_field(name="⚖️ פסיקה (Critic)", value=truncate(verdict, 700), inline=False)
    embed.set_footer(text=f"👤 {user.display_name} • ⏱ {duration}s")
    await msg.edit(embed=embed)


# ─── Context Menus ────────────────────────────────────────────────────────────

@tree.context_menu(name="🔍 Analyze Message")
async def ctx_analyze(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=False)
    text = message.content or "[no text content]"
    msg = await interaction.followup.send(embed=thinking_embed("analyze"))
    stop = asyncio.Event()
    anim = asyncio.create_task(animate_thinking(msg, "analyze", stop))
    result = await post_json(GATEWAY_URL, {
        "user_id": str(interaction.user.id),
        "message": f"נתח לעומק:\n{text[:800]}",
        "username": interaction.user.display_name,
        "agent": "analyze",
        "task_type": "analysis",
    })
    stop.set(); anim.cancel()
    embed = agent_embed("analyze", result.get("response", "שגיאה"),
                        interaction.user.display_name, result.get("model", ""), result.get("duration", 0))
    await msg.edit(embed=embed)


@tree.context_menu(name="🌐 Translate")
async def ctx_translate(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=False)
    text = message.content or "[no text content]"
    msg = await interaction.followup.send(embed=thinking_embed("main"))
    stop = asyncio.Event()
    anim = asyncio.create_task(animate_thinking(msg, "main", stop))
    result = await post_json(GATEWAY_URL, {
        "user_id": str(interaction.user.id),
        "message": f"תרגם לעברית ולאנגלית:\n{text[:800]}",
        "username": interaction.user.display_name,
        "agent": "main",
    })
    stop.set(); anim.cancel()
    embed = agent_embed("main", result.get("response", "שגיאה"),
                        interaction.user.display_name, result.get("model", ""), result.get("duration", 0))
    await msg.edit(embed=embed)


@tree.context_menu(name="📝 Summarize")
async def ctx_summarize(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=False)
    text = message.content or "[no text content]"
    msg = await interaction.followup.send(embed=thinking_embed("main"))
    stop = asyncio.Event()
    anim = asyncio.create_task(animate_thinking(msg, "main", stop))
    result = await post_json(GATEWAY_URL, {
        "user_id": str(interaction.user.id),
        "message": f"סכם בקצרה:\n{text[:800]}",
        "username": interaction.user.display_name,
        "agent": "main",
    })
    stop.set(); anim.cancel()
    embed = agent_embed("main", result.get("response", "שגיאה"),
                        interaction.user.display_name, result.get("model", ""), result.get("duration", 0))
    await msg.edit(embed=embed)


@tree.context_menu(name="💡 Explain Code")
async def ctx_explain(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=False)
    text = message.content or "[no text content]"
    msg = await interaction.followup.send(embed=thinking_embed("coder"))
    stop = asyncio.Event()
    anim = asyncio.create_task(animate_thinking(msg, "coder", stop))
    result = await post_json(GATEWAY_URL, {
        "user_id": str(interaction.user.id),
        "message": f"הסבר את הקוד הבא שורה אחרי שורה:\n{text[:800]}",
        "username": interaction.user.display_name,
        "agent": "coder",
        "task_type": "code",
    })
    stop.set(); anim.cancel()
    embed = agent_embed("coder", result.get("response", "שגיאה"),
                        interaction.user.display_name, result.get("model", ""), result.get("duration", 0))
    await msg.edit(embed=embed)


# ─── Autocomplete ─────────────────────────────────────────────────────────────

async def autocomplete_skill(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=f"{s[1]} — {s[2]}", value=s[0])
        for s in ALL_SKILLS
        if current.lower() in s[0] or current.lower() in s[1]
    ][:25]


async def autocomplete_github_repo(interaction: discord.Interaction, current: str):
    common = ["YitziKlein/", "YitziKlein/dealcellularyk", "YitziKlein/kleinkitch",
              "anthropics/anthropic-sdk-python", "discord/discord.py"]
    return [
        app_commands.Choice(name=r, value=r)
        for r in common if current.lower() in r.lower()
    ][:10]


# ─── Core AI helper (with progress bar) ──────────────────────────────────────

async def run_agent_cmd(interaction: discord.Interaction, prompt: str, agent: str,
                        task_type: str = "default", extra_fields: dict = None):
    """Defer → thinking embed with animation → call gateway → edit with result."""
    await interaction.response.defer()
    msg = await interaction.followup.send(embed=thinking_embed(agent))

    stop = asyncio.Event()
    anim = asyncio.create_task(animate_thinking(msg, agent, stop))

    payload = {
        "user_id": str(interaction.user.id),
        "message": prompt,
        "username": interaction.user.display_name,
        "agent": agent,
        "task_type": task_type,
        "channel_id": str(interaction.channel_id) if interaction.channel_id else "slash",
    }
    if extra_fields:
        payload.update(extra_fields)

    try:
        result = await post_json(GATEWAY_URL, payload, timeout=60)
    except Exception as e:
        stop.set(); anim.cancel()
        await msg.edit(embed=discord.Embed(title="❌ שגיאה", description=str(e), color=0xFF0000))
        return

    stop.set(); anim.cancel()
    embed = agent_embed(agent, result.get("response", "שגיאה"),
                        interaction.user.display_name,
                        result.get("model", ""), result.get("duration", 0))
    view = ResponseView(prompt, str(interaction.user.id), interaction.user.display_name, agent)
    await msg.edit(embed=embed, view=view)


# ─── Slash Commands ───────────────────────────────────────────────────────────

@tree.command(name="main", description="שיחה עם הסוכן הראשי", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt="מה אתה רוצה לשאול?")
async def cmd_main(interaction: discord.Interaction, prompt: str):
    await run_agent_cmd(interaction, prompt, "main")


@tree.command(name="coder", description="סוכן קוד — כתיבה, דיבוג, הסבר", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt="מה הקוד שאתה צריך?")
async def cmd_coder(interaction: discord.Interaction, prompt: str):
    await run_agent_cmd(interaction, prompt, "coder", "code")


@tree.command(name="research", description="חוקר מידע מעמיק", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt="מה לחקור?")
async def cmd_research(interaction: discord.Interaction, prompt: str = None):
    if not prompt:
        modal = ResearchModal()
        await interaction.response.send_modal(modal)
        return
    await run_agent_cmd(interaction, prompt, "research")


@tree.command(name="analyze", description="ניתוח עמוק עם Modal", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt="מה לנתח? (ריק = פתח Modal)")
async def cmd_analyze(interaction: discord.Interaction, prompt: str = None):
    if not prompt:
        modal = AnalyzeModal()
        await interaction.response.send_modal(modal)
        return
    await run_agent_cmd(interaction, prompt, "analyze", "analysis")


@tree.command(name="orchestrate", description="🧭 Orchestrator — מפעיל כמה סוכנים חכם", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(task="משימה מורכבת (ריק = פתח Modal)")
async def cmd_orchestrate(interaction: discord.Interaction, task: str = None):
    if not task:
        await interaction.response.send_modal(OrchestrateModal())
        return
    await interaction.response.defer()
    msg = await interaction.followup.send(embed=thinking_embed("orchestrator"))
    stop = asyncio.Event()
    anim = asyncio.create_task(animate_thinking(msg, "orchestrator", stop))
    try:
        result = await post_json(ORCHESTRATE_URL, {
            "user_id": str(interaction.user.id),
            "username": interaction.user.display_name,
            "task": task,
        }, timeout=120)
    except Exception as e:
        stop.set(); anim.cancel()
        await msg.edit(embed=discord.Embed(title="❌ שגיאה", description=str(e), color=0xFF0000))
        return
    stop.set(); anim.cancel()
    await _send_orchestrate_result(msg, result, interaction.user, task)


@tree.command(name="debate", description="⚔️ דיון בעד/נגד עם פסיקה", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(topic="נושא הדיון (ריק = Modal)")
async def cmd_debate(interaction: discord.Interaction, topic: str = None):
    if not topic:
        await interaction.response.send_modal(DebateModal())
        return
    await interaction.response.defer()
    msg = await interaction.followup.send(embed=thinking_embed("orchestrator"))
    stop = asyncio.Event()
    anim = asyncio.create_task(animate_thinking(msg, "orchestrator", stop))
    try:
        result = await post_json(DEBATE_URL, {
            "user_id": str(interaction.user.id),
            "username": interaction.user.display_name,
            "topic": topic,
        }, timeout=90)
    except Exception as e:
        stop.set(); anim.cancel()
        await msg.edit(embed=discord.Embed(title="❌ שגיאה", description=str(e), color=0xFF0000))
        return
    stop.set(); anim.cancel()
    await _send_debate_result(msg, result, interaction.user, topic)


@tree.command(name="swarm", description="🐝 Swarm — 4 סוכנים במקביל", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(task="משימה לסוורם")
async def cmd_swarm(interaction: discord.Interaction, task: str):
    await interaction.response.defer()
    msg = await interaction.followup.send(embed=thinking_embed("orchestrator"))
    stop = asyncio.Event()
    anim = asyncio.create_task(animate_thinking(msg, "orchestrator", stop))
    try:
        result = await post_json(SWARM_URL, {
            "user_id": str(interaction.user.id),
            "username": interaction.user.display_name,
            "task": task,
        }, timeout=120)
    except Exception as e:
        stop.set(); anim.cancel()
        await msg.edit(embed=discord.Embed(title="❌ שגיאה", description=str(e), color=0xFF0000))
        return
    stop.set(); anim.cancel()

    synthesis = result.get("synthesis", "שגיאה")
    agents_data = result.get("agents", {})
    duration = result.get("duration", 0)

    embed = discord.Embed(
        title="🐝 Swarm — תוצאה משולבת",
        description=truncate(synthesis),
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    for ag, data in agents_data.items():
        emoji = AGENT_CONFIG.get(ag, {}).get("emoji", "🤖")
        embed.add_field(
            name=f"{emoji} {ag.capitalize()}",
            value=truncate(data.get("response", ""), 300),
            inline=False
        )
    embed.set_footer(text=f"👤 {interaction.user.display_name} • ⏱ {duration}s")
    await msg.edit(embed=embed)

    # Send agent responses via webhook personas
    if isinstance(msg.channel, discord.TextChannel):
        for ag, data in agents_data.items():
            emb = agent_embed(ag, data.get("response", ""), "", data.get("model", ""))
            await send_via_webhook(msg.channel, ag, data.get("response", ""), emb)


@tree.command(name="search", description="🔎 חיפוש ב-DuckDuckGo", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(query="מה לחפש?")
async def cmd_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        result = await post_json(SEARCH_URL, {"query": query, "max_results": 5})
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    results = result.get("results", [])
    if not results:
        await interaction.followup.send("🔍 לא נמצאו תוצאות.")
        return
    embed = discord.Embed(title=f"🔎 תוצאות: {query[:60]}", color=0x5865F2, timestamp=datetime.utcnow())
    for r in results[:5]:
        embed.add_field(
            name=r.get("title", "")[:80],
            value=f"[קישור]({r.get('url', '#')})\n{r.get('body', '')[:200]}",
            inline=False
        )
    embed.set_footer(text=f"👤 {interaction.user.display_name} • {result.get('count', 0)} תוצאות")
    await interaction.followup.send(embed=embed)


@tree.command(name="run", description="▶️ הרץ קוד Python", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(code="קוד Python להרצה")
async def cmd_run(interaction: discord.Interaction, code: str):
    await interaction.response.defer()
    try:
        result = await post_json(CODE_URL, {"code": code})
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    success = result.get("success", False)
    output = result.get("output", "")
    color = 0x57F287 if success else 0xED4245
    embed = discord.Embed(
        title="✅ הצלחה" if success else "❌ שגיאה",
        description=f"```\n{truncate(output, 1900)}\n```",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"⏱ {result.get('duration', 0)}s")
    await interaction.followup.send(embed=embed)


@tree.command(name="memory", description="🧠 זיכרון המשתמש", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user_id="מזהה משתמש (ריק = שלך)")
async def cmd_memory(interaction: discord.Interaction, user_id: str = None):
    await interaction.response.defer()
    uid = user_id or str(interaction.user.id)
    try:
        mem = await get_json(f"{MEMORY_URL}/{uid}")
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    embed = discord.Embed(title="🧠 זיכרון משתמש", color=0x5865F2, timestamp=datetime.utcnow())
    embed.add_field(name="👤 שם", value=mem.get("username", "Unknown"), inline=True)
    embed.add_field(name="📊 בקשות", value=str(mem.get("request_count", 0)), inline=True)
    embed.add_field(name="🌐 שפה", value=mem.get("language", "he"), inline=True)
    embed.add_field(name="⭐ סוכן מועדף", value=mem.get("favorite_agent", "none"), inline=True)
    embed.add_field(name="⏱ זמן ממוצע", value=f"{mem.get('avg_duration', 0)}s", inline=True)
    embed.add_field(name="💬 הודעות בהקשר", value=str(mem.get("context_messages", 0)), inline=True)
    await interaction.followup.send(embed=embed)


@tree.command(name="recall", description="🔮 חיפוש בזיכרון הסמנטי", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(query="מה לחפש בזיכרון?")
async def cmd_recall(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        result = await post_json(RECALL_URL, {"user_id": str(interaction.user.id), "query": query, "top_k": 5})
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    memories = result.get("memories", [])
    if not memories:
        await interaction.followup.send("🔮 לא נמצאו זיכרונות רלוונטיים.")
        return
    embed = discord.Embed(title=f"🔮 זיכרונות: {query[:50]}", color=0x9B59B6, timestamp=datetime.utcnow())
    for m in memories[:5]:
        score = m.get("score", 0)
        bar = "🟩" * int(score * 5) + "⬜" * (5 - int(score * 5))
        embed.add_field(
            name=f"{bar} {score:.2f} | {m.get('agent', 'main')}",
            value=m.get("text", "")[:300],
            inline=False
        )
    await interaction.followup.send(embed=embed)


@tree.command(name="store-memory", description="💾 שמור זיכרון ידנית", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(text="הטקסט לשמור")
async def cmd_store_memory(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    try:
        await post_json(STORE_MEMORY_URL, {"user_id": str(interaction.user.id), "text": text, "agent": "main"})
        await interaction.followup.send(f"✅ נשמר: *{text[:80]}*")
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


@tree.command(name="github", description="📦 מידע על GitHub repo", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(repo="owner/repo")
@app_commands.autocomplete(repo=autocomplete_github_repo)
async def cmd_github(interaction: discord.Interaction, repo: str):
    await interaction.response.defer()
    parts = repo.strip("/").split("/")
    if len(parts) < 2:
        await interaction.followup.send("❌ פורמט: owner/repo")
        return
    owner, repo_name = parts[0], parts[1]
    try:
        data = await get_json(f"{GITHUB_URL}/repo/{owner}/{repo_name}")
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    if "error" in data:
        await interaction.followup.send(f"❌ {data['error']}")
        return
    embed = discord.Embed(title=f"📦 {data.get('name', repo)}", url=data.get("url", ""), color=0x24292E)
    embed.description = data.get("description", "*אין תיאור*")
    embed.add_field(name="⭐ Stars", value=str(data.get("stars", 0)), inline=True)
    embed.add_field(name="🍴 Forks", value=str(data.get("forks", 0)), inline=True)
    embed.add_field(name="🐛 Issues", value=str(data.get("open_issues", 0)), inline=True)
    embed.add_field(name="💻 Language", value=data.get("language", "N/A"), inline=True)
    embed.add_field(name="🌿 Branch", value=data.get("default_branch", "main"), inline=True)
    embed.add_field(name="🔒 Private", value="✅" if data.get("private") else "❌", inline=True)
    await interaction.followup.send(embed=embed)


@tree.command(name="github-prs", description="📋 Pull Requests של repo", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(repo="owner/repo", state="open/closed/all")
async def cmd_github_prs(interaction: discord.Interaction, repo: str, state: str = "open"):
    await interaction.response.defer()
    parts = repo.strip("/").split("/")
    if len(parts) < 2:
        await interaction.followup.send("❌ פורמט: owner/repo")
        return
    try:
        data = await get_json(f"{GITHUB_URL}/prs/{parts[0]}/{parts[1]}?state={state}")
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    if "error" in data:
        await interaction.followup.send(f"❌ {data['error']}")
        return
    prs = data.get("prs", [])
    embed = discord.Embed(title=f"📋 PRs: {repo} ({state})", color=0x238636)
    for pr in prs[:8]:
        embed.add_field(
            name=f"#{pr['number']} {pr['title'][:60]}",
            value=f"👤 {pr['user']} • 📅 {pr['created_at']} • [קישור]({pr['url']})",
            inline=False
        )
    if not prs:
        embed.description = "לא נמצאו PRs."
    await interaction.followup.send(embed=embed)


@tree.command(name="github-commits", description="📝 קומיטים אחרונים", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(repo="owner/repo")
async def cmd_github_commits(interaction: discord.Interaction, repo: str):
    await interaction.response.defer()
    parts = repo.strip("/").split("/")
    if len(parts) < 2:
        await interaction.followup.send("❌ פורמט: owner/repo")
        return
    try:
        data = await get_json(f"{GITHUB_URL}/commits/{parts[0]}/{parts[1]}")
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    if "error" in data:
        await interaction.followup.send(f"❌ {data['error']}")
        return
    commits = data.get("commits", [])
    embed = discord.Embed(title=f"📝 Commits: {repo}", color=0x24292E)
    for c in commits[:5]:
        embed.add_field(
            name=f"`{c['sha']}` {c['message'][:60]}",
            value=f"👤 {c['author']} • 📅 {c['date']} • [קישור]({c['url']})",
            inline=False
        )
    await interaction.followup.send(embed=embed)


@tree.command(name="notion-add", description="📓 הוסף לNotion", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(text="תוכן הפתקה", title="כותרת (אופציונלי)")
async def cmd_notion_add(interaction: discord.Interaction, text: str, title: str = None):
    await interaction.response.defer()
    try:
        result = await post_json(f"{NOTION_URL}/add", {"text": text, "title": title})
        if "error" in result:
            await interaction.followup.send(f"❌ {result['error']}")
        else:
            await interaction.followup.send(f"✅ נוצר בNotion: [{result.get('page_id', '')[:8]}...]({result.get('url', '#')})")
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


@tree.command(name="notion-list", description="📋 רשימת פתקים אחרונים", guild=discord.Object(id=GUILD_ID))
async def cmd_notion_list(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        result = await get_json(f"{NOTION_URL}/list")
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    pages = result.get("pages", [])
    embed = discord.Embed(title="📋 Notion — פתקים אחרונים", color=0x000000, timestamp=datetime.utcnow())
    for p in pages[:8]:
        embed.add_field(
            name=p.get("title", "(ללא כותרת)")[:60],
            value=f"📅 {p.get('edited', '')} • [פתח]({p.get('url', '#')})",
            inline=False
        )
    await interaction.followup.send(embed=embed)


@tree.command(name="notion-search", description="🔍 חיפוש בNotion", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(query="מה לחפש?")
async def cmd_notion_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        result = await get_json(f"{NOTION_URL}/search?q={query}")
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")
        return
    pages = result.get("results", [])
    if not pages:
        await interaction.followup.send("🔍 לא נמצאו תוצאות.")
        return
    embed = discord.Embed(title=f"🔍 Notion: {query[:50]}", color=0x000000)
    for p in pages[:5]:
        embed.add_field(
            name=p.get("title", "(ללא כותרת)")[:60],
            value=f"[{p.get('type', '')}]({p.get('url', '#')})",
            inline=False
        )
    await interaction.followup.send(embed=embed)


@tree.command(name="clawhub", description="🎯 ClawHub — כישורי AI", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(skill="בחר כישור", prompt="הבקשה שלך")
@app_commands.autocomplete(skill=autocomplete_skill)
async def cmd_clawhub(interaction: discord.Interaction, skill: str, prompt: str):
    skill_data = next((s for s in ALL_SKILLS if s[0] == skill), None)
    agent = "coder" if skill in ("code", "debug", "refactor", "review", "api", "database") else "research" if skill in ("research", "math", "data") else "analyze" if skill in ("analyze", "plan", "security") else "main"
    full_prompt = f"[כישור: {skill_data[1] if skill_data else skill}] {prompt}"
    await run_agent_cmd(interaction, full_prompt, agent)


@tree.command(name="skill-top", description="⭐ הכישורים הפופולריים", guild=discord.Object(id=GUILD_ID))
async def cmd_skill_top(interaction: discord.Interaction):
    embed = discord.Embed(title="⭐ Top ClawHub Skills", color=0xFEE75C, timestamp=datetime.utcnow())
    top = ALL_SKILLS[:10]
    for s in top:
        embed.add_field(name=s[1], value=s[2], inline=True)
    await interaction.response.send_message(embed=embed)


@tree.command(name="schedule", description="⏰ תזמון משימה", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(task="משימה לתזמן", delay_minutes="דחייה בדקות")
async def cmd_schedule(interaction: discord.Interaction, task: str, delay_minutes: int = 5):
    await interaction.response.send_message(
        f"⏰ משימה מתוזמנת בעוד **{delay_minutes} דקות**: `{task[:80]}`"
    )
    await asyncio.sleep(delay_minutes * 60)
    result = await post_json(GATEWAY_URL, {
        "user_id": str(interaction.user.id),
        "message": task,
        "username": interaction.user.display_name,
    })
    embed = agent_embed("main", result.get("response", "שגיאה"), interaction.user.display_name)
    try:
        await interaction.user.send(f"⏰ משימה מתוזמנת הסתיימה!", embed=embed)
    except Exception:
        pass


@tree.command(name="help", description="📖 עזרה ורשימת פקודות", guild=discord.Object(id=GUILD_ID))
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 OpenClaw v2.0 — עזרה",
        description="מערכת AI מרובת סוכנים עם Webhook Personas, Modals, ו-Context Menus",
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="🤖 AI סוכנים", value="`/main` `/coder` `/research` `/analyze`", inline=False)
    embed.add_field(name="🧭 Multi-Agent", value="`/orchestrate` `/debate` `/swarm`", inline=False)
    embed.add_field(name="🔍 כלים", value="`/search` `/run` `/memory` `/recall` `/store-memory`", inline=False)
    embed.add_field(name="📦 GitHub", value="`/github` `/github-prs` `/github-commits`", inline=False)
    embed.add_field(name="📓 Notion", value="`/notion-add` `/notion-list` `/notion-search`", inline=False)
    embed.add_field(name="🎯 ClawHub", value="`/clawhub` `/skill-top`", inline=False)
    embed.add_field(name="📋 מנהל", value="`/schedule` `/help`", inline=False)
    embed.add_field(
        name="🖱️ Context Menus (קליק ימני על הודעה)",
        value="• 🔍 Analyze Message\n• 🌐 Translate\n• 📝 Summarize\n• 💡 Explain Code",
        inline=False
    )
    embed.add_field(
        name="📺 ערוצים",
        value=f"• `#{TERMINAL_CHANNEL_NAME}` — פקודות shell\n• `#{AI_ADMIN_CHANNEL_NAME}` — ניהול\n• `#{KNOWLEDGE_CHANNEL_NAME}` — מחקר\n• `#{CLAWHUB_CHANNEL_NAME}` — כישורים",
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── Channel Handlers ─────────────────────────────────────────────────────────

async def handle_terminal_channel(message: discord.Message):
    """#terminal: run code blocks or analyze commands."""
    content = message.content.strip()
    code_match = content
    # Extract code block if present
    if "```" in content:
        parts = content.split("```")
        if len(parts) >= 3:
            lang_and_code = parts[1].strip()
            lines = lang_and_code.split("\n")
            code_match = "\n".join(lines[1:] if lines[0].strip().isalpha() else lines)

    async with message.channel.typing():
        result = await post_json(CODE_URL, {"code": code_match})
        success = result.get("success", False)
        output = result.get("output", "")
        color = 0x57F287 if success else 0xED4245
        embed = discord.Embed(
            title="✅ Output" if success else "❌ Error",
            description=f"```\n{truncate(output, 1900)}\n```",
            color=color,
            timestamp=datetime.utcnow()
        )
        await message.reply(embed=embed)


async def handle_ai_admin_channel(message: discord.Message):
    """#ai-admin: admin AI commands, memory management."""
    content = message.content.strip().lower()
    uid = str(message.author.id)

    if content.startswith("!reset"):
        async with message.channel.typing():
            await get_json(f"{MEMORY_URL}/{uid}")
            await message.reply("✅ זיכרון אופס.")
        return

    if content.startswith("!stats"):
        async with message.channel.typing():
            mem = await get_json(f"{MEMORY_URL}/{uid}")
            embed = discord.Embed(title="📊 Stats", color=0x5865F2)
            embed.add_field(name="בקשות", value=str(mem.get("request_count", 0)), inline=True)
            embed.add_field(name="סוכן מועדף", value=mem.get("favorite_agent", "none"), inline=True)
            await message.reply(embed=embed)
        return

    # Default: chat with main agent
    async with message.channel.typing():
        result = await post_json(GATEWAY_URL, {
            "user_id": uid,
            "message": message.content,
            "username": message.author.display_name,
        })
        embed = agent_embed("main", result.get("response", "שגיאה"),
                            message.author.display_name, result.get("model", ""), result.get("duration", 0))
        await message.reply(embed=embed)


async def handle_knowledge_channel(message: discord.Message):
    """#knowledge: research and deep information."""
    async with message.channel.typing():
        result = await post_json(GATEWAY_URL, {
            "user_id": str(message.author.id),
            "message": message.content,
            "username": message.author.display_name,
            "agent": "research",
        })
        embed = agent_embed("research", result.get("response", "שגיאה"),
                            message.author.display_name, result.get("model", ""), result.get("duration", 0))
        await message.reply(embed=embed)


async def handle_clawhub_channel(message: discord.Message):
    """#clawhub: skill-based responses."""
    content = message.content.strip()
    # Detect which skill to use from message content
    agent = "main"
    for skill_id, skill_he, _ in ALL_SKILLS:
        if skill_he in content or skill_id.lower() in content.lower():
            if skill_id in ("code", "debug", "refactor"):
                agent = "coder"
            elif skill_id in ("research", "data", "math"):
                agent = "research"
            elif skill_id in ("analyze", "plan", "security"):
                agent = "analyze"
            break

    async with message.channel.typing():
        result = await post_json(GATEWAY_URL, {
            "user_id": str(message.author.id),
            "message": content,
            "username": message.author.display_name,
            "agent": agent,
        })
        embed = agent_embed(agent, result.get("response", "שגיאה"),
                            message.author.display_name, result.get("model", ""), result.get("duration", 0))
        await message.reply(embed=embed)


# ─── Events ───────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} | {bot.user.id}")
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} commands to guild {GUILD_ID}")
    except Exception as e:
        print(f"❌ Sync error: {e}")

    # Status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🧠 OpenClaw v2.0 | /help"
        )
    )

    # Log startup
    await asyncio.sleep(2)
    await log_to_discord(bot, "🚀 OpenClaw v2.0 started — 22 commands synced")


async def _chat_reply(message: discord.Message, content: str, agent: str = "main", task_type: str = "default"):
    """
    Core chat reply — sends thinking indicator, calls gateway, posts VISIBLE response.
    Context is maintained per user (persistent across messages).
    """
    uid = str(message.author.id)
    async with message.channel.typing():
        try:
            result = await post_json(GATEWAY_URL, {
                "user_id": uid,
                "message": content,
                "username": message.author.display_name,
                "agent": agent,
                "task_type": task_type,
                "channel_id": str(message.channel.id),
            }, timeout=60)
        except Exception as e:
            await message.reply(f"❌ שגיאה: {e}")
            return

        # ── הזה הוא ה-FRONT ── התשובה הגלויה והמרכזית
        embed = agent_embed(
            agent,
            result.get("response", "שגיאה"),
            message.author.display_name,
            result.get("model", ""),
            result.get("duration", 0),
        )
        view = ResponseView(content, uid, message.author.display_name, agent)
        await message.reply(embed=embed, view=view)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content_raw = message.content.strip()
    if not content_raw:
        return

    channel_name = getattr(message.channel, "name", "")

    # ── DMs ──────────────────────────────────────────────────────────────────
    if isinstance(message.channel, discord.DMChannel):
        await _chat_reply(message, content_raw, "main")
        return

    # ── ערוץ #terminal ───────────────────────────────────────────────────────
    if channel_name == TERMINAL_CHANNEL_NAME:
        await handle_terminal_channel(message)
        return

    # ── ערוץ #knowledge ──────────────────────────────────────────────────────
    if channel_name == KNOWLEDGE_CHANNEL_NAME:
        await _chat_reply(message, content_raw, "research")
        return

    # ── ערוץ #clawhub ────────────────────────────────────────────────────────
    if channel_name == CLAWHUB_CHANNEL_NAME:
        await handle_clawhub_channel(message)
        return

    # ── ערוץ #ai-admin ───────────────────────────────────────────────────────
    if channel_name == AI_ADMIN_CHANNEL_NAME:
        # admin commands
        lower = content_raw.lower()
        if lower.startswith("!reset"):
            import aiohttp as _aiohttp
            async with _aiohttp.ClientSession() as s:
                await s.delete(f"{MEMORY_URL}/{message.author.id}")
            await message.reply("✅ זיכרון אופס.")
            return
        if lower.startswith("!stats"):
            mem = await get_json(f"{MEMORY_URL}/{message.author.id}")
            embed = discord.Embed(title="📊 Stats", color=0x5865F2)
            embed.add_field(name="בקשות", value=str(mem.get("request_count", 0)), inline=True)
            embed.add_field(name="סוכן מועדף", value=mem.get("favorite_agent", "none"), inline=True)
            embed.add_field(name="זמן ממוצע", value=f"{mem.get('avg_duration', 0)}s", inline=True)
            await message.reply(embed=embed)
            return
        # fallthrough → main agent
        await _chat_reply(message, content_raw, "main")
        return

    # ── כל שאר הערוצים: עם תיוג / ריפליי — תמיד עונה ────────────────────────
    is_mention = bot.user in message.mentions
    is_reply_to_bot = (
        message.reference is not None
        and message.reference.resolved is not None
        and getattr(message.reference.resolved, "author", None) == bot.user
    )
    # הסר את התיוג מהטקסט אם קיים
    clean = content_raw.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    if not clean:
        clean = content_raw

    if is_mention or is_reply_to_bot:
        await _chat_reply(message, clean, "main")
        return

    # ── ברירת מחדל — ANY message in ANY channel → main agent ─────────────────
    # (ללא צורך בתיוג — הבוט עונה לכל הודעה)
    await _chat_reply(message, content_raw, "main")

    # ── process prefix commands (! commands) ─────────────────────────────────
    await bot.process_commands(message)




@bot.event
async def on_command_error(ctx, error):
    pass  # Suppress prefix command errors


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = f"❌ שגיאה: {str(error)[:200]}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

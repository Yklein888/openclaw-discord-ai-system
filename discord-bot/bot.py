import discord
from discord import app_commands
import aiohttp
import httpx
import subprocess
import logging
import asyncio
import json as _json
import json as _json2
import time as _time
from datetime import datetime
import os
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = 1492111780934320138
ADMIN_ID = "1488848655594295366"
GATEWAY_URL = "http://127.0.0.1:4001/chat"
MEMORY_URL  = "http://127.0.0.1:4001/memory"
SEARCH_URL  = "http://127.0.0.1:4001/search"
CODE_URL    = "http://127.0.0.1:4001/run-code"
GITHUB_URL  = "http://127.0.0.1:4001/github"
NOTION_URL  = "http://127.0.0.1:4001/notion"
VISION_URL        = "http://127.0.0.1:4001/vision"
RECALL_URL        = "http://127.0.0.1:4001/recall"
STORE_MEMORY_URL  = "http://127.0.0.1:4001/store-memory"
SWARM_URL         = "http://127.0.0.1:4001/swarm"
ORCHESTRATE_URL   = "http://127.0.0.1:4001/orchestrate"
STREAM_URL        = "http://127.0.0.1:4001/chat/stream"  # Phase 17: streaming
CLAWHUB_URL       = "https://clawhub.ai/skills"
CLAWHUB_API       = "https://clawhub.ai"
CLAWHUB_CHANNEL_NAME   = "clawhub"
ADMIN_CHANNEL_NAME     = "admin"
KNOWLEDGE_CHANNEL_NAME = "knowledge"   # drop files/text → auto-embed → RAG
TERMINAL_CHANNEL_NAME  = "terminal"    # every message = shell command on server
AI_ADMIN_CHANNEL_NAME  = "ai-admin"   # natural language → AI understands → runs on server
LOGS_CHANNEL_ID = 1493685126285234240
STATUS_CHANNEL_ID = 1493685127786663959

AGENT_CONFIG = {
    "main":     {"color": 0x5865F2, "emoji": "\U0001f916", "system": "\u05d0\u05ea\u05d4 \u05e2\u05d5\u05d6\u05e8 AI \u05d7\u05db\u05dd. \u05e2\u05e0\u05d4 \u05ea\u05de\u05d9\u05d3 \u05d1\u05e2\u05d1\u05e8\u05d9\u05ea."},
    "coder":    {"color": 0x57F287, "emoji": "\U0001f4bb", "system": "\u05d0\u05ea\u05d4 \u05de\u05d5\u05de\u05d7\u05d4 \u05e7\u05d5\u05d3. \u05e2\u05d5\u05e0\u05d4 \u05e8\u05e7 \u05d1\u05e7\u05d5\u05d3 \u05e0\u05e7\u05d9 \u05e2\u05dd \u05d4\u05e1\u05d1\u05e8\u05d9\u05dd \u05e7\u05e6\u05e8\u05d9\u05dd."},
    "research": {"color": 0xFEE75C, "emoji": "\U0001f50d", "system": "\u05d0\u05ea\u05d4 \u05d7\u05d5\u05e7\u05e8 \u05de\u05d5\u05de\u05d7\u05d4. \u05ea\u05df \u05ea\u05e9\u05d5\u05d1\u05d5\u05ea \u05de\u05e4\u05d5\u05e8\u05d8\u05d5\u05ea \u05e2\u05dd \u05de\u05e7\u05d5\u05e8\u05d5\u05ea."},
    "analyze":  {"color": 0xED4245, "emoji": "\U0001f4ca", "system": "\u05d0\u05ea\u05d4 \u05de\u05e0\u05ea\u05d7 \u05e0\u05ea\u05d5\u05e0\u05d9\u05dd. \u05ea\u05e0\u05ea\u05d7 \u05dc\u05e2\u05d5\u05de\u05e7 \u05d5\u05ea\u05df \u05ea\u05d5\u05d1\u05e0\u05d5\u05ea."},
}

# Stats tracking
stats = {"total": 0, "by_agent": {}, "total_duration": 0.0, "models": {}}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
GUILD = discord.Object(id=GUILD_ID)

# ── Scheduler (Phase 16) ────────────────────────────────────────────────────
scheduler = AsyncIOScheduler() if HAS_SCHEDULER else None

import redis as _redis
_r = _redis.Redis(host="localhost", port=6379, decode_responses=True)

def _sched_key(uid: str, sid: int) -> str:
    return f"sched:{uid}:{sid}"

def save_schedule(uid: str, sid: int, channel_id: int, task: str, minutes: int):
    _r.set(_sched_key(uid, sid), _json.dumps(
        {"uid": uid, "sid": sid, "channel_id": channel_id,
         "task": task, "minutes": minutes}
    ))

def delete_schedule_data(uid: str, sid: int):
    _r.delete(_sched_key(uid, sid))

def list_schedules(uid: str) -> list:
    keys = _r.keys(f"sched:{uid}:*")
    result = []
    for k in keys:
        raw = _r.get(k)
        if raw:
            try:
                result.append(_json.loads(raw))
            except Exception:
                pass
    return sorted(result, key=lambda x: x["sid"])


# --- PHASE 4: Buttons View ---
class AgentView(discord.ui.View):
    def __init__(self, user_id: str, username: str, agent: str, original_message: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.username = username
        self.agent = agent
        self.original_message = original_message

    @discord.ui.button(label="Ask Again", emoji="\U0001f504", style=discord.ButtonStyle.primary)
    async def ask_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        data = await ask_gateway(self.user_id, self.username, self.original_message, self.agent)
        embed = make_embed(self.agent, data["response"], data.get("model", "?"), data.get("duration", 0))
        await interaction.followup.send(embed=embed, view=AgentView(self.user_id, self.username, self.agent, self.original_message))

    @discord.ui.button(label="Delete", emoji="\U0001f5d1", style=discord.ButtonStyle.danger)
    async def delete_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


async def ask_gateway(user_id: str, username: str, message: str, agent: str, image_url: str = None) -> dict:
    cfg = AGENT_CONFIG[agent]
    payload = {
        "user_id": f"{agent}:{user_id}",
        "username": username,
        "message": message,
        "system_prompt": cfg["system"],
        "image_url": image_url,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(GATEWAY_URL, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            return await resp.json()


# ─── Phase 17: Streaming ─────────────────────────────────────────────────────

async def ask_gateway_stream(
    interaction: discord.Interaction,
    user_id: str,
    username: str,
    message: str,
    agent: str,
    image_url: str = None,
    channel_id: str = None
) -> None:
    """
    Streams from gateway /chat/stream and progressively edits Discord embed.
    Creates a typewriter effect — each chunk arrives and the message updates.
    """
    cfg = AGENT_CONFIG[agent]
    payload = {
        "user_id": f"{agent}:{user_id}",
        "username": username,
        "message": message,
        "agent": agent,
        "channel_id": channel_id or str(interaction.channel_id),
        "image_url": image_url,
    }

    # Initial "thinking" embed
    init_embed = discord.Embed(
        title=f"{cfg['emoji']} {agent.capitalize()}",
        description="⏳ חושב...",
        color=cfg["color"]
    )
    msg = await interaction.followup.send(embed=init_embed)

    accumulated = ""
    last_edit   = _time.time()
    model_used  = "?"
    duration    = 0

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            async with client.stream("POST", STREAM_URL, json=payload) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    try:
                        chunk_data = _json2.loads(raw)
                    except Exception:
                        continue

                    if chunk_data.get("done"):
                        model_used = chunk_data.get("model", model_used)
                        duration   = chunk_data.get("duration", 0)
                        break
                    if chunk_data.get("error"):
                        accumulated = accumulated or chunk_data["error"]
                        break

                    delta = chunk_data.get("content", "")
                    if not delta:
                        continue
                    accumulated += delta
                    if chunk_data.get("model"):
                        model_used = chunk_data["model"]

                    # Update Discord message every 0.8s to avoid rate limits
                    now = _time.time()
                    if now - last_edit >= 0.8:
                        upd_embed = discord.Embed(
                            title=f"{cfg['emoji']} {agent.capitalize()}",
                            description=(accumulated[:3900] + "▌") if len(accumulated) <= 3900 else accumulated[:3900] + "...\n▌",
                            color=cfg["color"]
                        )
                        try:
                            await msg.edit(embed=upd_embed)
                            last_edit = now
                        except Exception:
                            pass

        # Final edit — complete response + footer + buttons
        final_embed = discord.Embed(
            title=f"{cfg['emoji']} {agent.capitalize()}",
            description=accumulated[:4000] if accumulated else "❌ אין תגובה",
            color=cfg["color"]
        )
        final_embed.set_footer(text=f"Model: {model_used} | ⏱ {duration}s")
        view = AgentView(user_id, username, agent, message)
        await msg.edit(embed=final_embed, view=view)
        await log_request(username, agent, duration, model_used)

        # Thread for long responses
        if len(accumulated) > 2000 and hasattr(interaction.channel, 'create_thread'):
            try:
                thread = await interaction.channel.create_thread(
                    name=f"{agent}: {message[:50]}",
                    auto_archive_duration=60
                )
                # Split into chunks if needed
                chunks = [accumulated[i:i+1900] for i in range(0, len(accumulated), 1900)]
                for chunk in chunks:
                    await thread.send(chunk)
            except Exception:
                pass

    except Exception as e:
        err_embed = discord.Embed(
            title="❌ שגיאת Streaming",
            description=str(e)[:500],
            color=0xED4245
        )
        try:
            await msg.edit(embed=err_embed)
        except Exception:
            pass


def make_embed(agent: str, reply: str, model: str, duration: float) -> discord.Embed:
    cfg = AGENT_CONFIG[agent]
    embed = discord.Embed(
        title=f"{cfg['emoji']} {agent.capitalize()}",
        description=reply[:4000],
        color=cfg["color"]
    )
    embed.set_footer(text=f"Model: {model} | \u23f1 {duration}s")
    return embed


async def log_request(username: str, agent: str, duration: float, model: str):
    """PHASE 5: Send log to #logs channel"""
    stats["total"] += 1
    stats["by_agent"][agent] = stats["by_agent"].get(agent, 0) + 1
    stats["total_duration"] += duration
    stats["models"][model] = stats["models"].get(model, 0) + 1

    channel = client.get_channel(LOGS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(color=0x2F3136)
        embed.add_field(name="User", value=username, inline=True)
        embed.add_field(name="Agent", value=f"/{agent}", inline=True)
        embed.add_field(name="Duration", value=f"{duration}s", inline=True)
        embed.add_field(name="Model", value=model, inline=True)
        embed.set_footer(text=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
        await channel.send(embed=embed)


async def send_hourly_status():
    """PHASE 5: Send hourly status to #status channel"""
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(3600)
        channel = client.get_channel(STATUS_CHANNEL_ID)
        if channel and stats["total"] > 0:
            avg = round(stats["total_duration"] / stats["total"], 2) if stats["total"] else 0
            top_model = max(stats["models"], key=stats["models"].get) if stats["models"] else "N/A"
            embed = discord.Embed(title="\U0001f4ca Hourly Status", color=0x00FF99)
            embed.add_field(name="Total Requests", value=str(stats["total"]), inline=True)
            embed.add_field(name="Avg Duration", value=f"{avg}s", inline=True)
            embed.add_field(name="Top Model", value=top_model, inline=True)
            for agent, count in stats["by_agent"].items():
                embed.add_field(name=f"/{agent}", value=str(count), inline=True)
            embed.set_footer(text=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
            await channel.send(embed=embed)
            # Reset hourly stats
            stats.update({"total": 0, "by_agent": {}, "total_duration": 0.0, "models": {}})


@client.event
async def on_ready():
    # Do NOT use copy_global_to — it leaks commands into DMs and causes OpenAI errors
    synced = await tree.sync(guild=GUILD)
    logger.info(f"Logged in as {client.user} | Synced {len(synced)} commands")
    client.loop.create_task(send_hourly_status())

    # ── Start APScheduler + reload persisted schedules ─────────────────────
    if scheduler:
        scheduler.start()
        # Reload all saved schedules from Redis
        all_sched_keys = _r.keys("sched:*:*")
        loaded = 0
        for key in all_sched_keys:
            if key.startswith("sched:cnt:"):
                continue
            raw = _r.get(key)
            if not raw:
                continue
            try:
                s = _json.loads(raw)
                uid, sid, channel_id = str(s["uid"]), int(s["sid"]), int(s["channel_id"])
                task, minutes = s["task"], int(s["minutes"])
                job_id = f"sched_{uid}_{sid}"

                async def _fire(u=uid, t=task, m=minutes, ch=channel_id, s_id=sid):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                GATEWAY_URL,
                                json={"user_id": f"sched:{u}", "username": "scheduler",
                                      "message": t, "system_prompt": None},
                                timeout=aiohttp.ClientTimeout(total=60)
                            ) as resp:
                                data = await resp.json()
                        reply = data.get("response", "שגיאה")
                        model = data.get("model", "?")
                        channel = client.get_channel(ch)
                        if channel:
                            embed = discord.Embed(
                                title=f"⏰ משימה מתוזמנת: {t[:60]}",
                                description=reply[:3800],
                                color=0x00FF99
                            )
                            embed.set_footer(text=f"Model: {model} | כל {m} דקות | #{s_id}")
                            await channel.send(embed=embed)
                    except Exception as ex:
                        logger.error(f"Schedule fire error: {ex}")

                scheduler.add_job(
                    _fire,
                    IntervalTrigger(minutes=minutes),
                    id=job_id,
                    replace_existing=True
                )
                loaded += 1
            except Exception as ex:
                logger.warning(f"Failed to reload schedule {key}: {ex}")
        logger.info(f"Reloaded {loaded} scheduled tasks from Redis")


async def handle_agent_command(
    interaction: discord.Interaction,
    message: str,
    agent: str,
    image: discord.Attachment = None
):
    """Handle agent slash commands with streaming + optional image support."""
    await interaction.response.defer()
    image_url = None
    if image and any(image.filename.lower().endswith(e) for e in IMAGE_EXTS):
        image_url = image.url

    # Use streaming for typewriter effect
    await ask_gateway_stream(
        interaction,
        str(interaction.user.id),
        interaction.user.name,
        message,
        agent,
        image_url=image_url,
        channel_id=str(interaction.channel_id)
    )


@tree.command(name="main", description="🤖 שאל את ה-AI (תומך תמונות!)", guild=GUILD)
@app_commands.describe(message="ההודעה שלך", image="תמונה לניתוח (אופציונלי)")
async def main_cmd(interaction: discord.Interaction, message: str, image: discord.Attachment = None):
    await handle_agent_command(interaction, message, "main", image)

@tree.command(name="coder", description="💻 עזרה בקוד (תומך screenshots!)", guild=GUILD)
@app_commands.describe(message="שאלת קוד", image="צילום מסך של קוד/שגיאה (אופציונלי)")
async def coder_cmd(interaction: discord.Interaction, message: str, image: discord.Attachment = None):
    await handle_agent_command(interaction, message, "coder", image)

@tree.command(name="research", description="🔍 מחקר מעמיק (תומך תמונות!)", guild=GUILD)
@app_commands.describe(message="נושא לחקירה", image="תמונה לניתוח (אופציונלי)")
async def research_cmd(interaction: discord.Interaction, message: str, image: discord.Attachment = None):
    await handle_agent_command(interaction, message, "research", image)

@tree.command(name="analyze", description="📊 ניתוח נתונים (תומך גרפים/תמונות!)", guild=GUILD)
@app_commands.describe(message="מה לנתח?", image="גרף/תמונה לניתוח (אופציונלי)")
async def analyze_cmd(interaction: discord.Interaction, message: str, image: discord.Attachment = None):
    await handle_agent_command(interaction, message, "analyze", image)


# ─── Phase 17: VISION slash command ──────────────────────────────────────────

@tree.command(name="vision", description="👁️ שלח תמונה לניתוח Gemini Vision", guild=GUILD)
@app_commands.describe(
    image="התמונה לניתוח (PNG/JPG/GIF/WebP)",
    question="שאלה על התמונה (אופציונלי — ברירת מחדל: תיאור כללי)"
)
async def vision_cmd(interaction: discord.Interaction, image: discord.Attachment, question: str = ""):
    await interaction.response.defer()
    if not any(image.filename.lower().endswith(e) for e in IMAGE_EXTS):
        await interaction.followup.send("❌ קובץ לא נתמך. שלח PNG / JPG / GIF / WebP.")
        return
    try:
        payload = {
            "user_id": str(interaction.user.id),
            "username": interaction.user.name,
            "image_url": image.url,
            "text": question or "תאר את התמונה הזו בפירוט. ציין כל פרט חשוב."
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(VISION_URL, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=45)) as resp:
                data = await resp.json()

        reply    = data.get("response", "שגיאה בעיבוד התמונה")
        model    = data.get("model", "gemini-flash")
        duration = data.get("duration", 0)

        embed = discord.Embed(
            title="👁️ Vision Analysis",
            description=reply[:4000],
            color=0x9B59B6
        )
        embed.set_thumbnail(url=image.url)
        embed.set_footer(text=f"Model: {model} | ⏱ {duration}s | {image.filename}")
        await interaction.followup.send(embed=embed)
        await log_request(interaction.user.name, "vision", duration, model)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאת Vision: {e}")

# ─── PHASE 12: GITHUB ────────────────────────────────────────────────────────

@tree.command(name="github", description="🐙 מידע על GitHub repo", guild=GUILD)
async def github_cmd(interaction: discord.Interaction, repo: str):
    """repo format: owner/repo  e.g.  yitzi/my-project"""
    await interaction.response.defer()
    try:
        parts = repo.strip().split("/")
        if len(parts) != 2:
            await interaction.followup.send("❌ פורמט לא תקין. השתמש בצורה: `owner/repo`")
            return
        owner, repo_name = parts
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GITHUB_URL}/repo/{owner}/{repo_name}",
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()

        if "error" in data:
            await interaction.followup.send(f"❌ {data['error']}")
            return

        embed = discord.Embed(
            title=f"🐙 {data['name']}",
            description=data.get("description") or "אין תיאור",
            url=data.get("url", ""),
            color=0x24292E
        )
        embed.add_field(name="⭐ Stars",      value=str(data["stars"]),        inline=True)
        embed.add_field(name="🍴 Forks",      value=str(data["forks"]),        inline=True)
        embed.add_field(name="🐛 Issues",     value=str(data["open_issues"]),  inline=True)
        embed.add_field(name="💻 Language",   value=data.get("language","N/A"),inline=True)
        embed.add_field(name="🌿 Branch",     value=data["default_branch"],    inline=True)
        embed.add_field(name="🔒 Private",    value="כן" if data["private"] else "לא", inline=True)
        embed.set_footer(text=f"עודכן: {data.get('updated_at','')[:10]}")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


@tree.command(name="github-prs", description="🔀 Pull Requests פתוחים", guild=GUILD)
async def github_prs_cmd(interaction: discord.Interaction, repo: str, state: str = "open"):
    await interaction.response.defer()
    try:
        parts = repo.strip().split("/")
        if len(parts) != 2:
            await interaction.followup.send("❌ פורמט: `owner/repo`")
            return
        owner, repo_name = parts
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GITHUB_URL}/prs/{owner}/{repo_name}",
                                   params={"state": state},
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()

        if "error" in data:
            await interaction.followup.send(f"❌ {data['error']}")
            return

        prs = data.get("prs", [])
        embed = discord.Embed(
            title=f"🔀 PRs — {data['repo']} ({state})",
            description=f"נמצאו {data['count']} pull requests",
            color=0x6F42C1
        )
        for pr in prs[:8]:
            embed.add_field(
                name=f"#{pr['number']} {pr['title'][:55]}",
                value=f"👤 {pr['user']} | 📅 {pr['created_at']} | [🔗 פתח]({pr['url']})",
                inline=False
            )
        if not prs:
            embed.description = f"אין pull requests {state}"
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


@tree.command(name="github-commits", description="📜 Commits אחרונים ב-repo", guild=GUILD)
async def github_commits_cmd(interaction: discord.Interaction, repo: str):
    await interaction.response.defer()
    try:
        parts = repo.strip().split("/")
        if len(parts) != 2:
            await interaction.followup.send("❌ פורמט: `owner/repo`")
            return
        owner, repo_name = parts
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GITHUB_URL}/commits/{owner}/{repo_name}",
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()

        if "error" in data:
            await interaction.followup.send(f"❌ {data['error']}")
            return

        embed = discord.Embed(title=f"📜 Commits — {data['repo']}", color=0x0D1117)
        for c in data.get("commits", []):
            embed.add_field(
                name=f"`{c['sha']}` {c['message'][:60]}",
                value=f"👤 {c['author']} | 📅 {c['date']} | [🔗 פתח]({c['url']})",
                inline=False
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


# ─── PHASE 13: NOTION ────────────────────────────────────────────────────────

@tree.command(name="notion-add", description="📝 הוסף הערה ל-Notion", guild=GUILD)
async def notion_add_cmd(interaction: discord.Interaction, text: str, title: str = None):
    await interaction.response.defer(ephemeral=True)
    try:
        payload = {"text": text}
        if title:
            payload["title"] = title
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{NOTION_URL}/add", json=payload,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()

        if "error" in data:
            await interaction.followup.send(f"❌ Notion error: {data['error']}")
            return

        embed = discord.Embed(title="📝 נוסף ל-Notion!", color=0x000000)
        embed.add_field(name="תוכן", value=text[:200], inline=False)
        if data.get("url"):
            embed.add_field(name="🔗 קישור", value=data["url"], inline=False)
        embed.set_footer(text=f"Page ID: {data.get('page_id','')[:8]}...")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


@tree.command(name="notion-list", description="📋 דפים אחרונים ב-Notion", guild=GUILD)
async def notion_list_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{NOTION_URL}/list",
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()

        if "error" in data:
            await interaction.followup.send(f"❌ Notion error: {data['error']}")
            return

        pages = data.get("pages", [])
        embed = discord.Embed(
            title="📋 Notion — דפים אחרונים",
            description=f"נמצאו {data['count']} דפים",
            color=0x000000
        )
        for p in pages:
            title_text = p['title'][:55] or "(ללא כותרת)"
            link = f"[🔗 פתח]({p['url']})" if p.get("url") else ""
            embed.add_field(
                name=title_text,
                value=f"📅 {p.get('edited','')[:10]} {link}",
                inline=False
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


@tree.command(name="notion-search", description="🔍 חפש ב-Notion", guild=GUILD)
async def notion_search_cmd(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{NOTION_URL}/search", params={"q": query},
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()

        if "error" in data:
            await interaction.followup.send(f"❌ {data['error']}")
            return

        results = data.get("results", [])
        embed = discord.Embed(
            title=f"🔍 Notion Search: {query[:40]}",
            description=f"{data['count']} תוצאות",
            color=0x000000
        )
        for p in results:
            link = f"[🔗]({p['url']})" if p.get("url") else ""
            embed.add_field(
                name=p["title"][:60] or "(ללא כותרת)",
                value=f"`{p['type']}` {link}",
                inline=False
            )
        if not results:
            embed.description = "לא נמצאו תוצאות"
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


# ─── CLAWHUB ─────────────────────────────────────────────────────────────────

@tree.command(name="clawhub", description="🔌 חפש skills/plugins ב-ClawHub", guild=GUILD)
async def clawhub_cmd(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    skills = await clawhub_search(query)
    embed  = make_clawhub_embed(query, skills)

    # If no API results, enrich with AI description via gateway
    if not skills:
        try:
            ai_data = await ask_gateway(
                str(interaction.user.id), interaction.user.name,
                f"תאר בקצרה (3-4 שורות) את הskill הבא מ-ClawHub: '{query}'. "
                f"אם אתה לא מכיר אותו, תסביר מה skill כזה יכול לעשות לפי השם.",
                "research"
            )
            embed.add_field(name="🤖 AI תיאור", value=ai_data.get("response","")[:400], inline=False)
        except Exception:
            pass

    embed.set_footer(text=f"53,848 skills ב-ClawHub | npx clawhub@latest install <slug>")
    await interaction.followup.send(embed=embed)


ALL_SKILLS = [
    # (slug, author, downloads, stars, description)
    ("self-improving-agent",    "pskoett",            "388k", "3.2k", "לומד מטעויות ומשתפר — continuous improvement"),
    ("skill-vetter",            "spclaudehome",       "207k", "899",  "בודק אבטחה לפני כל התקנת skill"),
    ("ontology",                "oswalpalash",        "164k", "529",  "knowledge graph לזיכרון מובנה של agent"),
    ("self-improving",          "ivangdavila",        "162k", "958",  "self-reflection + self-learning + זיכרון"),
    ("github",                  "steipete",           "157k", "511",  "GitHub CLI — issues, PRs, runs, API"),
    ("gog",                     "steipete",           "155k", "836",  "Google Workspace — Gmail, Calendar, Drive, Docs"),
    ("proactive-agent",         "halthelobster",      "143k", "706",  "AI proactive עם WAL Protocol + Autonomous Crons"),
    ("weather",                 "steipete",           "134k", "355",  "מזג אוויר ותחזיות — ללא API key"),
    ("multi-search-engine",     "gpyangyoujun",       "118k", "556",  "16 מנועי חיפוש (Google, Reddit, arXiv...)"),
    ("polymarket-trade",        "joelchance",         "112k", "72",   "Polymarket — prediction markets ואחוזים"),
    ("nano-pdf",                "steipete",           "90.4k","218",  "עריכת PDF בשפה טבעית"),
    ("humanizer",               "biostartechnology",  "90.1k","533",  "מסיר סימני AI writing מטקסטים"),
    ("agent-browser-clawdbot",  "matrixy",            "86.7k","315",  "Browser automation headless לagents"),
    ("nano-banana-pro",         "steipete",           "85.8k","337",  "יצירת/עריכת תמונות עם Gemini 3 Pro"),
    ("openclaw-tavily-search",  "jacky1n7",           "81.1k","214",  "Web search via Tavily API"),
    ("obsidian",                "steipete",           "81k",  "324",  "Obsidian vault — plain Markdown notes"),
    ("admapix",                 "fly0pants",          "80.7k","237",  "Ad intelligence + app analytics"),
    ("baidu-search",            "ide-rea",            "78.4k","200",  "חיפוש Baidu AI Search Engine"),
    ("prismfy-search",          "uroboros1205",       "76.7k","24",   "10 מנועים — Google, Reddit, GitHub, HN..."),
    ("notion",                  "steipete",           "76.5k","228",  "Notion API — pages, databases, blocks"),
    ("auto-updater",            "maximeprades",       "72.5k","359",  "עדכון skills אוטומטי כל יום"),
    ("pollyreach",              "pollyreach",         "71.2k","16",   "מספר טלפון לagent — שיחות ויכולות"),
    ("skill-creator",           "chindden",           "70.3k","246",  "מדריך ליצירת skills משלך"),
    ("openai-whisper",          "steipete",           "69k",  "271",  "speech-to-text עם Whisper — ללא API key"),
    ("sonoscli",                "steipete",           "77.4k","47",   "שליטה ברמקולי Sonos"),
]

@tree.command(name="skill-top", description="🏆 Top 25 skills ב-ClawHub (2 עמודים)", guild=GUILD)
async def skill_top_cmd(interaction: discord.Interaction, page: int = 1):
    await interaction.response.defer()

    per_page = 13
    start = (page - 1) * per_page
    chunk = ALL_SKILLS[start:start + per_page]
    total_pages = (len(ALL_SKILLS) + per_page - 1) // per_page

    embed = discord.Embed(
        title=f"🏆 Top {len(ALL_SKILLS)} ClawHub Skills — עמוד {page}/{total_pages}",
        description="[🔗 clawhub.ai/skills](https://clawhub.ai/skills?sort=downloads)",
        color=0x7C3AED
    )
    for slug, author, dl, stars, desc in chunk:
        embed.add_field(
            name=f"📦 {slug}  ⬇️{dl} ⭐{stars}",
            value=f"{desc}\n`npx clawhub@latest install {slug}`",
            inline=False
        )
    embed.set_footer(text=f"עמוד {page}/{total_pages} | /skill-top page:2 לעמוד הבא")
    await interaction.followup.send(embed=embed)


# ─── PHASE 10: SEARCH ────────────────────────────────────────────────────────

@tree.command(name="search", description="🔎 חפש באינטרנט עם DuckDuckGo", guild=GUILD)
async def search_cmd(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SEARCH_URL, json={"query": query, "max_results": 5},
                                    timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()

        results = data.get("results", [])
        error   = data.get("error", "")
        duration = data.get("duration", 0)

        if error or not results:
            await interaction.followup.send(f"❌ לא נמצאו תוצאות: `{error or 'empty'}`")
            return

        embed = discord.Embed(
            title=f"🔎 תוצאות חיפוש: {query[:60]}",
            color=0xFEE75C
        )
        for i, r in enumerate(results, 1):
            title = r.get("title", "ללא כותרת")[:60]
            url   = r.get("url", "")
            body  = r.get("body", "")[:120]
            embed.add_field(
                name=f"{i}. {title}",
                value=f"{body}\n[🔗 קישור]({url})" if url else body,
                inline=False
            )
        embed.set_footer(text=f"⏱ {duration}s | DuckDuckGo")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאת חיפוש: {e}")


def clean_code(code: str) -> str:
    """Strip Discord markdown fences and fix escaped newlines."""
    import re
    code = code.strip()
    # Remove ```python ... ``` or ``` ... ``` fences
    code = re.sub(r'^```(?:python|py)?\s*\n?', '', code)
    code = re.sub(r'\n?```\s*$', '', code)
    code = code.strip()
    # Discord slash command args pass \n as literal \\n — convert back
    code = code.replace('\\n', '\n').replace('\\t', '\t')
    return code


@tree.command(name="run", description="⚙️ הרץ קוד Python", guild=GUILD)
async def run_cmd(interaction: discord.Interaction, code: str):
    await interaction.response.defer()
    try:
        code = clean_code(code)
        async with aiohttp.ClientSession() as session:
            async with session.post(CODE_URL, json={"code": code, "timeout": 10},
                                    timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.json()

        success  = data.get("success", False)
        output   = data.get("output", "")
        duration = data.get("duration", 0)
        exit_code = data.get("exit_code", "?")

        color = 0x57F287 if success else 0xED4245
        status = "✅ הצליח" if success else "❌ נכשל"

        embed = discord.Embed(title=f"⚙️ Python Runner — {status}", color=color)
        # Show the code
        code_display = code[:500] + ("..." if len(code) > 500 else "")
        embed.add_field(name="📝 קוד", value=f"```python\n{code_display}\n```", inline=False)
        # Show output
        output_display = output[:800] + ("..." if len(output) > 800 else "")
        embed.add_field(name="📤 פלט", value=f"```\n{output_display}\n```", inline=False)
        embed.set_footer(text=f"exit={exit_code} | ⏱ {duration}s | max 15s")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


@tree.command(name="memory", description="🧠 מה המערכת זוכרת עליך", guild=GUILD)
async def memory_cmd(interaction: discord.Interaction, reset: bool = False):
    uid = str(interaction.user.id)
    # Try all 4 agent namespaces to find data
    agent_ids = [f"{a}:{uid}" for a in AGENT_CONFIG.keys()]

    if reset:
        async with aiohttp.ClientSession() as session:
            for aid in agent_ids:
                await session.delete(f"{MEMORY_URL}/{aid}")
        embed = discord.Embed(title="🧠 זיכרון אופס", description="כל הנתונים שלך נמחקו ✅", color=0xED4245)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Aggregate memory across all agent namespaces
    total_requests = 0
    total_duration = 0.0
    total_tokens = 0
    total_context = 0
    agent_counts = {}
    lang = "he"
    username = interaction.user.display_name

    async with aiohttp.ClientSession() as session:
        for aid in agent_ids:
            async with session.get(f"{MEMORY_URL}/{aid}") as resp:
                if resp.status == 200:
                    d = await resp.json()
                    total_requests += d.get("request_count", 0)
                    total_duration += d.get("total_duration", 0)
                    total_tokens += d.get("total_tokens_est", 0)
                    total_context += d.get("context_messages", 0)
                    for agent, count in d.get("agent_counts", {}).items():
                        agent_counts[agent] = agent_counts.get(agent, 0) + count
                    if d.get("language"):
                        lang = d["language"]

    avg_dur = round(total_duration / total_requests, 2) if total_requests else 0
    fav_agent = max(agent_counts, key=agent_counts.get) if agent_counts else "none"
    lang_display = {"he": "🇮🇱 עברית", "en": "🇺🇸 English", "ar": "🇸🇦 Arabic"}.get(lang, lang)

    embed = discord.Embed(title=f"🧠 זיכרון – {username}", color=0x5865F2)
    embed.add_field(name="📊 סה״כ בקשות",    value=str(total_requests),    inline=True)
    embed.add_field(name="⭐ סוכן מועדף",    value=f"/{fav_agent}",         inline=True)
    embed.add_field(name="🌐 שפה מועדפת",    value=lang_display,            inline=True)
    embed.add_field(name="⏱ ממוצע זמן",      value=f"{avg_dur}s",           inline=True)
    embed.add_field(name="🔤 טוקנים (הערכה)", value=str(total_tokens),       inline=True)
    embed.add_field(name="💬 הודעות בזיכרון", value=str(total_context),      inline=True)

    if agent_counts:
        breakdown = " | ".join(f"/{a}: {c}" for a, c in agent_counts.items())
        embed.add_field(name="📈 שימוש לפי סוכן", value=breakdown, inline=False)

    embed.set_footer(text="כדי לאפס: /memory reset:True")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── PHASE 15: RECALL ────────────────────────────────────────────────────────

@tree.command(name="recall", description="🧠 חפש בזיכרון הארוך-טווח שלך", guild=GUILD)
async def recall_cmd(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id)
    try:
        # Search across all agent namespaces
        all_memories = []
        async with aiohttp.ClientSession() as session:
            for agent_prefix in ["main", "coder", "research", "analyze", "swarm"]:
                async with session.post(
                    RECALL_URL,
                    json={"user_id": f"{agent_prefix}:{uid}", "query": query, "top_k": 3},
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    data = await resp.json()
                    all_memories.extend(data.get("memories", []))

        # Sort by score desc
        all_memories.sort(key=lambda x: x["score"], reverse=True)
        top = all_memories[:6]

        embed = discord.Embed(
            title=f"🧠 Recall — {query[:50]}",
            description=f"נמצאו {len(top)} זיכרונות רלוונטיים" if top else "לא נמצאו זיכרונות רלוונטיים",
            color=0x5865F2
        )
        for i, m in enumerate(top, 1):
            ts = datetime.fromtimestamp(m.get("timestamp", 0)).strftime("%d/%m %H:%M") if m.get("timestamp") else "?"
            embed.add_field(
                name=f"{i}. [{m['agent']}] score={m['score']} | {ts}",
                value=m["text"][:300],
                inline=False
            )
        embed.set_footer(text="כדי לשמור זיכרון ידנית: /store-memory")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


@tree.command(name="store-memory", description="💾 שמור זיכרון ידנית לזיכרון הארוך", guild=GUILD)
async def store_memory_cmd(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                STORE_MEMORY_URL,
                json={"user_id": f"main:{uid}", "text": text, "agent": "manual"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
        embed = discord.Embed(title="💾 זיכרון נשמר!", color=0x57F287)
        embed.add_field(name="תוכן", value=text[:300], inline=False)
        embed.set_footer(text="הזיכרון יוזכר אוטומטית בשיחות עתידיות")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ שגיאה: {e}")


# ─── PHASE 16: SWARM ─────────────────────────────────────────────────────────

@tree.command(name="swarm", description="🤖 3 סוכנים במקביל: חוקר+מתכנת+מנתח", guild=GUILD)
async def swarm_cmd(interaction: discord.Interaction, task: str):
    await interaction.response.defer()
    uid  = str(interaction.user.id)
    uname = interaction.user.name

    # Send "thinking" message first since swarm takes ~20s
    thinking_embed = discord.Embed(
        title="🤖 Swarm מופעל...",
        description=(
            f"**משימה:** {task[:200]}\n\n"
            "⏳ מפעיל 3 סוכנים במקביל:\n"
            "🔍 **Researcher** — חוקר עובדות\n"
            "💻 **Coder** — בונה פתרון טכני\n"
            "📊 **Analyzer** — מנתח יתרונות/חסרונות\n\n"
            "_זה לוקח ~20-30 שניות..._"
        ),
        color=0xFEE75C
    )
    await interaction.followup.send(embed=thinking_embed)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SWARM_URL,
                json={"user_id": f"swarm:{uid}", "username": uname, "task": task},
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                data = await resp.json()

        agents   = data.get("agents", {})
        synthesis = data.get("synthesis", "שגיאה")
        duration  = data.get("duration", 0)

        # Main embed: synthesis
        embed = discord.Embed(
            title=f"🤖 Swarm — {task[:60]}",
            description=synthesis[:3800],
            color=0x5865F2
        )
        embed.set_footer(text=f"⏱ {duration}s | researcher:{agents.get('researcher',{}).get('model','?')} | coder:{agents.get('coder',{}).get('model','?')} | analyzer:{agents.get('analyzer',{}).get('model','?')}")
        await interaction.channel.send(embed=embed)

        # Thread with individual agent outputs
        if hasattr(interaction.channel, 'create_thread'):
            try:
                thread = await interaction.channel.create_thread(
                    name=f"Swarm: {task[:50]}",
                    auto_archive_duration=60
                )
                for role, info in agents.items():
                    role_emojis = {"researcher": "🔍", "coder": "💻", "analyzer": "📊"}
                    t_embed = discord.Embed(
                        title=f"{role_emojis.get(role,'🤖')} {role.capitalize()}",
                        description=info.get("response","")[:3800],
                        color={"researcher": 0xFEE75C, "coder": 0x57F287, "analyzer": 0xED4245}.get(role, 0x5865F2)
                    )
                    t_embed.set_footer(text=f"Model: {info.get('model','?')}")
                    await thread.send(embed=t_embed)
            except Exception:
                pass

        await log_request(uname, "swarm", duration, data.get("model", "?"))
    except Exception as e:
        await interaction.channel.send(f"❌ Swarm שגיאה: {e}")


# ─── PHASE 17: ORCHESTRATE (smart multi-agent) ───────────────────────────────

@tree.command(name="orchestrate", description="🧭 מנהל חכם — מפעיל סוכנים אוטומטית לפי הצורך", guild=GUILD)
@app_commands.describe(
    task="המשימה שאתה רוצה לבצע — OpenClaw יחליט אילו סוכנים נדרשים",
    agents="אופציונלי: ציין סוכנים ספציפיים (coder,researcher,analyzer,critic)"
)
async def orchestrate_cmd(interaction: discord.Interaction, task: str, agents: str = None):
    await interaction.response.defer()
    uid   = str(interaction.user.id)
    uname = interaction.user.name

    # Parse agents list if provided
    selected_agents = None
    if agents:
        valid = {"coder", "researcher", "analyzer", "critic"}
        selected_agents = [a.strip().lower() for a in agents.split(",") if a.strip().lower() in valid]
        if not selected_agents:
            selected_agents = None

    # Thinking embed
    agent_line = f"סוכנים: `{agents}`" if agents else "הסוכנים נבחרים אוטומטית בהתאם למשימה"
    thinking_embed = discord.Embed(
        title="🧭 Orchestrator מופעל...",
        description=(
            f"**משימה:** {task[:200]}\n\n"
            f"🔍 {agent_line}\n\n"
            "_מנתח את המשימה, בוחר סוכנים, מריץ במקביל ומסנתז תשובה מושלמת..._\n"
            "⏳ זה לוקח ~30-60 שניות"
        ),
        color=0x9B59B6
    )
    thinking_msg = await interaction.followup.send(embed=thinking_embed)

    try:
        payload = {
            "user_id": f"orchestrate:{uid}",
            "username": uname,
            "task": task,
        }
        if selected_agents:
            payload["agents"] = selected_agents

        async with aiohttp.ClientSession() as session:
            async with session.post(
                ORCHESTRATE_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=180)
            ) as resp:
                data = await resp.json()

        plan          = data.get("plan", "")
        agents_used   = data.get("agents_used", [])
        agent_results = data.get("agent_responses", {})
        critic_data   = data.get("critic", {})
        synthesis     = data.get("synthesis", "שגיאה")
        duration      = data.get("duration", 0)

        # Main embed: synthesis
        agent_emojis = {"researcher": "🔍", "coder": "💻", "analyzer": "📊", "critic": "⚖️"}
        used_str = " + ".join(f"{agent_emojis.get(a,'🤖')}{a}" for a in agents_used)
        main_embed = discord.Embed(
            title=f"🧭 Orchestrator — {task[:60]}",
            description=synthesis[:3900],
            color=0x9B59B6
        )
        main_embed.set_footer(text=f"⏱ {duration}s | {used_str} | {plan[:80]}")
        await thinking_msg.edit(embed=main_embed)

        # Thread with individual agent outputs + critic
        if hasattr(interaction.channel, 'create_thread') and agent_results:
            try:
                thread = await interaction.channel.create_thread(
                    name=f"Orchestrate: {task[:50]}",
                    auto_archive_duration=60
                )
                colors = {"researcher": 0xFEE75C, "coder": 0x57F287, "analyzer": 0xED4245, "critic": 0xEB459E}
                for role, info in agent_results.items():
                    t_embed = discord.Embed(
                        title=f"{agent_emojis.get(role,'🤖')} {role.capitalize()}",
                        description=info.get("response", "")[:3900],
                        color=colors.get(role, 0x5865F2)
                    )
                    t_embed.set_footer(text=f"Model: {info.get('model','?')}")
                    await thread.send(embed=t_embed)
                # Critic in thread too
                if critic_data.get("response"):
                    c_embed = discord.Embed(
                        title="⚖️ Critic",
                        description=critic_data["response"][:3900],
                        color=0xEB459E
                    )
                    c_embed.set_footer(text=f"Model: {critic_data.get('model','?')}")
                    await thread.send(embed=c_embed)
            except Exception:
                pass

        await log_request(uname, "orchestrate", duration, data.get("synthesis_model", "?"))

    except Exception as e:
        err_embed = discord.Embed(
            title="❌ Orchestrator שגיאה",
            description=str(e)[:500],
            color=0xED4245
        )
        try:
            await thinking_msg.edit(embed=err_embed)
        except Exception:
            await interaction.channel.send(f"❌ Orchestrator שגיאה: {e}")


# ─── PHASE 16: SCHEDULE ──────────────────────────────────────────────────────

@tree.command(name="schedule", description="⏰ מתזמן משימות (add/list/remove)", guild=GUILD)
@app_commands.describe(
    action="add / list / remove",
    task="תיאור המשימה (לdaily briefing, price check וכו')",
    minutes="כל כמה דקות להריץ (e.g. 60 = כל שעה)",
    id="מזהה למחיקה (מ-/schedule list)"
)
async def schedule_cmd(
    interaction: discord.Interaction,
    action: str,
    task: str = None,
    minutes: int = None,
    id: int = None
):
    await interaction.response.defer(ephemeral=True)
    uid   = str(interaction.user.id)
    uname = interaction.user.name

    action = action.lower().strip()

    # ── LIST ──
    if action == "list":
        scheds = list_schedules(uid)
        if not scheds:
            await interaction.followup.send("📅 אין משימות מתוזמנות.")
            return
        embed = discord.Embed(title="📅 משימות מתוזמנות", color=0x5865F2)
        for s in scheds:
            embed.add_field(
                name=f"#{s['sid']} — כל {s['minutes']} דקות",
                value=f"📝 {s['task'][:200]}",
                inline=False
            )
        embed.set_footer(text="/schedule action:remove id:<מזהה> למחיקה")
        await interaction.followup.send(embed=embed)
        return

    # ── REMOVE ──
    if action == "remove":
        if id is None:
            await interaction.followup.send("❌ ציין id. השתמש ב-`/schedule list` לראות מזהים.")
            return
        job_id = f"sched_{uid}_{id}"
        if scheduler and scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        delete_schedule_data(uid, id)
        await interaction.followup.send(f"🗑️ משימה #{id} נמחקה.")
        return

    # ── ADD ──
    if action == "add":
        if not task:
            await interaction.followup.send("❌ ציין task.")
            return
        if not minutes or minutes < 1:
            await interaction.followup.send("❌ ציין minutes (מינימום 1).")
            return

        sid = int(_r.incr(f"sched:cnt:{uid}"))
        channel_id = interaction.channel_id
        save_schedule(uid, sid, channel_id, task, minutes)

        async def fire_schedule():
            """Called by APScheduler — runs the task and posts result to Discord."""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        GATEWAY_URL,
                        json={"user_id": f"sched:{uid}", "username": uname,
                              "message": task, "system_prompt": None},
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        data = await resp.json()
                reply   = data.get("response","שגיאה")
                model   = data.get("model","?")
                channel = client.get_channel(channel_id)
                if channel:
                    embed = discord.Embed(
                        title=f"⏰ משימה מתוזמנת: {task[:60]}",
                        description=reply[:3800],
                        color=0x00FF99
                    )
                    embed.set_footer(text=f"Model: {model} | כל {minutes} דקות | #{sid}")
                    await channel.send(embed=embed)
            except Exception as ex:
                logger.error(f"Schedule fire error: {ex}")

        if scheduler:
            scheduler.add_job(
                fire_schedule,
                IntervalTrigger(minutes=minutes),
                id=f"sched_{uid}_{sid}",
                replace_existing=True
            )

        embed = discord.Embed(title="⏰ משימה נוצרה!", color=0x57F287)
        embed.add_field(name="📝 משימה",   value=task[:300],         inline=False)
        embed.add_field(name="⏱ תדירות",  value=f"כל {minutes} דקות", inline=True)
        embed.add_field(name="🆔 מזהה",    value=str(sid),            inline=True)
        embed.set_footer(text="/schedule action:remove id:<מזהה> לביטול")
        await interaction.followup.send(embed=embed)
        return

    await interaction.followup.send("❌ action לא מוכר. השתמש ב: `add` / `list` / `remove`")


@tree.command(name="help", description="📋 רשימת פקודות", guild=GUILD)
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Openclaw AI — פקודות (Phase 17)", color=0x5865F2)
    embed.add_field(name="/main [message] [image?]",     value="🤖 שאלה כללית — **תומך תמונות!** — עם Streaming", inline=False)
    embed.add_field(name="/coder [message] [image?]",    value="💻 עזרה בקוד — שלח screenshot שגיאה!", inline=False)
    embed.add_field(name="/research [message] [image?]", value="🔍 מחקר מעמיק — עם Streaming", inline=False)
    embed.add_field(name="/analyze [message] [image?]",  value="📊 ניתוח — שלח גרף לניתוח!", inline=False)
    embed.add_field(name="/vision [image] [question?]",  value="👁️ **NEW** — ניתוח תמונה עם Gemini Vision", inline=False)
    embed.add_field(name="/orchestrate [task] [agents?]", value="🧭 **NEW** — מנהל חכם שבוחר סוכנים אוטומטית + ביקורת + סינתזה", inline=False)
    embed.add_field(name="/swarm [task]",                value="🤖 3 סוכנים במקביל: חוקר+מתכנת+מנתח", inline=False)
    embed.add_field(name="/search [query]",              value="🔎 חיפוש באינטרנט עם DuckDuckGo", inline=False)
    embed.add_field(name="/run [code]",                  value="⚙️ הרצת קוד Python בסביבה מבודדת", inline=False)
    embed.add_field(name="/memory [reset?]",             value="🧠 מה המערכת זוכרת עליך", inline=False)
    embed.add_field(name="/recall [query]",              value="🧠 חפש בזיכרון הארוך-טווח", inline=False)
    embed.add_field(name="/store-memory [text]",         value="💾 שמור זיכרון ידנית", inline=False)
    embed.add_field(name="/github [owner/repo]",         value="🐙 מידע על GitHub repo", inline=False)
    embed.add_field(name="/github-prs / /github-commits",value="🔀 PRs ו-Commits", inline=False)
    embed.add_field(name="/notion-add/list/search",      value="📝 Notion integration", inline=False)
    embed.add_field(name="/clawhub / /skill-top",        value="🔌 חיפוש ClawHub skills", inline=False)
    embed.add_field(name="/schedule [add/list/remove]",  value="⏰ מתזמן משימות", inline=False)
    embed.add_field(name="#knowledge",                   value="📚 שלח טקסט/קובץ → RAG memory", inline=False)
    embed.add_field(name="#clawhub",                     value="📺 חיפוש skill אוטומטי", inline=False)
    embed.add_field(name="📷 שלח תמונה בכל ערוץ",       value="👁️ Gemini Vision מנתח אוטומטית", inline=False)
    embed.set_footer(text="Phase 17 | Streaming • Vision • /orchestrate • Multi-Agent | Oracle Cloud")
    await interaction.response.send_message(embed=embed)


IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')

# ─── ClawHub skill search ────────────────────────────────────────────────────

async def clawhub_search(query: str, limit: int = 5) -> list[dict]:
    """Search ClawHub skills via their search endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            # ClawHub search API (query param)
            async with session.get(
                f"https://clawhub.ai/api/search",
                params={"q": query, "limit": limit},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("skills", data if isinstance(data, list) else [])
    except Exception:
        pass

    # Fallback: ask our gateway AI to return skill info
    return []


def make_clawhub_embed(query: str, skills: list, from_channel: bool = False) -> discord.Embed:
    embed = discord.Embed(
        title=f"🔌 ClawHub — {query[:50]}",
        description=f"[🔗 פתח ב-ClawHub](https://clawhub.ai/skills?q={query.replace(' ','+')})",
        color=0x7C3AED
    )
    if skills:
        for s in skills[:5]:
            name  = s.get("name") or s.get("slug","?")
            desc  = (s.get("summary") or s.get("description",""))[:120]
            dl    = s.get("downloads","?")
            stars = s.get("stars","?")
            author= s.get("author","?")
            slug  = s.get("slug", name.lower().replace(" ","-"))
            embed.add_field(
                name=f"📦 {name}",
                value=f"{desc}\n`npx clawhub@latest install {slug}`\n👤 {author} | ⬇️ {dl} | ⭐ {stars}",
                inline=False
            )
    else:
        embed.add_field(
            name="🔍 חיפוש ידני",
            value=(
                f"לא נמצאו תוצאות API — חפש ידנית:\n"
                f"[clawhub.ai/skills?q={query.replace(' ','+')}]"
                f"(https://clawhub.ai/skills?q={query.replace(' ','+')})"
            ),
            inline=False
        )
    if from_channel:
        embed.set_footer(text="כתוב שם skill או תיאור • /clawhub להשוואה • install עם npx clawhub@latest install <slug>")
    return embed

async def handle_image(message, caption: str = ""):
    """Send image attachment to Gemini vision endpoint."""
    attachment = next((a for a in message.attachments
                       if any(a.filename.lower().endswith(e) for e in IMAGE_EXTS)), None)
    if not attachment:
        return False
    try:
        payload = {
            "user_id": str(message.author.id),
            "username": message.author.name,
            "image_url": attachment.url,
            "text": caption or "תאר את התמונה הזו בפירוט."
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(VISION_URL, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=45)) as resp:
                data = await resp.json()
        reply = data.get("response", "שגיאה")
        model = data.get("model", "gemini-flash")
        duration = data.get("duration", 0)
        chunks = [reply[i:i+1900] for i in range(0, max(len(reply),1), 1900)]
        for i, chunk in enumerate(chunks):
            suffix = f"\n\n`👁️ {model} | {duration}s`" if i == len(chunks)-1 else ""
            await message.reply(chunk + suffix)
        await log_request(message.author.name, "vision", duration, model)
    except Exception as e:
        await message.reply(f"❌ שגיאת vision: {e}")
    return True


async def dm_reply(message, text: str, model: str = "", duration: float = 0):
    """Send DM reply, split if needed, with model footer on last chunk."""
    chunks = [text[i:i+1900] for i in range(0, max(len(text), 1), 1900)]
    for i, chunk in enumerate(chunks):
        suffix = f"\n\n`{model} | {duration}s`" if (model and i == len(chunks) - 1) else ""
        await message.channel.send(chunk + suffix)


async def handle_dm(message, content: str):
    """Handle DM messages — plain text → /main, slash commands → route correctly."""
    uid = str(message.author.id)
    uname = message.author.name

    # ── Slash-style command parser (/agent, /search, /run, /memory, /help) ──
    if content.startswith('/'):
        parts = content.split(None, 1)
        cmd  = parts[0].lstrip('/').lower()
        arg  = parts[1].strip() if len(parts) > 1 else ''

        # Agent commands
        if cmd in AGENT_CONFIG:
            if not arg:
                await message.channel.send(f"❌ שימוש: `/{cmd} <הודעה>`")
                return
            async with message.channel.typing():
                data = await ask_gateway(uid, uname, arg, cmd)
            await dm_reply(message, data.get("response", "שגיאה"),
                           data.get("model","?"), data.get("duration",0))
            await log_request(uname, cmd, data.get("duration",0), data.get("model","?"))
            return

        # /search
        if cmd == 'search':
            if not arg:
                await message.channel.send("❌ שימוש: `/search <שאילתה>`")
                return
            async with message.channel.typing():
                async with aiohttp.ClientSession() as session:
                    async with session.post(SEARCH_URL, json={"query": arg, "max_results": 5},
                                            timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        data = await resp.json()
            results = data.get("results", [])
            if not results:
                await message.channel.send(f"❌ לא נמצאו תוצאות: `{data.get('error','empty')}`")
                return
            lines = [f"🔎 **תוצאות: {arg[:50]}**\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"**{i}. {r.get('title','')[:60]}**\n{r.get('body','')[:120]}\n{r.get('url','')}\n")
            await dm_reply(message, "\n".join(lines))
            return

        # /run
        if cmd == 'run':
            if not arg:
                await message.channel.send("❌ שימוש: `/run <קוד>`\nאפשר גם multiline עם `\\n`")
                return
            code = clean_code(arg)
            async with message.channel.typing():
                async with aiohttp.ClientSession() as session:
                    async with session.post(CODE_URL, json={"code": code, "timeout": 10},
                                            timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        data = await resp.json()
            status = "✅ הצליח" if data.get("success") else "❌ נכשל"
            out = data.get("output","")[:1200]
            reply = f"⚙️ **Python Runner — {status}**\n```python\n{code[:400]}\n```\n**פלט:**\n```\n{out}\n```\n`exit={data.get('exit_code','?')} | {data.get('duration',0)}s`"
            await dm_reply(message, reply)
            return

        # /memory
        if cmd == 'memory':
            if arg.lower() in ('reset','true','1','איפוס'):
                async with aiohttp.ClientSession() as session:
                    for a in AGENT_CONFIG:
                        await session.delete(f"{MEMORY_URL}/{a}:{uid}")
                await message.channel.send("🧠 זיכרון אופס ✅")
                return
            total_req = total_dur = total_tok = total_ctx = 0
            agent_counts = {}
            async with aiohttp.ClientSession() as session:
                for a in AGENT_CONFIG:
                    async with session.get(f"{MEMORY_URL}/{a}:{uid}") as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            total_req += d.get("request_count", 0)
                            total_dur += d.get("total_duration", 0)
                            total_tok += d.get("total_tokens_est", 0)
                            total_ctx += d.get("context_messages", 0)
                            for k, v in d.get("agent_counts", {}).items():
                                agent_counts[k] = agent_counts.get(k, 0) + v
            avg = round(total_dur / total_req, 2) if total_req else 0
            fav = max(agent_counts, key=agent_counts.get) if agent_counts else "none"
            breakdown = " | ".join(f"/{a}: {c}" for a, c in agent_counts.items()) or "אין"
            text = (f"🧠 **זיכרון — {uname}**\n"
                    f"📊 בקשות: {total_req} | ⭐ מועדף: /{fav}\n"
                    f"⏱ ממוצע: {avg}s | 🔤 טוקנים: {total_tok}\n"
                    f"💬 הודעות בזיכרון: {total_ctx}\n"
                    f"📈 {breakdown}\n\n"
                    f"_כדי לאפס: `/memory reset`_")
            await message.channel.send(text)
            return

        # /recall
        if cmd == 'recall':
            if not arg:
                await message.channel.send("❌ שימוש: `/recall <נושא>`")
                return
            async with message.channel.typing():
                all_mems = []
                async with aiohttp.ClientSession() as session:
                    for ap in ["main", "coder", "research", "analyze", "swarm"]:
                        async with session.post(
                            RECALL_URL,
                            json={"user_id": f"{ap}:{uid}", "query": arg, "top_k": 2},
                            timeout=aiohttp.ClientTimeout(total=20)
                        ) as resp:
                            d = await resp.json()
                            all_mems.extend(d.get("memories", []))
            all_mems.sort(key=lambda x: x["score"], reverse=True)
            top = all_mems[:5]
            if not top:
                await message.channel.send("🧠 לא נמצאו זיכרונות רלוונטיים.")
                return
            lines = [f"🧠 **Recall: {arg[:50]}**\n"]
            for i, m in enumerate(top, 1):
                lines.append(f"**{i}.** [{m['agent']}] score={m['score']}\n{m['text'][:250]}\n")
            await dm_reply(message, "\n".join(lines))
            return

        # /swarm
        if cmd == 'swarm':
            if not arg:
                await message.channel.send("❌ שימוש: `/swarm <משימה>`")
                return
            await message.channel.send("🤖 Swarm מופעל... (~20-30 שניות)")
            async with message.channel.typing():
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        SWARM_URL,
                        json={"user_id": f"swarm:{uid}", "username": uname, "task": arg},
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as resp:
                        data = await resp.json()
            synthesis = data.get("synthesis", "שגיאה")
            duration  = data.get("duration", 0)
            await dm_reply(message, f"🤖 **Swarm — {arg[:60]}**\n\n{synthesis}", data.get("model","?"), duration)
            return

        # /help
        if cmd == 'help':
            help_text = (
                "**🤖 Openclaw AI — פקודות DM**\n\n"
                "**סוכנים:**\n"
                "`/main <שאלה>` — עוזר כללי\n"
                "`/coder <שאלה>` — מומחה קוד\n"
                "`/research <שאלה>` — חוקר מעמיק\n"
                "`/analyze <שאלה>` — מנתח נתונים\n\n"
                "**כלים:**\n"
                "`/search <שאילתה>` — DuckDuckGo\n"
                "`/run <קוד>` — הרצת Python\n"
                "`/memory` — הצג זיכרון\n"
                "`/memory reset` — אפס זיכרון\n"
                "`/recall <נושא>` — זיכרון ארוך-טווח\n"
                "`/swarm <משימה>` — 3 סוכנים במקביל\n\n"
                "**ללא פקודה** — ישירות ל-/main 💬"
            )
            await message.channel.send(help_text)
            return

        # Unknown slash command
        await message.channel.send(f"❓ פקודה לא מוכרת: `{cmd}`\nכתוב `/help` לרשימה מלאה.")
        return

    # ── /vision or unknown slash → hint ──────────────────────────────────────
    if content.startswith('/'):
        await message.channel.send(f"❓ פקודה לא מוכרת.\nכתוב `/help` לרשימה מלאה.")
        return

    # ── Plain text → main agent ───────────────────────────────────────────────
    try:
        async with message.channel.typing():
            data = await ask_gateway(uid, uname, content, "main")
        await dm_reply(message, data.get("response", "שגיאה"),
                       data.get("model","?"), data.get("duration",0))
        await log_request(uname, "main", data.get("duration",0), data.get("model","?"))
    except Exception as e:
        await message.channel.send(f"❌ שגיאה: {e}")


@client.event
async def on_message(message):
    if message.author.bot:
        return

    # ── #ai-admin channel — Natural language → AI → shell commands on server ──
    if (hasattr(message.channel, 'name') and
            message.channel.name == AI_ADMIN_CHANNEL_NAME):
        if str(message.author.id) != ADMIN_ID:
            await message.reply("⛔ ערוץ זה מיועד לAdmin בלבד.", delete_after=5)
            try: await message.delete()
            except Exception: pass
            return
        user_request = message.content.strip()
        if not user_request:
            return
        try: await message.add_reaction("🤔")
        except Exception: pass

        # Step 1: Ask AI to convert natural language → shell command(s)
        system_prompt = """אתה מנהל שרת לינוקס מומחה. השרת הוא Oracle Cloud Ubuntu 22.04.
הפרויקט נמצא ב: /home/ubuntu/ai-system/
הבוט נמצא ב: /home/ubuntu/ai-system/discord-bot/bot.py
ה-gateway נמצא ב: /home/ubuntu/ai-system/gateway/
LiteLLM רץ על port 4000.
Gateway (uvicorn) רץ על port 4001.
websockify רץ על port 6081.

כאשר המשתמש מבקש משהו בעברית או כל שפה אחרת:
1. הבן מה הוא רוצה לעשות על השרת
2. החזר JSON בפורמט הבא בדיוק:
{
  "explanation": "הסבר קצר בעברית מה אתה עושה",
  "commands": ["פקודה1", "פקודה2"],
  "dangerous": false
}

חוקים:
- אם המשתמש מבקש לראות סטטוס/לוגים/מידע → commands עם cat/systemctl status/journalctl/ps
- אם המשתמש מבקש להפעיל/לכבות → commands עם systemctl start/stop/restart
- אם המשתמש מבקש לעדכן קוד → git pull + restart
- אם המשתמש מבקש להתקין משהו → apt-get install
- אם המשתמש מבקש לראות קבצים → ls/cat/find
- אם הבקשה מסוכנת (מחיקת קבצים חשובים, shutdown) → dangerous: true
- החזר JSON בלבד, ללא טקסט נוסף"""

        async with message.channel.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "user_id": f"ai-admin:{message.author.id}",
                        "message": user_request,
                        "system_prompt": system_prompt,
                        "username": message.author.name
                    }
                    async with session.post(
                        GATEWAY_URL,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        data = await resp.json()
                        ai_response = data.get("response", "")
            except Exception as e:
                await message.reply(f"❌ שגיאה בתקשורת עם AI: `{e}`")
                return

        # Step 2: Parse AI response
        import re
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                import json as json_lib
                parsed = json_lib.loads(json_match.group())
                explanation = parsed.get("explanation", "מריץ פקודות...")
                commands = parsed.get("commands", [])
                dangerous = parsed.get("dangerous", False)
            else:
                raise ValueError("No JSON found")
        except Exception:
            # AI didn't return JSON — just show its response as explanation
            await message.reply(f"🤖 **AI:** {ai_response[:1500]}")
            try: await message.remove_reaction("🤔", client.user)
            except Exception: pass
            return

        # Step 3: Safety check
        if dangerous:
            await message.reply(
                f"⚠️ **בקשה מסוכנת!**\n"
                f"AI זיהה שהפקודות עלולות להיות מסוכנות:\n"
                f"```\n{chr(10).join(commands)}\n```\n"
                f"לאישור, שלח: `!admin {'; '.join(commands)}`"
            )
            try: await message.remove_reaction("🤔", client.user)
            except Exception: pass
            return

        if not commands:
            await message.reply(f"🤖 {explanation}")
            try: await message.remove_reaction("🤔", client.user)
            except Exception: pass
            return

        # Step 4: Execute commands and collect output
        try: await message.remove_reaction("🤔", client.user)
        except Exception: pass
        try: await message.add_reaction("⚙️")
        except Exception: pass

        full_cmd = " && ".join(commands)
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True, text=True, timeout=60
            )
            output = result.stdout or result.stderr or "(אין פלט)"
            exit_ok = result.returncode == 0
        except subprocess.TimeoutExpired:
            output = "⏱️ Timeout - הפקודה לקחה יותר מ-60 שניות"
            exit_ok = False

        # Step 5: Reply with friendly format
        status = "✅" if exit_ok else "❌"
        output_short = output[:1200]
        reply_parts = [
            f"{status} **{explanation}**",
            f"```bash\n$ {full_cmd[:200]}\n```",
        ]
        if output_short.strip():
            reply_parts.append(f"```\n{output_short}\n```")

        await message.reply("\n".join(reply_parts))
        try: await message.remove_reaction("⚙️", client.user)
        except Exception: pass
        return

    # ── #terminal channel — Every message = direct shell command on server ──
    if (hasattr(message.channel, 'name') and
            message.channel.name == TERMINAL_CHANNEL_NAME):
        if str(message.author.id) != ADMIN_ID:
            await message.reply("⛔ ערוץ זה מיועד לAdmin בלבד.", delete_after=5)
            try: await message.delete()
            except Exception: pass
            return
        cmd = message.content.strip()
        if not cmd:
            return
        # Special meta-commands
        if cmd == "help":
            help_msg = (
                "**🖥️ #terminal — פקודות שרת ישירות**\n\n"
                "כל מה שתכתוב כאן רץ ישירות על שרת Oracle!\n\n"
                "**דוגמאות:**\n"
                "```\n"
                "uptime\n"
                "free -h\n"
                "df -h\n"
                "ps aux | grep python\n"
                "sudo systemctl status openclaw-bot\n"
                "sudo systemctl restart openclaw-bot\n"
                "cat /home/ubuntu/openclaw-discord-ai-system/.env\n"
                "tail -20 /var/log/syslog\n"
                "cd /home/ubuntu/openclaw-discord-ai-system && git pull origin main\n"
                "```\n\n"
                "⚠️ **הכל רץ כ-ubuntu user עם sudo access**"
            )
            await message.reply(help_msg)
            return
        # Add reaction to show command is running
        try: await message.add_reaction("⏳")
        except Exception: pass
        # Execute command
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60
            )
            out = result.stdout or result.stderr or "(no output)"
            exit_code = result.returncode
            status_emoji = "✅" if exit_code == 0 else "❌"
            # Split long output into chunks
            chunks = [out[i:i+1800] for i in range(0, min(len(out), 5400), 1800)]
            await message.reply(f"{status_emoji} `exit={exit_code}` `$ {cmd[:60]}`\n```\n{chunks[0]}\n```")
            for chunk in chunks[1:]:
                await message.channel.send(f"```\n{chunk}\n```")
        except subprocess.TimeoutExpired:
            await message.reply(f"⏱️ Timeout (60s): `{cmd[:100]}`")
        except Exception as e:
            await message.reply(f"❌ Error: `{e}`")
        # Update reaction
        try:
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("✅" if exit_code == 0 else "❌")
        except Exception: pass
        return

    # ── #admin channel — Admin-only, all commands as text ────────────────────
    if (hasattr(message.channel, 'name') and
            message.channel.name == ADMIN_CHANNEL_NAME):
        if str(message.author.id) != ADMIN_ID:
            await message.reply("⛔ ערוץ זה מיועד לAdmin בלבד.", delete_after=5)
            try: await message.delete()
            except Exception: pass
            return
        content = message.content.strip()
        if not content:
            return
        parts = content.split(None, 1)
        cmd = parts[0].lstrip('/').lower()
        arg = parts[1].strip() if len(parts) > 1 else ''
        uid, uname = str(message.author.id), message.author.name

        # ── Route to any agent ──
        if cmd in AGENT_CONFIG:
            async with message.channel.typing():
                data = await ask_gateway(uid, uname, arg or "שלום", cmd)
            embed = make_embed(cmd, data.get("response",""), data.get("model","?"), data.get("duration",0))
            await message.reply(embed=embed)
            return

        # ── /search ──
        if cmd == 'search':
            async with message.channel.typing():
                async with aiohttp.ClientSession() as s:
                    async with s.post(SEARCH_URL, json={"query": arg, "max_results": 5},
                                      timeout=aiohttp.ClientTimeout(total=30)) as r:
                        data = await r.json()
            results = data.get("results", [])
            lines = [f"🔎 **{arg}**\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"**{i}.** [{r.get('title','')}]({r.get('url','')})\n{r.get('body','')[:100]}\n")
            await message.reply("\n".join(lines)[:1900])
            return

        # ── /run ──
        if cmd == 'run':
            code = clean_code(arg)
            async with message.channel.typing():
                async with aiohttp.ClientSession() as s:
                    async with s.post(CODE_URL, json={"code": code, "timeout": 10},
                                      timeout=aiohttp.ClientTimeout(total=20)) as r:
                        data = await r.json()
            status = "✅" if data.get("success") else "❌"
            out = data.get("output","")[:1500]
            await message.reply(f"{status} `exit={data.get('exit_code','?')} | {data.get('duration',0)}s`\n```python\n{code[:300]}\n```\n```\n{out}\n```")
            return

        # ── /memory ──
        if cmd == 'memory':
            if arg.lower() in ('reset-all', 'reset_all', 'all'):
                async with aiohttp.ClientSession() as s:
                    async with s.delete(f"{MEMORY_URL}") as r:
                        result = await r.json()
                await message.reply(f"🧠 ריסט כולל: {result}")
                return

        # ── /recall ──
        if cmd == 'recall':
            all_mems = []
            async with message.channel.typing():
                async with aiohttp.ClientSession() as s:
                    for ap in ["main", "coder", "research", "analyze", "swarm"]:
                        async with s.post(
                            RECALL_URL,
                            json={"user_id": f"{ap}:{uid}", "query": arg, "top_k": 3},
                            timeout=aiohttp.ClientTimeout(total=20)
                        ) as r2:
                            d = await r2.json()
                            all_mems.extend(d.get("memories", []))
            all_mems.sort(key=lambda x: x["score"], reverse=True)
            lines = [f"🧠 **Recall: {arg}**\n"]
            for i, m in enumerate(all_mems[:6], 1):
                lines.append(f"**{i}.** [{m['agent']}] {m['score']}\n{m['text'][:200]}\n")
            await message.reply("\n".join(lines)[:1900] or "לא נמצאו זיכרונות.")
            return

        # ── /swarm ──
        if cmd == 'swarm':
            await message.reply("🤖 Swarm מופעל... (~20-30 שניות)")
            async with message.channel.typing():
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        SWARM_URL,
                        json={"user_id": f"swarm:{uid}", "username": uname, "task": arg},
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as r2:
                        data = await r2.json()
            embed = make_embed("main", data.get("synthesis","שגיאה"), data.get("model","?"), data.get("duration",0))
            embed.title = f"🤖 Swarm — {arg[:60]}"
            await message.reply(embed=embed)
            return

        # ── /clawhub ──
        if cmd == 'clawhub':
            async with message.channel.typing():
                skills = await clawhub_search(arg)
            embed = make_clawhub_embed(arg, skills)
            await message.reply(embed=embed)
            return

        # ── /skill-top ──
        if cmd in ('skill-top', 'skills'):
            page = int(arg) if arg.isdigit() else 1
            per_page = 13
            start = (page - 1) * per_page
            chunk = ALL_SKILLS[start:start + per_page]
            total_pages = (len(ALL_SKILLS) + per_page - 1) // per_page
            embed = discord.Embed(title=f"🏆 Top Skills — עמוד {page}/{total_pages}", color=0x7C3AED)
            for slug, author, dl, stars, desc in chunk:
                embed.add_field(name=f"📦 {slug}  ⬇️{dl} ⭐{stars}",
                                value=f"{desc}\n`npx clawhub@latest install {slug}`", inline=False)
            embed.set_footer(text=f"skills page:2 לעמוד הבא")
            await message.reply(embed=embed)
            return

        # ── /status ──
        if cmd == 'status':
            async with message.channel.typing():
                r = subprocess.run("pgrep -c -f 'litellm|uvicorn|bot.py'",
                                   shell=True, capture_output=True, text=True)
                gw = subprocess.run("curl -s http://localhost:4001/health",
                                    shell=True, capture_output=True, text=True)
            await message.reply(f"⚙️ Processes: `{r.stdout.strip()}`\n🌐 Gateway: `{gw.stdout.strip()}`")
            return

        # ── /restart ──
        if cmd == 'restart':
            subprocess.Popen(
                "sleep 1 && tmux kill-session -t bot && "
                "tmux new-session -d -s bot 'python3 /home/ubuntu/ai-system/discord-bot/bot.py'",
                shell=True
            )
            await message.reply("🔄 Restarting bot...")
            return

        # ── /logs ──
        if cmd == 'logs':
            r = subprocess.run("tail -30 /tmp/bot.log 2>/dev/null",
                               shell=True, capture_output=True, text=True)
            await message.reply(f"```{r.stdout[-1800:]}```")
            return

        # ── /models ──
        if cmd == 'models':
            r = subprocess.run(
                "curl -s http://localhost:4000/models -H 'Authorization: Bearer sk-litellm-master-2026'",
                shell=True, capture_output=True, text=True)
            import json as _json
            try:
                names = "\n".join(m["id"] for m in _json.loads(r.stdout).get("data",[])[:20])
            except Exception:
                names = r.stdout[:400]
            await message.reply(f"```\n{names}\n```")
            return

        # ── fallback: shell command ──
        r = subprocess.run(content, shell=True, capture_output=True, text=True, timeout=30)
        out = (r.stdout or r.stderr)[:1800]
        await message.reply(f"```{out}```" if out else "✅ (no output)")
        return
    # ─────────────────────────────────────────────────────────────────────────

    # ── #knowledge channel — embed text/files into long-term memory (RAG) ───
    if (hasattr(message.channel, 'name') and
            message.channel.name == KNOWLEDGE_CHANNEL_NAME):
        uid   = str(message.author.id)
        uname = message.author.name
        texts_to_store = []

        # Plain text message
        if message.content.strip():
            texts_to_store.append(message.content.strip())

        # Text file attachments
        for attachment in message.attachments:
            fname = attachment.filename.lower()
            if any(fname.endswith(ext) for ext in ('.txt', '.md', '.py', '.js', '.ts', '.json', '.csv', '.html')):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            raw_text = await resp.text(encoding='utf-8', errors='replace')
                    # Chunk into 500-char pieces with overlap
                    chunk_size, overlap = 500, 50
                    chunks = []
                    for i in range(0, len(raw_text), chunk_size - overlap):
                        chunk = raw_text[i:i + chunk_size].strip()
                        if chunk:
                            chunks.append(f"[{attachment.filename}]: {chunk}")
                    texts_to_store.extend(chunks[:20])  # max 20 chunks per file
                except Exception as e:
                    await message.reply(f"❌ לא הצלחתי לקרוא את הקובץ: {e}")

        if not texts_to_store:
            return

        # Store all chunks
        stored = 0
        async with aiohttp.ClientSession() as session:
            for text in texts_to_store:
                try:
                    await session.post(
                        STORE_MEMORY_URL,
                        json={"user_id": f"main:{uid}", "text": text, "agent": "knowledge"},
                        timeout=aiohttp.ClientTimeout(total=15)
                    )
                    stored += 1
                except Exception:
                    pass

        await message.reply(
            f"📚 **{stored} קטעים נשמרו לזיכרון!**\n"
            f"השתמש ב-`/recall <נושא>` כדי לשלוף אותם בשיחות."
        )
        return

    # ── #clawhub channel — auto skill search ─────────────────────────────────
    if (hasattr(message.channel, 'name') and
            message.channel.name == CLAWHUB_CHANNEL_NAME and
            message.content.strip()):
        query = message.content.strip()
        async with message.channel.typing():
            skills = await clawhub_search(query)
            # Enrich with AI if no API results
            ai_desc = ""
            if not skills:
                try:
                    ai_data = await ask_gateway(
                        str(message.author.id), message.author.name,
                        f"תאר בקצרה (3-4 שורות) את הskill הבא מ-ClawHub: '{query}'. "
                        f"אם לא מכיר, הסבר מה skill כזה יכול לעשות.",
                        "research"
                    )
                    ai_desc = ai_data.get("response","")[:400]
                except Exception:
                    pass
            embed = make_clawhub_embed(query, skills, from_channel=True)
            if ai_desc:
                embed.add_field(name="🤖 AI תיאור", value=ai_desc, inline=False)
        await message.reply(embed=embed)
        return
    # ─────────────────────────────────────────────────────────────────────────

    # ── Image/Vision handler (works in guild + DM) ───────────────────────────
    if message.attachments and any(
        any(a.filename.lower().endswith(e) for e in IMAGE_EXTS)
        for a in message.attachments
    ):
        caption = message.content.strip()
        await handle_image(message, caption)
        return
    # ─────────────────────────────────────────────────────────────────────────

    # ── DM support ────────────────────────────────────────────────────────────
    if isinstance(message.channel, discord.DMChannel):
        content = message.content.strip()
        if not content:
            return
        await handle_dm(message, content)
        return
    # ──────────────────────────────────────────────────────────────────────────

    if str(message.author.id) != ADMIN_ID:
        return
    if not message.content.startswith("!admin"):
        return
    parts = message.content.split(None, 1)
    subcmd = parts[1] if len(parts) > 1 else "status"
    if subcmd == "status":
        r = subprocess.run("pgrep -c -f 'litellm|uvicorn|bot.py'", shell=True, capture_output=True, text=True)
        await message.reply(f"Processes: {r.stdout.strip()}")
    elif subcmd == "models":
        r = subprocess.run(
            "curl -s http://localhost:4000/models -H 'Authorization: Bearer sk-litellm-master-2026'",
            shell=True, capture_output=True, text=True
        )
        import json
        try:
            d = json.loads(r.stdout)
            names = "\n".join(m["id"] for m in d.get("data", [])[:15])
        except Exception:
            names = r.stdout[:400]
        await message.reply(f"```\n{names}\n```")
    elif subcmd == "stats":
        avg = round(stats["total_duration"] / stats["total"], 2) if stats["total"] else 0
        msg = f"Total: {stats['total']} | Avg: {avg}s\nBy agent: {stats['by_agent']}\nModels: {stats['models']}"
        await message.reply(f"```{msg}```")
    elif subcmd == "memory-reset-all":
        import asyncio
        async def do_reset():
            async with aiohttp.ClientSession() as session:
                async with session.delete(f"{MEMORY_URL}") as resp:
                    return await resp.json()
        result = asyncio.get_event_loop().run_until_complete(do_reset())
        await message.reply(f"✅ אופס זיכרון כולל: {result}")
    elif subcmd == "restart":
        subprocess.Popen(
            "sleep 1 && sudo systemctl restart openclaw-bot openclaw-gateway",
            shell=True
        )
        await message.reply("🔄 Restarting bot + gateway via systemctl...")
    elif subcmd == "restart-bot":
        subprocess.Popen("sleep 1 && sudo systemctl restart openclaw-bot", shell=True)
        await message.reply("🔄 Restarting bot...")
    elif subcmd == "restart-gateway":
        subprocess.Popen("sleep 1 && sudo systemctl restart openclaw-gateway", shell=True)
        await message.reply("🔄 Restarting gateway...")
    elif subcmd == "update":
        r = subprocess.run(
            "cd /home/ubuntu/openclaw-discord-ai-system && git pull origin main 2>&1",
            shell=True, capture_output=True, text=True, timeout=60
        )
        await message.reply(f"📥 Git pull:\n```{r.stdout[-800:]}```\nUse `!admin restart` to apply.")
    elif subcmd == "logs":
        r = subprocess.run(
            "sudo journalctl -u openclaw-bot -n 20 --no-pager 2>/dev/null || tail -20 /tmp/bot.log 2>/dev/null",
            shell=True, capture_output=True, text=True
        )
        await message.reply(f"```{r.stdout[-1800:]}```")
    elif subcmd == "logs-gateway":
        r = subprocess.run(
            "sudo journalctl -u openclaw-gateway -n 20 --no-pager 2>/dev/null",
            shell=True, capture_output=True, text=True
        )
        await message.reply(f"```{r.stdout[-1800:]}```")
    elif subcmd == "service-status":
        r = subprocess.run(
            "sudo systemctl status openclaw-bot openclaw-gateway openclaw-redis 2>&1 | head -50",
            shell=True, capture_output=True, text=True
        )
        await message.reply(f"```{r.stdout[-1800:]}```")
    elif subcmd == "tunnel":
        # Start Cloudflare Quick Tunnel for noVNC (port 6081) — bypasses all firewalls
        await message.reply("🌐 מפעיל Cloudflare Tunnel ל-noVNC...\nמחכה לURL (~10 שניות)")
        r = subprocess.run(
            "which cloudflared || (curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared)",
            shell=True, capture_output=True, text=True, timeout=60
        )
        proc = subprocess.Popen(
            "cloudflared tunnel --url http://localhost:6081 2>&1 | tee /tmp/cf-tunnel.log",
            shell=True
        )
        import time
        time.sleep(10)
        r2 = subprocess.run("grep -o 'https://.*trycloudflare.com' /tmp/cf-tunnel.log | head -1", shell=True, capture_output=True, text=True)
        url = r2.stdout.strip()
        if url:
            await message.reply(f"✅ **Cloudflare Tunnel פעיל!**\n🌐 גישה מכל מחשב (גם חסום):\n{url}/vnc.html\n\n*ה-URL חי עד ש-tunnel נסגר.*")
        else:
            r3 = subprocess.run("cat /tmp/cf-tunnel.log | tail -20", shell=True, capture_output=True, text=True)
            await message.reply(f"⏳ Tunnel מופעל, לוג:\n```{r3.stdout[-800:]}```\nנסה שוב בעוד 30 שניות: `!admin tunnel-url`")
    elif subcmd == "tunnel-url":
        r = subprocess.run("grep -o 'https://.*trycloudflare.com' /tmp/cf-tunnel.log | tail -1", shell=True, capture_output=True, text=True)
        url = r.stdout.strip()
        if url:
            await message.reply(f"🌐 **Cloudflare Tunnel URL:**\n{url}/vnc.html")
        else:
            await message.reply("❌ Tunnel לא פעיל. הרץ: `!admin tunnel`")
    elif subcmd == "tunnel-stop":
        subprocess.run("pkill cloudflared", shell=True)
        await message.reply("🛑 Cloudflare Tunnel נסגר.")
    elif subcmd == "env":
        r = subprocess.run(
            "grep -v 'TOKEN\\|KEY\\|SECRET\\|PASSWORD' /home/ubuntu/openclaw-discord-ai-system/.env 2>/dev/null | head -20",
            shell=True, capture_output=True, text=True
        )
        await message.reply(f"```{r.stdout[-800:]}```")
    elif subcmd == "help":
        help_text = """**🔑 !admin Commands:**
`!admin status` — מספר פרוצסים פעילים
`!admin service-status` — סטטוס services
`!admin logs` — לוגים אחרונים של הבוט
`!admin logs-gateway` — לוגים של gateway
`!admin restart` — restart bot + gateway
`!admin restart-bot` — restart בוט בלבד
`!admin restart-gateway` — restart gateway בלבד
`!admin update` — git pull קוד חדש
`!admin tunnel` — Cloudflare Tunnel לגישה מכל מחשב
`!admin tunnel-url` — הצג את ה-URL של ה-tunnel
`!admin tunnel-stop` — עצור את ה-tunnel
`!admin models` — רשימת מודלים ב-LiteLLM
`!admin stats` — סטטיסטיקות
`!admin memory-reset-all` — ריסט כל הזיכרון
`!admin env` — הצג משתני סביבה (ללא סודות)
`!admin <any bash>` — הרץ כל פקודה על השרת!

**דוגמאות:**
`!admin cat /proc/uptime` — uptime השרת
`!admin free -h` — זיכרון פנוי
`!admin df -h` — מקום אחסון"""
        await message.reply(help_text)
    else:
        r = subprocess.run(subcmd, shell=True, capture_output=True, text=True, timeout=60)
        out = (r.stdout or r.stderr or "no output")[:1800]
        await message.reply(f"```{out}```")


client.run(DISCORD_TOKEN)

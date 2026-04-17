# discord-bot/ui_helpers.py
# Embed builders, progress bars, and interactive views

import os
import aiohttp
import discord

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:4001")

# צבעים לפי סוכן (hex)
COLORS = {
    "main": 0x5865F2,
    "coder": 0x57F287,
    "researcher": 0xFEE75C,
    "analyzer": 0xEB459E,
    "orchestrator": 0xED4245,
    "critic": 0xFFA500,
    "kilo": 0x2C2F33,
    "tool": 0x99AAB5,
    "error": 0xED4245,
    "success": 0x57F287,
    "memory": 0x9B59B6,
}

AGENT_EMOJI = {
    "main": "🤖",
    "coder": "💻",
    "researcher": "🔍",
    "analyzer": "📊",
    "orchestrator": "🧭",
    "critic": "⚖️",
}

FRAMES = [
    "⬜⬜⬜⬜⬜",
    "🟦⬜⬜⬜⬜",
    "🟦🟦⬜⬜⬜",
    "🟦🟦🟦⬜⬜",
    "🟦🟦🟦🟦⬜",
    "🟦🟦🟦🟦🟦",
]


def make_thinking_embed(agent: str, frame: str = FRAMES[0]) -> discord.Embed:
    emoji = AGENT_EMOJI.get(agent, "🤖")
    e = discord.Embed(
        title=f"{emoji} {agent.capitalize()} חושב...",
        description=frame,
        color=COLORS.get(agent, COLORS["main"]),
    )
    e.set_footer(text="OpenClaw v3 • agentic loop")
    return e


def make_response_embed(
    response: str,
    agent: str,
    model: str,
    elapsed: float,
    iterations: int,
    project: str | None,
) -> discord.Embed:
    emoji = AGENT_EMOJI.get(agent, "🤖")
    content = response[:3800]
    if len(response) > 3800:
        content += "\n\n*(תשובה ארוכה — קוצרה)*"

    e = discord.Embed(
        description=content,
        color=COLORS.get(agent, COLORS["main"]),
    )
    e.set_author(name=f"{emoji} {agent.capitalize()}")

    footer_parts = [f"🧠 {model}", f"⏱ {elapsed}s"]
    if iterations > 1:
        footer_parts.append(f"🔄 {iterations} צעדים")
    if project:
        footer_parts.append(f"📁 {project}")
    e.set_footer(text="  •  ".join(footer_parts))
    return e


def make_tool_log_embed(tool_log: list) -> discord.Embed:
    e = discord.Embed(
        title="🔧 Tool Execution Log",
        color=COLORS["tool"],
    )
    for entry in tool_log[:8]:
        name = entry.get("tool", "?")
        elapsed = entry.get("elapsed", 0)
        result = str(entry.get("result", ""))[:200]
        e.add_field(
            name=f"`{name}` — {elapsed}s",
            value=f"```\n{result}\n```",
            inline=False,
        )
    return e


def make_error_embed(error: str) -> discord.Embed:
    return discord.Embed(
        title="❌ שגיאה",
        description=f"```\n{error[:1500]}\n```",
        color=COLORS["error"],
    )


def make_kilo_embed(status: str, task: str) -> discord.Embed:
    e = discord.Embed(
        title="⚡ Kilo CLI",
        description=status,
        color=COLORS["kilo"],
    )
    e.add_field(name="משימה", value=f"`{task[:200]}`", inline=False)
    e.set_footer(text="kilo run --auto")
    return e


# ─── Interactive Views ────────────────────────────────────────────


class ResponseView(discord.ui.View):
    def __init__(
        self, original_message: str, agent: str, channel_id: str, user_id: str
    ):
        super().__init__(timeout=300)
        self.original_message = original_message
        self.agent = agent
        self.channel_id = channel_id
        self.user_id = user_id

    @discord.ui.button(label="🔄 שאל שוב", style=discord.ButtonStyle.secondary)
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{GATEWAY_URL}/chat",
                    json={
                        "user_id": self.user_id,
                        "message": self.original_message,
                        "agent": self.agent,
                        "channel_id": self.channel_id,
                        "username": interaction.user.display_name,
                    },
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as resp:
                    result = await resp.json()

            embed = make_response_embed(
                result["response"],
                self.agent,
                result.get("model", "?"),
                result.get("duration", 0),
                result.get("iterations", 1),
                None,
            )
            view = ResponseView(
                self.original_message,
                self.agent,
                self.channel_id,
                self.user_id,
            )
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await interaction.followup.send(embed=make_error_embed(str(e)))

    @discord.ui.button(label="🔀 החלף סוכן", style=discord.ButtonStyle.secondary)
    async def switch_agent(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        view = AgentSelectView(self.original_message, self.channel_id, self.user_id)
        await interaction.response.send_message("בחר סוכן:", view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ מחק", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message(
            "נמחק ✓", ephemeral=True, delete_after=2
        )


class AgentSelectView(discord.ui.View):
    def __init__(self, original_message: str, channel_id: str, user_id: str):
        super().__init__(timeout=60)
        self.add_item(AgentSelect(original_message, channel_id, user_id))


class AgentSelect(discord.ui.Select):
    def __init__(self, original_message: str, channel_id: str, user_id: str):
        self.original_message = original_message
        self.channel_id = channel_id
        self.user_id = user_id
        options = [
            discord.SelectOption(
                label="🤖 Main", value="main", description="עוזר כללי"
            ),
            discord.SelectOption(
                label="💻 Coder", value="coder", description="מומחה קוד"
            ),
            discord.SelectOption(
                label="🔍 Researcher", value="researcher", description="חוקר מידע"
            ),
            discord.SelectOption(
                label="📊 Analyzer", value="analyzer", description="ניתוח אסטרטגי"
            ),
            discord.SelectOption(
                label="🧭 Orchestrate", value="orchestrate", description="רב-סוכנים"
            ),
        ]
        super().__init__(placeholder="בחר סוכן...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        agent = self.values[0]
        try:
            if agent == "orchestrate":
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        f"{GATEWAY_URL}/orchestrate",
                        json={
                            "user_id": self.user_id,
                            "task": self.original_message,
                            "channel_id": self.channel_id,
                        },
                        timeout=aiohttp.ClientTimeout(total=180),
                    ) as resp:
                        result = await resp.json()
                response = result.get("synthesis", "")
                model = result.get("synthesis_model", "?")
                iterations = 1
                duration = result.get("duration", 0)
            else:
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        f"{GATEWAY_URL}/chat",
                        json={
                            "user_id": self.user_id,
                            "message": self.original_message,
                            "agent": agent,
                            "channel_id": self.channel_id,
                            "username": interaction.user.display_name,
                        },
                        timeout=aiohttp.ClientTimeout(total=180),
                    ) as resp:
                        result = await resp.json()
                response = result.get("response", "")
                model = result.get("model", "?")
                iterations = result.get("iterations", 1)
                duration = result.get("duration", 0)

            embed = make_response_embed(
                response, agent, model, duration, iterations, None
            )
            view = ResponseView(
                self.original_message, agent, self.channel_id, self.user_id
            )
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await interaction.followup.send(embed=make_error_embed(str(e)))


class KiloControlView(discord.ui.View):
    @discord.ui.button(label="✅ סגור", style=discord.ButtonStyle.success)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✓", ephemeral=True, delete_after=1)
        self.stop()

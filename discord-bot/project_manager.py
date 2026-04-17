# discord-bot/project_manager.py
# Discord Category/Channel management for project workspaces

import json
import os
import discord
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ערוצי ברירת מחדל לכל פרויקט חדש
DEFAULT_CHANNELS = [
    ("main", "main", "ערוץ ראשי לשיחות כלליות"),
    ("code", "coder", "קוד ופיתוח — agent: coder"),
    ("research", "researcher", "מחקר ותיעוד — agent: researcher"),
]


class ProjectManager:
    def __init__(self):
        self.redis = None

    async def init(self, guild: discord.Guild):
        self.redis = aioredis.from_url(REDIS_URL)
        print(f"[PM] Ready for guild: {guild.name}")

    async def create_project(self, guild: discord.Guild, project_name: str) -> dict:
        """
        Creates a Discord Category with 3 default channels.
        Returns dict with category_id and list of channel_ids.
        """
        # Create the category
        category = await guild.create_category(
            name=project_name,
            reason=f"OpenClaw: new project {project_name}",
        )

        channel_ids = []
        for suffix, agent, topic in DEFAULT_CHANNELS:
            # Channel name format: projectname-suffix (lowercase, no spaces)
            ch_name = f"{project_name.lower().replace(' ', '-')}-{suffix}"
            ch = await guild.create_text_channel(
                name=ch_name,
                category=category,
                topic=topic,
            )
            channel_ids.append(ch.id)
            if self.redis:
                await self.redis.set(
                    f"channel_meta:{ch.id}",
                    json.dumps(
                        {
                            "project": project_name,
                            "agent": agent,
                            "topic": topic,
                        }
                    ),
                )

        return {
            "category_id": category.id,
            "channel_ids": channel_ids,
            "project": project_name,
        }

    async def add_channel_to_project(
        self,
        guild: discord.Guild,
        project_name: str,
        channel_name: str,
        agent: str = "main",
    ) -> dict:
        """Adds a channel to an existing project category."""
        # Find existing category
        category = discord.utils.get(guild.categories, name=project_name)
        if not category:
            category = await guild.create_category(name=project_name)

        full_name = f"{project_name.lower().replace(' ', '-')}-{channel_name.lower()}"
        ch = await guild.create_text_channel(
            name=full_name,
            category=category,
        )
        if self.redis:
            await self.redis.set(
                f"channel_meta:{ch.id}",
                json.dumps({"project": project_name, "agent": agent}),
            )
        return {"channel_id": ch.id}

    async def get_channel_meta(self, channel_id: int) -> dict:
        """Returns channel metadata (project, agent) from Redis."""
        if not self.redis:
            return {}
        try:
            raw = await self.redis.get(f"channel_meta:{channel_id}")
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

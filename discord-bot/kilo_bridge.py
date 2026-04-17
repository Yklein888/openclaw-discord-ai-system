# discord-bot/kilo_bridge.py
# Bridge between Discord #kilo-code channel and Kilo CLI

import asyncio
import json
import os
import shutil
from typing import Callable, Awaitable, Optional

KILO_BIN = os.getenv("KILO_BIN", "")
WORK_DIR = os.getenv("KILO_WORK_DIR", "/home/ubuntu")


class KiloBridge:
    def __init__(self):
        self.available = False
        self.kilo_path: Optional[str] = None

    async def init(self):
        """Checks if kilo CLI is installed on the server."""
        # Try env var first, then PATH
        candidate = KILO_BIN or shutil.which("kilo") or shutil.which("kilocode")
        if candidate and os.path.isfile(candidate):
            self.available = True
            self.kilo_path = candidate
            print(f"[Kilo] ✅ Found at {candidate}")
        else:
            self.available = False
            print("[Kilo] ⚠️  kilo CLI not found. Channel #kilo-code will show error.")

    async def run_task(
        self,
        task: str,
        callback: Callable[[str, str], Awaitable[None]],
        work_dir: str = WORK_DIR,
        timeout: int = 300,
    ):
        """
        Runs: kilo run --auto "{task}" --format json
        Fires callback(event_type, data) as output arrives.
        event_type: "text" | "done" | "error"
        """
        if not self.available:
            await callback(
                "error",
                "Kilo CLI לא מותקן על השרת.\n"
                "להתקנה: `npm install -g kilocode`\n"
                "לאחר ההתקנה הפעל מחדש: `sudo systemctl restart discord-bot`",
            )
            return

        cmd = [self.kilo_path, "run", "--auto", task, "--format", "json"]
        output_lines = []

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )

            async def read_stdout():
                async for raw_line in proc.stdout:
                    line = raw_line.decode(errors="replace").strip()
                    if not line:
                        continue
                    output_lines.append(line)

                    # Try to parse as JSON event from kilo
                    try:
                        ev = json.loads(line)
                        ev_type = ev.get("type", "")

                        if ev_type == "assistant":
                            content = ev.get("content", "")
                            if isinstance(content, list):
                                for block in content:
                                    if block.get("type") == "text":
                                        await callback("text", block.get("text", ""))
                            elif isinstance(content, str) and content:
                                await callback("text", content)

                        elif ev_type == "tool_use":
                            tool_name = ev.get("name", "?")
                            await callback("text", f"🔧 מפעיל: `{tool_name}`...")

                        elif ev_type == "error":
                            await callback("error", ev.get("message", str(ev)))

                    except json.JSONDecodeError:
                        # Plain text line — send as-is if meaningful
                        if len(line) > 5:
                            await callback("text", line)

            try:
                await asyncio.wait_for(
                    asyncio.gather(read_stdout(), proc.wait()),
                    timeout=timeout,
                )
                summary = "\n".join(output_lines[-40:])
                await callback("done", summary)

            except asyncio.TimeoutError:
                proc.kill()
                await callback(
                    "error", f"⏱ Timeout: הפעולה נמשכה יותר מ-{timeout} שניות"
                )

        except Exception as e:
            await callback("error", f"שגיאה בהפעלת Kilo: {e}")

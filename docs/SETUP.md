# 🚀 OpenClaw v2.0 — Setup Guide

## Prerequisites

- Ubuntu 22.04+ server (ARM64 or x86_64)
- 8GB+ RAM recommended (24GB ideal for all models)
- Python 3.11+
- A Discord bot token
- At least 1 Groq API key + 1 Gemini API key

---

## Step 1 — Server Prep

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv redis-server git curl
sudo systemctl enable --now redis
```

---

## Step 2 — Clone & Install

```bash
cd /home/ubuntu
git clone https://github.com/Yklein888/openclaw-discord-ai-system.git ai-system
cd ai-system

# Create virtualenv
python3 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install --upgrade pip
pip install \
  discord.py \
  fastapi \
  uvicorn \
  httpx \
  aiohttp \
  redis \
  duckduckgo-search \
  pygithub \
  notion-client \
  litellm \
  crawl4ai \
  qdrant-client \
  mem0ai
```

---

## Step 3 — Configure .env

Copy the example and fill in your values:
```bash
cp .env.example .env
nano .env
```

Required fields:
```env
DISCORD_TOKEN=MTQ...          # Discord bot token
GEMINI_KEY_1=AIza...          # At least 1 Gemini key
GITHUB_TOKEN=ghp_...          # GitHub PAT (optional)
NOTION_TOKEN=secret_...       # Notion token (optional)
NOTION_INBOX_DB=...           # Notion database ID (optional)
```

Get API keys:
- **Discord**: https://discord.com/developers/applications → New Application → Bot
- **Gemini**: https://aistudio.google.com/apikey (free, create 5 for rotation)
- **Groq**: https://console.groq.com (free, create 9 for load balancing)
- **Cerebras**: https://cloud.cerebras.ai (free tier)
- **GitHub**: https://github.com/settings/tokens (repo scope)
- **Notion**: https://www.notion.so/my-integrations

---

## Step 4 — Configure LiteLLM

Edit `litellm-config.yaml` and fill in your API keys:

```yaml
model_list:
  - model_name: groq-llama-70b
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: gsk_YOUR_KEY_HERE
      rpm: 30
  # ... add more models
```

---

## Step 5 — Create systemd Services

Copy service files and install:
```bash
sudo cp systemd/ai-gateway.service /etc/systemd/system/
sudo cp systemd/discord-bot.service /etc/systemd/system/
sudo cp systemd/litellm.service /etc/systemd/system/
sudo systemctl daemon-reload
```

---

## Step 6 — Create Discord Bot

1. Go to https://discord.com/developers/applications
2. New Application → name it "OpenClaw"
3. Bot → Add Bot → copy token → save to `.env`
4. Bot → Privileged Gateway Intents → enable:
   - **Message Content Intent** ✅
   - **Server Members Intent** ✅
5. OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Manage Webhooks`, `Read Message History`, `Use Application Commands`
6. Copy URL → invite bot to your server

---

## Step 7 — Update Guild ID

In `discord-bot/bot.py`, update:
```python
GUILD_ID = YOUR_SERVER_ID_HERE  # Right-click server → Copy ID
```

---

## Step 8 — Set Up Discord Channels

Create these channels in your Discord server:
- `#terminal` — Python code execution
- `#knowledge` — Research and deep information
- `#ai-admin` — Admin commands
- `#clawhub` — Skill-based responses

---

## Step 9 — Start Everything

```bash
sudo systemctl enable --now redis litellm ai-gateway discord-bot

# Check status
sudo systemctl status discord-bot ai-gateway litellm redis

# View live logs
journalctl -u discord-bot -f
```

---

## Step 10 — Verify

1. Check bot is online in Discord (green status dot)
2. Test: `curl http://localhost:4001/health`
3. Expected response: `{"status":"ok","version":"2.0","redis":"ok",...}`
4. In Discord: `/help` should show all 22 commands
5. Type any message in any channel — bot should respond

---

## Step 11 — Set Up Daily Backups

```bash
chmod +x backup.sh
# Already added to cron during setup. Verify:
crontab -l | grep backup
# Should show: 0 3 * * * /home/ubuntu/ai-system/backup.sh
```

---

## Troubleshooting

### Bot doesn't respond
```bash
journalctl -u discord-bot -n 50
# Check for: "Logged in as OpenClaw" and "Synced N commands"
```

### Gateway errors
```bash
curl http://localhost:4001/health
journalctl -u ai-gateway -n 50
```

### LiteLLM errors
```bash
journalctl -u litellm -n 50
# Check litellm-config.yaml has valid API keys
```

### Redis not working
```bash
redis-cli ping  # Should return PONG
sudo systemctl restart redis
```

### Disk full
```bash
df -h
# Clean up
pip3 cache purge
sudo apt autoremove && sudo apt clean
# Remove large files
du -sh /home/ubuntu/ai-system/* | sort -rh | head -10
```

---

## Quick Reference

```bash
# SSH to server
ssh -i your-key.pem ubuntu@YOUR_SERVER_IP

# Restart all services
sudo systemctl restart discord-bot ai-gateway litellm

# View bot logs live
journalctl -u discord-bot -f

# Test gateway
curl http://localhost:4001/health
curl -X POST http://localhost:4001/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test","message":"hello","agent":"main"}'

# Test orchestrator
curl -X POST http://localhost:4001/orchestrate \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test","task":"explain how Redis works"}'

# Manual backup
/home/ubuntu/ai-system/backup.sh

# Check memory usage
redis-cli info memory | grep used_memory_human
```

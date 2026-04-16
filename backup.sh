#!/bin/bash
BACKUP_DIR=/home/ubuntu/ai-system/backups
DATE=$(date +%Y-%m-%d)
mkdir -p $BACKUP_DIR

# Redis dump
redis-cli SAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis-$DATE.rdb 2>/dev/null ||   cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis-$DATE.rdb 2>/dev/null || true

# Config files
cp /home/ubuntu/ai-system/.env $BACKUP_DIR/env-$DATE.bak
cp /home/ubuntu/ai-system/litellm-config.yaml $BACKUP_DIR/litellm-$DATE.yaml
cp /etc/systemd/system/discord-bot.service $BACKUP_DIR/discord-bot-$DATE.service 2>/dev/null || true
cp /etc/systemd/system/ai-gateway.service $BACKUP_DIR/ai-gateway-$DATE.service 2>/dev/null || true

# Keep only last 7 days
find $BACKUP_DIR -name '*.rdb' -mtime +7 -delete
find $BACKUP_DIR -name '*.bak' -mtime +7 -delete
find $BACKUP_DIR -name '*.yaml' -mtime +7 -delete

echo "[$(date)] Backup done → $BACKUP_DIR" >> /var/log/openclaw-backup.log

# Solsbot Helper

Discord bot that bridges Sol's RNG game notifications to Discord servers. Users register their Roblox usernames, and when they get auras in-game, notifications are posted to subscribed servers via webhooks.

Add the bot: https://discord.com/oauth2/authorize?client_id=1457837557516603465
## Quick Start

## Production Deployment (Kubernetes)

### Prerequisites
- Kubernetes cluster (tested on k3s)
- `kubectl` configured
- Docker Hub account (or other registry)
- MariaDB/MySQL database (external or in-cluster)

### Step-by-Step

1. **Create namespace and secrets:**
```bash
kubectl apply -f k8s/namespace.yaml

# Copy and edit secrets template
cp k8s/secrets.yaml.example k8s/secrets.yaml
# Edit k8s/secrets.yaml with base64-encoded values:
# echo -n 'your-value' | base64

kubectl apply -f k8s/secrets.yaml
```

2. **Configure environment:**
```bash
# Edit k8s/configmap.yaml
# Set ENVIRONMENT to "production" or "development"
kubectl apply -f k8s/configmap.yaml
```

3. **Build and push Docker image:**
```bash
docker build -t yourusername/solsbot-helper:latest .
docker push yourusername/solsbot-helper:latest
```

4. **Update deployment image:**
```bash
# Edit k8s/deployment.yaml line 37:
# image: yourusername/solsbot-helper:latest
```

5. **Deploy:**
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/pdb.yaml  # Optional: Pod Disruption Budget
```

6. **Verify:**
```bash
kubectl get pods -n solsbot
kubectl logs -f deployment/solsbot-helper -n solsbot
```

---

### Local Development

1. Clone and set up environment:
```bash
git clone https://github.com/diamivore/Solsbot-Helper.git
cd Solsbot-Helper
python3 -m venv .
source bin/activate
pip install -r requirements.txt
```

2. Configure `.env`:
```bash
cp .env.example .env
# Edit .env with your values
```

Required variables:
- `ENVIRONMENT` - `development` or `production`
- `BOT_TOKEN_DEV` - Discord bot token for development
- `DEV_DB_URL` - MariaDB/MySQL connection string
- `SOLS_BOT_TOKEN` - API token from mongoosee.com

3. Run:
```bash
python3 main.py          # Normal mode
python3 main.py -v       # Verbose logging
python3 main.py -s       # Silent (no logs)
```
---

## Database Setup

The bot requires MariaDB/MySQL. Install and configure locally:

```bash
# Install MariaDB
sudo apt install mariadb-server  # Debian/Ubuntu
brew install mariadb             # macOS

# Start service
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Create database and user
sudo mysql -e "
CREATE DATABASE solsbot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'solsbot'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON solsbot_db.* TO 'solsbot'@'localhost';
FLUSH PRIVILEGES;
"
```

Connection string for `.env`:
```
DEV_DB_URL=mysql://solsbot:your-password@localhost:3306/solsbot_db
```

Tables are auto-created on first run via Tortoise ORM.

---

## Updating

### Local
```bash
git pull
pip install -r requirements.txt
python3 main.py
```

### Kubernetes
```bash
docker build -t yourusername/solsbot-helper:latest .
docker push yourusername/solsbot-helper:latest
kubectl rollout restart deployment/solsbot-helper -n solsbot
```

---

## Environment Modes

| Mode | Bot Token | Database | Use Case |
|------|-----------|----------|----------|
| `development` | `BOT_TOKEN_DEV` | `DEV_DB_URL` | Testing with separate bot |
| `production` | `BOT_TOKEN` | `DB_URL` | Live deployment |

Local `.env` defaults to development. Kubernetes ConfigMap defaults to production.

---

## Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OWNER_WEBHOOK_DEBUG_URL` | Discord webhook URL for error notifications. When set, unhandled command errors are posted here with full stack traces. | None (disabled) |
| `TZ` | Timezone for log timestamps (e.g., `America/New_York`, `UTC`) | System default |

Set these in `.env` for local development or `k8s/configmap.yaml` for Kubernetes.

---

## Bot Commands

### User Commands
| Command | Description |
|---------|-------------|
| `/add_username [name]` | Register a Roblox username |
| `/remove_username [name]` | Unregister a username |
| `/view_usernames` | List your registered usernames |
| `/add_server [id]` | Subscribe to notifications in a server |
| `/remove_server [id]` | Unsubscribe from a server |
| `/view_servers` | List your subscribed servers |
| `/help` | Show all commands |

### Admin Commands (Requires Administrator)
| Command | Description |
|---------|-------------|
| `/admin toggle_notifications` | Enable/disable notifications for server |
| `/admin add_subscriber_webhook [url]` | Set webhook for notifications |
| `/admin add_notification_role [id]` | Require role for posting |
| `/admin view_info` | Show server configuration |

---

## Project Structure

```
├── main.py              # Entry point, bot initialization
├── cogs/                # Discord command handlers
│   ├── admin.py         # Admin commands
│   ├── errors.py        # Error handling
│   ├── help.py          # Help command
│   └── user.py          # User commands
├── infrastructure/      # External connections
│   ├── database.py      # Tortoise ORM wrapper
│   └── websocket.py     # WebSocket client
├── models/              # Database models
├── repositories/        # Data access layer
├── services/            # Business logic
└── k8s/                 # Kubernetes manifests
```

---

## Troubleshooting

**Bot not starting:**
- Check logs: `kubectl logs deployment/solsbot-helper -n solsbot`
- Verify secrets: `kubectl get secrets -n solsbot`
- Test database connection manually

**Notifications not posting:**
- Ensure `/admin toggle_notifications` is enabled
- Check webhook URL is valid
- Verify user has required role (if set)

**WebSocket disconnects:**
- Check `SOLS_BOT_TOKEN` is valid
- API may be rate limiting - bot auto-reconnects

---

## License

MIT License - see [LICENSE](LICENSE)

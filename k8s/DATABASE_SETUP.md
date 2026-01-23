# Database Setup

The bot requires MariaDB 10.5+ or MySQL 8.0+.

## Local Installation

### Linux (Debian/Ubuntu)

```bash
# Install
sudo apt update
sudo apt install mariadb-server

# Start and enable
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Secure installation (optional but recommended)
sudo mysql_secure_installation
```

### macOS

```bash
brew install mariadb
brew services start mariadb
```

### Windows

Download from https://mariadb.org/download/ and run the installer.

---

## Create Database and User

```bash
sudo mysql
```

```sql
CREATE DATABASE solsbot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'solsbot'@'localhost' IDENTIFIED BY 'your-secure-password';
GRANT ALL PRIVILEGES ON solsbot_db.* TO 'solsbot'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## Connection String

For local `.env`:
```
DEV_DB_URL=mysql://solsbot:your-secure-password@localhost:3306/solsbot_db
```

For Kubernetes secrets (if DB is on same host as cluster):
```
mysql://solsbot:your-secure-password@host.docker.internal:3306/solsbot_db
```

Or use your machine's local IP (e.g., `192.168.1.x`).

---

## Kubernetes In-Cluster Option

If you want MariaDB running inside K8s, apply `k8s/mysql.yaml`:

```bash
kubectl apply -f k8s/mysql.yaml
```

Then use this connection string:
```
mysql://solsbot:password@mysql-service.solsbot.svc.cluster.local:3306/solsbot_db
```

Edit the passwords in `mysql.yaml` before deploying.

---

## Test Connection

```bash
mysql -h localhost -u solsbot -p solsbot_db
```

Or with Python:
```python
import asyncio, asyncmy

async def test():
    conn = await asyncmy.connect(
        host='localhost', port=3306,
        user='solsbot', password='your-password',
        db='solsbot_db'
    )
    print('Connected!')
    await conn.ensure_closed()

asyncio.run(test())
```

---

## Schema

Tables are auto-created on first bot startup. No manual schema setup needed.

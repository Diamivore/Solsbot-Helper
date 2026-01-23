# Solsbot Helper - Kubernetes Deployment Guide

This guide covers deploying the Solsbot Helper Discord bot to Kubernetes.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Namespace: solsbot                      │  │
│  │                                                            │  │
│  │  ┌──────────────────┐     ┌─────────────────────────────┐ │  │
│  │  │   Deployment     │     │      External Services      │ │  │
│  │  │  (1 replica)     │     │                             │ │  │
│  │  │                  │────▶│  • Discord API (HTTPS)      │ │  │
│  │  │  ┌────────────┐  │     │  • WebSocket API (WSS)      │ │  │
│  │  │  │  Pod       │  │     │  • MySQL/MariaDB            │ │  │
│  │  │  │            │  │     │                             │ │  │
│  │  │  │ solsbot    │  │     └─────────────────────────────┘ │  │
│  │  │  │ container  │  │                                     │  │
│  │  │  └────────────┘  │                                     │  │
│  │  └──────────────────┘                                     │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
│  │  │   Secret     │  │  ConfigMap   │  │       PDB        │ │  │
│  │  │              │  │              │  │                  │ │  │
│  │  │ • DB_URL     │  │ • ENVIRONMENT│  │ minAvailable: 0  │ │  │
│  │  │ • BOT_TOKEN  │  │ • TZ         │  │                  │ │  │
│  │  │ • SOLS_TOKEN │  │              │  │                  │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes cluster (v1.25+)
- `kubectl` configured to access your cluster
- Docker registry access (Docker Hub, GCR, ECR, etc.)
- MySQL/MariaDB database (managed service or self-hosted)

## Quick Start

### 1. Build and Push Docker Image

```bash
# Build the image
docker build -t your-registry/solsbot-helper:latest .

# Push to registry
docker push your-registry/solsbot-helper:latest
```

### 2. Create Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### 3. Create Secrets

**Option A: Using kubectl (Recommended)**

```bash
kubectl create secret generic solsbot-secrets \
  --namespace=solsbot \
  --from-literal=DB_URL='mysql://user:password@host:3306/database' \
  --from-literal=BOT_TOKEN='your-discord-bot-token' \
  --from-literal=SOLS_BOT_TOKEN='your-sols-api-token'
```

**Option B: Edit and apply secrets.yaml**

```bash
# Edit k8s/secrets.yaml with your values (base64 encoded)
kubectl apply -f k8s/secrets.yaml
```

### 4. Update Deployment Image

Edit `k8s/deployment.yaml` and update the image reference:

```yaml
image: your-registry/solsbot-helper:latest
```

### 5. Deploy Everything

```bash
# Apply all manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml  # Skip if using Option A above
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/pdb.yaml

# Or apply all at once
kubectl apply -f k8s/
```

### 6. Verify Deployment

```bash
# Check pod status
kubectl get pods -n solsbot

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=solsbot-helper -n solsbot --timeout=120s

# Check deployment status
kubectl get deployment solsbot-helper -n solsbot
```

## Operations Guide

### Viewing Logs

```bash
# Stream live logs
kubectl logs -f deployment/solsbot-helper -n solsbot

# View last 100 lines
kubectl logs deployment/solsbot-helper -n solsbot --tail=100

# View logs from previous container (after restart)
kubectl logs deployment/solsbot-helper -n solsbot --previous

# With timestamps
kubectl logs deployment/solsbot-helper -n solsbot --timestamps
```

### Debugging

```bash
# Describe pod for events and status
kubectl describe pod -l app.kubernetes.io/name=solsbot-helper -n solsbot

# Execute shell in running container (limited - read-only filesystem)
kubectl exec -it deployment/solsbot-helper -n solsbot -- /bin/bash

# Check environment variables
kubectl exec deployment/solsbot-helper -n solsbot -- env | grep -E 'DB_URL|BOT_TOKEN|SOLS'

# Check if process is running
kubectl exec deployment/solsbot-helper -n solsbot -- pgrep -f 'python.*main.py'
```

### Restarting the Bot

```bash
# Rollout restart (graceful)
kubectl rollout restart deployment/solsbot-helper -n solsbot

# Force delete pod (not graceful - use sparingly)
kubectl delete pod -l app.kubernetes.io/name=solsbot-helper -n solsbot

# Scale down and up (full restart)
kubectl scale deployment solsbot-helper -n solsbot --replicas=0
kubectl scale deployment solsbot-helper -n solsbot --replicas=1
```

### Updating the Bot

```bash
# Build new image with tag
docker build -t your-registry/solsbot-helper:v1.2.0 .
docker push your-registry/solsbot-helper:v1.2.0

# Update deployment
kubectl set image deployment/solsbot-helper \
  solsbot=your-registry/solsbot-helper:v1.2.0 -n solsbot

# Watch rollout status
kubectl rollout status deployment/solsbot-helper -n solsbot

# Rollback if needed
kubectl rollout undo deployment/solsbot-helper -n solsbot
```

### Scaling (DON'T!)

⚠️ **WARNING**: This bot MUST run as a single replica!

```bash
# DO NOT RUN THIS:
# kubectl scale deployment solsbot-helper -n solsbot --replicas=2  # BAD!
```

Multiple replicas would cause:
- Duplicate Discord notifications
- WebSocket connection conflicts
- Database race conditions

## Database Setup

The bot needs MariaDB/MySQL. For Kubernetes, you can either:

1. **Run MariaDB on the same host** as your K8s cluster and use the host IP
2. **Deploy MariaDB in-cluster** using the StatefulSet in `k8s/mysql.yaml`

See [DATABASE_SETUP.md](DATABASE_SETUP.md) for detailed instructions.

Connection string format:
```
mysql+asyncmy://solsbot:password@host:3306/solsbot_db
```

## Health Check Strategy

Since the bot doesn't expose HTTP endpoints, we use exec probes:

| Probe | Purpose | Interval | Failure Threshold |
|-------|---------|----------|-------------------|
| **Startup** | Allow time for initial connections | 10s | 30 (5 min total) |
| **Liveness** | Detect hung processes | 30s | 3 |
| **Readiness** | Verify bot is operational | 15s | 3 |

All probes use `pgrep -f 'python.*main.py'` to verify the process is running.

The bot also writes a health file to `/tmp/health` every 10 seconds for Kubernetes to check.

## Troubleshooting

### Pod Stuck in Pending

```bash
kubectl describe pod -l app.kubernetes.io/name=solsbot-helper -n solsbot
```

Common causes:
- Insufficient cluster resources
- Image pull errors (check registry credentials)
- PersistentVolume issues

### Pod CrashLoopBackOff

```bash
# Check logs
kubectl logs -l app.kubernetes.io/name=solsbot-helper -n solsbot --previous

# Common causes:
# - Missing/invalid environment variables
# - Database connection failures
# - Invalid bot token
```

### WebSocket Connection Failures

If the bot can't connect to `wss://api.mongoosee.com`:

1. Check NetworkPolicy allows egress on port 443
2. Verify DNS resolution works
3. Check if API is up externally

```bash
# Test DNS from pod
kubectl exec deployment/solsbot-helper -n solsbot -- nslookup api.mongoosee.com

# Check network policy
kubectl get networkpolicy -n solsbot
```

### Database Connection Issues

```bash
# Verify DB_URL secret is set correctly
kubectl get secret solsbot-secrets -n solsbot -o jsonpath='{.data.DB_URL}' | base64 -d

# Test connectivity (requires mysql client in image - add if needed)
kubectl exec deployment/solsbot-helper -n solsbot -- python -c "
import asyncio
import asyncmy
async def test():
    conn = await asyncmy.connect(host='mysql-service', user='solsbot', password='pass', db='solsbot_db')
    print('Connected!')
    await conn.close()
asyncio.run(test())
"
```

## Resource Tuning

Default resources are conservative. Adjust based on monitoring:

| Metric | Default Request | Default Limit | Notes |
|--------|-----------------|---------------|-------|
| Memory | 128Mi | 512Mi | Increase if OOMKilled |
| CPU | 100m | 500m | Usually sufficient for bot workload |

Monitor with:

```bash
kubectl top pod -n solsbot
```

## Security Considerations

1. **Secrets Management**: Consider using external secrets managers (Vault, AWS Secrets Manager)
2. **Network Policy**: Included in `pdb.yaml` - restricts egress to required services only
3. **Non-root User**: Container runs as UID 1000
4. **Read-only Filesystem**: Only `/tmp` is writable
5. **No Privilege Escalation**: Explicitly disabled

## Monitoring & Alerting

Consider adding:

1. **Prometheus metrics** - Add `/metrics` endpoint to bot
2. **Grafana dashboards** - Visualize bot health
3. **PagerDuty/Slack alerts** - On pod restarts or failures

Example Prometheus rule for alerting:

```yaml
groups:
  - name: solsbot
    rules:
      - alert: SolsbotDown
        expr: kube_deployment_status_replicas_available{deployment="solsbot-helper"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Solsbot Helper is down"
```

## Cleanup

To remove all resources:

```bash
kubectl delete -f k8s/
kubectl delete namespace solsbot
```

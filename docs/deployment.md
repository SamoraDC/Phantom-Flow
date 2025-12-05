# Deployment Guide

This guide covers deploying QuantumFlow to Fly.io and configuring the automated workflows.

## Prerequisites

- [Fly.io account](https://fly.io)
- [GitHub account](https://github.com) with repository access
- `flyctl` CLI installed

## Initial Setup

### 1. Install Fly.io CLI

```bash
curl -L https://fly.io/install.sh | sh
```

### 2. Authenticate

```bash
flyctl auth login
```

### 3. Create the App

```bash
flyctl apps create quantumflow-hft
```

### 4. Create Persistent Volume

```bash
flyctl volumes create quantumflow_data --size 1 --region gru
```

### 5. Set Secrets

```bash
flyctl secrets set TELEGRAM_BOT_TOKEN="your_token"
flyctl secrets set TELEGRAM_CHAT_ID="your_chat_id"
```

## Deployment

### Manual Deploy

```bash
flyctl deploy
```

### Automated Deploy (via GitHub Actions)

1. Get Fly.io API token:
   ```bash
   flyctl auth token
   ```

2. Add to GitHub Secrets:
   - `FLY_API_TOKEN`: Your Fly.io token

3. Push to `main` branch to trigger deploy

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SYMBOLS` | Trading symbols | `BTCUSDT,ETHUSDT` |
| `DATABASE_URL` | SQLite path | `sqlite:///data/trades.db` |
| `RISK_MAX_POSITION` | Max position size | `1.0` |
| `RISK_MAX_DRAWDOWN` | Max drawdown % | `0.05` |
| `TIMEZONE` | Shabbat timezone | `America/Sao_Paulo` |

### Scaling

The default configuration uses:
- 1 shared CPU
- 256MB RAM
- 1GB persistent storage

For higher throughput:
```bash
flyctl scale vm shared-cpu-2x --memory 512
```

## Monitoring

### View Logs

```bash
flyctl logs
```

### SSH Access

```bash
flyctl ssh console
```

### Health Check

```bash
curl https://quantumflow-hft.fly.dev/health
```

## GitHub Actions Workflows

### CI (`ci.yml`)

Runs on every push:
- Rust tests and linting
- OCaml tests
- Python tests
- Docker build validation

### Deploy (`deploy.yml`)

Runs on push to `main`:
- Deploys to Fly.io
- Runs health check
- Alerts on failure

### Daily Report (`daily-report.yml`)

Runs daily at 00:00 UTC:
- Downloads database from Fly.io
- Generates performance charts
- Updates README
- Commits changes

### Health Check (`health-check.yml`)

Runs every 15 minutes:
- Checks API health
- Restarts if unhealthy
- Sends Telegram alert on failure

## Troubleshooting

### App Won't Start

1. Check logs: `flyctl logs`
2. Verify volume mount: `flyctl volumes list`
3. Check secrets: `flyctl secrets list`

### Database Issues

1. SSH into container: `flyctl ssh console`
2. Check database: `sqlite3 /data/trades.db ".tables"`
3. Reset if needed: `rm /data/trades.db`

### Reconnection Issues

The Rust component has automatic reconnection with exponential backoff. If issues persist:
1. Check Binance API status
2. Verify network connectivity
3. Restart: `flyctl apps restart quantumflow-hft`

## Backup & Recovery

### Export Database

```bash
flyctl ssh console -C "cat /data/trades.db" > backup.db
```

### Restore Database

```bash
cat backup.db | flyctl ssh console -C "cat > /data/trades.db"
```

## Cost Optimization

Fly.io free tier includes:
- 3 shared-cpu VMs
- 160GB outbound transfer
- Unlimited inbound

The default configuration stays within free tier limits.

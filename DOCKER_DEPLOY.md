# Docker Deployment Guide

Complete guide for deploying the ShopGuard AI Trading Platform using Docker.

## Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env with your API keys
nano .env

# 3. Start all services
docker-compose up -d

# 4. View logs
docker-compose logs -f trading-app

# 5. Access services
# - Dashboard: http://localhost:5001
# - API Server: http://localhost:8000
# - Jupyter Lab: http://localhost:8888
# - Grafana: http://localhost:3000 (with monitoring profile)
```

## Services

### Core Services

1. **trading-app** - Main trading application
   - Port: 5000 (internal), 8000 (API)
   - Interactive trading assistant
   - AI-powered trading logic

2. **dashboard** - Web dashboard
   - Port: 5001
   - Real-time monitoring
   - Strategy management
   - Login: admin/quanttrader2024

3. **postgres** - TimescaleDB database
   - Port: 5432
   - Time-series optimized storage
   - Market data, trades, positions

4. **redis** - Cache and message queue
   - Port: 6379
   - Real-time data caching
   - Message passing

5. **jupyter** - Research environment
   - Port: 8888
   - Interactive analysis
   - Strategy development

### Optional Services (Monitoring Profile)

6. **prometheus** - Metrics collection
   - Port: 9090

7. **grafana** - Visualization dashboard
   - Port: 3000
   - Username: admin
   - Password: Set in .env as GRAFANA_PASSWORD

## Commands

### Start Services

```bash
# Start all core services
docker-compose up -d

# Start with monitoring (Prometheus + Grafana)
docker-compose --profile monitoring up -d

# Start specific service
docker-compose up -d trading-app

# Build and start (after code changes)
docker-compose up -d --build
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f trading-app
docker-compose logs -f dashboard

# Last 100 lines
docker-compose logs --tail=100 trading-app
```

### Manage Services

```bash
# Restart a service
docker-compose restart trading-app

# Execute command in container
docker-compose exec trading-app python quick_start.py --test

# Access shell
docker-compose exec trading-app /bin/bash

# View running services
docker-compose ps

# View resource usage
docker stats
```

## Configuration

### Environment Variables

Edit `.env` file:

```bash
# Trading Configuration
TRADING_MODE=paper  # paper or live
DEFAULT_BROKER=paper
INITIAL_CAPITAL=100000

# API Keys
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
BINANCE_API_KEY=your_key_here
BINANCE_SECRET_KEY=your_secret_here

# Database
POSTGRES_USER=trader
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=quant_research

# Monitoring
GRAFANA_PASSWORD=your_secure_password
```

### Volumes

Data is persisted in Docker volumes:

- `postgres-data` - Database storage
- `redis-data` - Redis persistence
- `prometheus-data` - Metrics history
- `grafana-data` - Dashboards & settings

Local mounted volumes:
- `./data` - Trading data, models
- `./logs` - Application logs
- `./config` - Configuration files (read-only)
- `./notebooks` - Jupyter notebooks

## Production Deployment

### Security Hardening

1. **Change default passwords**
   ```bash
   # In .env
   POSTGRES_PASSWORD=strong_random_password
   GRAFANA_PASSWORD=another_strong_password
   ```

2. **Update dashboard credentials**
   Edit `webapp/app.py` and change:
   ```python
   USERS = {
       "admin": hashlib.sha256("your_new_password".encode()).hexdigest()
   }
   ```

3. **Use HTTPS**
   - Add reverse proxy (nginx/traefik)
   - Configure SSL certificates
   - Example nginx config:
   ```nginx
   server {
       listen 443 ssl;
       server_name trading.yourdomain.com;

       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;

       location / {
           proxy_pass http://localhost:5001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

4. **Firewall rules**
   ```bash
   # Only expose necessary ports
   # Block PostgreSQL (5432) and Redis (6379) from external access
   ufw allow 443/tcp
   ufw allow 80/tcp
   ufw deny 5432/tcp
   ufw deny 6379/tcp
   ```

### Resource Limits

Add to `docker-compose.yml` for each service:

```yaml
services:
  trading-app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Backup Strategy

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U trader quant_research > backup.sql

# Backup volumes
docker run --rm -v shopguard_postgres-data:/data -v $(pwd):/backup \
    alpine tar czf /backup/postgres-backup.tar.gz /data

# Restore
docker run --rm -v shopguard_postgres-data:/data -v $(pwd):/backup \
    alpine tar xzf /backup/postgres-backup.tar.gz -C /
```

### Monitoring

Enable monitoring profile:

```bash
docker-compose --profile monitoring up -d
```

Access:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Import pre-built dashboards in Grafana:
1. Trading Performance Dashboard
2. System Metrics Dashboard
3. Risk Analytics Dashboard

### Auto-restart

Services are configured with `restart: unless-stopped` which will:
- Auto-restart on failure
- Start on system boot
- Stop only when explicitly stopped

### Log Rotation

Configure log rotation to prevent disk space issues:

```bash
# /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Restart Docker:
```bash
sudo systemctl restart docker
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs trading-app

# Check container status
docker-compose ps

# Rebuild
docker-compose build --no-cache trading-app
docker-compose up -d trading-app
```

### Database connection errors

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U trader -d quant_research
```

### Out of memory

```bash
# Check resource usage
docker stats

# Increase Docker memory limit in Docker Desktop settings
# Or add memory limits to docker-compose.yml
```

### Network issues

```bash
# Recreate network
docker-compose down
docker network prune
docker-compose up -d
```

## Development Workflow

```bash
# 1. Make code changes locally

# 2. Rebuild and restart
docker-compose up -d --build trading-app

# 3. View logs
docker-compose logs -f trading-app

# 4. Run tests
docker-compose exec trading-app pytest

# 5. Access shell for debugging
docker-compose exec trading-app /bin/bash
```

## CI/CD Integration

Example GitHub Actions workflow (see `.github/workflows/docker.yml`):

```yaml
name: Docker Build and Push

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build image
        run: docker build -t shopguard:latest .
      - name: Run tests
        run: docker run shopguard:latest pytest
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/shopguard/issues
- Documentation: See README.md
- Logs: `docker-compose logs -f`

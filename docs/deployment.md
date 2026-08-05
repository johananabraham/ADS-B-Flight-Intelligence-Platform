# Deployment Guide

This guide covers deploying the ADS-B Flight Intelligence Platform to production.

## Prerequisites

- Docker and Docker Compose installed
- Domain name (optional, for HTTPS)
- SSL certificate (use Let's Encrypt for free certificates)

## Quick Start (Development)

```bash
# Clone and start demo mode
git clone https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform.git
cd ADS-B-Flight-Intelligence-Platform

docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build -d
```

## Production Deployment

### 1. Configure Environment

Create a `.env` file with production settings:

```bash
# Required
POSTGRES_PASSWORD=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)
LLM_API_KEY=your_llm_api_key

# Optional
ANTHROPIC_API_KEY=your_anthropic_key
OPENSKY_ENABLED=true
OPENSKY_CLIENT_ID=your_opensky_id
OPENSKY_CLIENT_SECRET=your_opensky_secret

# For demo/simulation mode
OBSERVATION_SOURCE_TYPE=SIMULATION
```

### 2. Build and Deploy

```bash
# Production deployment
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# Apply database migrations
docker compose exec backend alembic -c alembic.ini upgrade head

# Verify deployment
curl http://localhost:8000/health
curl http://localhost:80/health
```

### 3. Configure HTTPS

For production, use a reverse proxy with SSL termination:

#### Option A: nginx with Let's Encrypt

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://localhost:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### Option B: Caddy (auto-HTTPS)

```caddyfile
your-domain.com {
    reverse_proxy /api/* localhost:8000
    reverse_proxy /ws localhost:8000
    reverse_proxy localhost:5173
}
```

## Security Checklist

### Before Deployment

- [ ] Strong POSTGRES_PASSWORD set (not "password")
- [ ] SECRET_KEY generated with `openssl rand -hex 32`
- [ ] PostgreSQL port (5432) not exposed to internet
- [ ] All API keys stored in environment variables, not code
- [ ] HTTPS enabled for all public traffic

### After Deployment

- [ ] Verify health endpoints respond
- [ ] Test WebSocket connections work
- [ ] Check logs for errors: `docker compose logs -f`
- [ ] Run security audit: `docker compose exec backend pip-audit -r requirements.txt`

## Monitoring

### Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Backend liveness |
| `GET /api/v1/safety/ingestion/status` | Data ingestion status |
| `GET /api/v1/corroboration/source-health` | External source health |

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail 100 backend
```

### Database Backups

```bash
# Create backup
docker compose exec db pg_dump -U postgres adsb_intel > backup_$(date +%Y%m%d).sql

# Restore backup
cat backup_20260805.sql | docker compose exec -T db psql -U postgres adsb_intel
```

## Scaling Considerations

### Current Limits

The default configuration supports:
- ~10 concurrent receivers
- ~1000 tracked aircraft
- ~100 concurrent WebSocket connections

### Scaling Options

1. **Vertical**: Increase container memory limits in `docker-compose.prod.yml`
2. **Database**: Move PostgreSQL to managed service (AWS RDS, Cloud SQL)
3. **Load balancing**: Add nginx upstream for multiple backend instances
4. **Message queue**: Add Redis/RabbitMQ for ingestion scaling

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs backend

# Check container status
docker compose ps

# Rebuild from scratch
docker compose down -v
docker compose up --build
```

### Database connection errors

```bash
# Verify database is healthy
docker compose exec db pg_isready -U postgres

# Check connection from backend
docker compose exec backend python -c "from app.core.database import engine; engine.connect()"
```

### WebSocket not connecting

1. Check that WebSocket path matches frontend config
2. Verify nginx/proxy WebSocket upgrade headers
3. Check firewall allows WebSocket connections

### High memory usage

1. Check container limits: `docker stats`
2. Reduce worker count in gunicorn/uvicorn
3. Add connection pooling for database

## Environment Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_PASSWORD` | Yes | - | Database password |
| `SECRET_KEY` | Yes | - | FastAPI session secret |
| `LLM_API_KEY` | Yes | - | LLM provider API key |
| `DATABASE_URL` | No | Auto | PostgreSQL connection URL |
| `ANTHROPIC_API_KEY` | No | - | Claude API key for summaries |
| `OPENSKY_ENABLED` | No | false | Enable OpenSky corroboration |
| `OPENSKY_CLIENT_ID` | No | - | OpenSky OAuth client ID |
| `OPENSKY_CLIENT_SECRET` | No | - | OpenSky OAuth secret |
| `OBSERVATION_SOURCE_TYPE` | No | LIVE_RF | Data source type |

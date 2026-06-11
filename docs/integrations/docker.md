# Docker Deployment Guide

This guide explains how to deploy the Meeting Transcript Summarizer using Docker.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+ (optional, for easier management)

## Quick Start

### Using Docker Compose (Recommended)

1. **Copy environment file:**
   ```bash
   cp .env.docker.example .env
   # Edit .env with your API keys
   ```

2. **Build and run:**
   ```bash
   docker-compose up -d
   ```

3. **View logs:**
   ```bash
   docker-compose logs -f
   ```

4. **Access the application:**
   - Frontend: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

5. **Stop the application:**
   ```bash
   docker-compose down
   ```

### Using Docker directly

1. **Build the image:**
   ```bash
   docker build -t meeting-summarizer .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     --name meeting-summarizer-app \
     -p 8000:8000 \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/.env:/app/.env:ro \
     meeting-summarizer
   ```

3. **View logs:**
   ```bash
   docker logs -f meeting-summarizer-app
   ```

4. **Stop the container:**
   ```bash
   docker stop meeting-summarizer-app
   docker rm meeting-summarizer-app
   ```

## Configuration

### Environment Variables

Create a `.env` file with your configuration (see `.env.docker.example`):

```bash
# Required API Keys
TRELLO_API_KEY=your_key
TRELLO_API_TOKEN=your_token
OPENAI_API_KEY=your_key

# Optional: Confluence
CONFLUENCE_URL=https://your-domain.atlassian.net
CONFLUENCE_USERNAME=your_email
CONFLUENCE_API_TOKEN=your_token
```

### Data Persistence

The `data/` directory is mounted as a volume to persist:
- Database (`meetings.db`)
- Processed transcripts
- Meeting summaries
- Trello board cache

## Docker Compose Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Rebuild and restart
docker-compose up -d --build

# Execute command in container
docker-compose exec meeting-summarizer bash

# View container status
docker-compose ps
```

## Production Deployment

### Using Docker Compose

1. **Set environment variables:**
   ```bash
   export TRELLO_API_KEY=your_key
   export TRELLO_API_TOKEN=your_token
   # ... other variables
   ```

2. **Run in detached mode:**
   ```bash
   docker-compose up -d
   ```

3. **Set up reverse proxy (nginx/traefik):**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

### Using Docker Swarm or Kubernetes

The Dockerfile is compatible with orchestration platforms. Use the same image and configure:
- Environment variables via secrets/configmaps
- Persistent volumes for data
- Health checks (already configured)
- Resource limits

## Health Checks

The container includes a health check that verifies the API is responding:

```bash
# Check health status
docker ps  # Look for "healthy" status

# Manual health check
curl http://localhost:8000/health
```

## Troubleshooting

### Container won't start

1. Check logs:
   ```bash
   docker-compose logs
   ```

2. Verify environment variables:
   ```bash
   docker-compose exec meeting-summarizer env
   ```

3. Check port availability:
   ```bash
   netstat -tuln | grep 8000
   ```

### Data not persisting

Ensure the data volume is mounted:
```bash
docker-compose exec meeting-summarizer ls -la /app/data
```

### Permission issues

If you encounter permission issues with the data directory:
```bash
sudo chown -R 1000:1000 data/
```

## Building for Different Platforms

### Build for specific architecture:
```bash
docker buildx build --platform linux/amd64 -t meeting-summarizer .
```

### Multi-platform build:
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t meeting-summarizer .
```

## Image Size Optimization

The current image uses `python:3.12-slim` for a smaller footprint. For even smaller images, consider:
- Multi-stage builds
- Alpine Linux base
- Removing unnecessary system packages

## Security Notes

1. **Never commit `.env` files** - Use secrets management in production
2. **Use read-only mounts** for configuration files
3. **Run as non-root user** (add to Dockerfile if needed)
4. **Keep base images updated** - Regularly rebuild with latest base images


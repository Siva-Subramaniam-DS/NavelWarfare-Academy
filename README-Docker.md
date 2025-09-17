# Discord Bot Docker Deployment Guide

This guide will help you deploy your Discord bot using Docker without modifying any existing code.

## 📋 Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed on your system
- [Docker Compose](https://docs.docker.com/compose/install/) installed
- Your Discord bot token

## 🚀 Quick Start

### 1. Set up Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example file
cp env.example .env

# Edit the .env file with your bot token
DISCORD_TOKEN=your_actual_bot_token_here
```

### 2. Run the Bot

#### Option A: Using the provided scripts

**On Linux/Mac:**
```bash
chmod +x docker-run.sh
./docker-run.sh
```

**On Windows:**
```cmd
docker-run.bat
```

#### Option B: Manual Docker commands

```bash
# Build and start the container
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

## 📁 File Structure

```
Discord Bots/
├── app.py                 # Main bot code (unchanged)
├── requirements.txt       # Python dependencies
├── Templates/            # Image templates (mounted as volume)
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose configuration
├── .dockerignore        # Files to exclude from Docker build
├── docker-run.sh        # Linux/Mac startup script
├── docker-run.bat       # Windows startup script
├── env.example          # Environment variables template
└── README-Docker.md     # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Your Discord bot token | ✅ Yes |

### Volume Mounts

- `./Templates:/app/Templates` - Persists your template images
- `./logs:/app/logs` - Persists bot logs (if implemented)

### Resource Limits

- Memory: 256MB reserved, 512MB limit
- CPU: No specific limits (uses Docker defaults)

## 🛠️ Docker Commands

### Basic Operations

```bash
# Start the bot
docker-compose up -d

# Stop the bot
docker-compose down

# Restart the bot
docker-compose restart

# View logs
docker-compose logs -f

# View logs for last 100 lines
docker-compose logs --tail=100 -f
```

### Development Commands

```bash
# Rebuild the image (after code changes)
docker-compose up --build -d

# Run in foreground (for debugging)
docker-compose up

# Access container shell
docker-compose exec discord-bot bash

# View container status
docker-compose ps
```

### Maintenance Commands

```bash
# Remove all containers and images
docker-compose down --rmi all --volumes

# Clean up unused Docker resources
docker system prune -a

# Update the bot (pull latest code first)
git pull
docker-compose up --build -d
```

## 🔍 Troubleshooting

### Common Issues

1. **Bot not starting**
   ```bash
   # Check logs
   docker-compose logs discord-bot
   
   # Check if token is set
   docker-compose exec discord-bot env | grep DISCORD_TOKEN
   ```

2. **Permission errors**
   ```bash
   # Fix file permissions
   chmod +x docker-run.sh
   ```

3. **Port conflicts**
   - The bot doesn't use any external ports, so this shouldn't be an issue

4. **Memory issues**
   - Increase memory limits in `docker-compose.yml` if needed

### Health Checks

The container includes health checks to ensure the bot is running properly:

```bash
# Check health status
docker-compose ps

# View health check logs
docker inspect discord-bot | grep -A 10 "Health"
```

## 📊 Monitoring

### Log Management

- Logs are automatically rotated (max 10MB, keep 3 files)
- View real-time logs: `docker-compose logs -f`
- Logs are stored in `./logs/` directory

### Resource Monitoring

```bash
# Monitor resource usage
docker stats discord-bot

# View container details
docker inspect discord-bot
```

## 🔄 Updates

To update your bot:

1. Pull the latest code: `git pull`
2. Rebuild and restart: `docker-compose up --build -d`
3. Check logs: `docker-compose logs -f`

## 🚨 Security Notes

- Never commit your `.env` file to version control
- The `.env` file is already in `.dockerignore` and `.gitignore`
- Keep your Discord bot token secure
- Regularly update Docker images and dependencies

## 📞 Support

If you encounter issues:

1. Check the logs: `docker-compose logs discord-bot`
2. Verify your Discord token is correct
3. Ensure Docker and Docker Compose are properly installed
4. Check that all required files are present

## 🎯 Benefits of Docker Deployment

- ✅ **Consistent Environment**: Same setup across different machines
- ✅ **Easy Deployment**: One command to start/stop
- ✅ **Isolation**: Bot runs in its own container
- ✅ **Scalability**: Easy to scale or migrate
- ✅ **No Code Changes**: Your existing code works unchanged
- ✅ **Resource Management**: Built-in memory and CPU limits
- ✅ **Health Monitoring**: Automatic health checks
- ✅ **Log Management**: Structured logging with rotation

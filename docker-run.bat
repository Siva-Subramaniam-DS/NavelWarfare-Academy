@echo off
REM Discord Bot Docker Runner Script for Windows
REM This script helps you run the Discord bot in Docker

echo 🎮 Discord Bot Docker Runner
echo ============================

REM Check if .env file exists
if not exist .env (
    echo ❌ .env file not found!
    echo Please create a .env file with your Discord bot token:
    echo DISCORD_TOKEN=your_bot_token_here
    pause
    exit /b 1
)

REM Check if DISCORD_TOKEN is set in .env
findstr /C:"DISCORD_TOKEN=" .env >nul
if errorlevel 1 (
    echo ❌ DISCORD_TOKEN not found in .env file!
    echo Please add your Discord bot token to the .env file:
    echo DISCORD_TOKEN=your_bot_token_here
    pause
    exit /b 1
)

echo ✅ Environment variables loaded
echo 🤖 Starting Discord bot in Docker...

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Run with docker-compose
docker-compose up --build -d

if errorlevel 1 (
    echo ❌ Failed to start the bot!
    echo Please check your Docker installation and try again.
    pause
    exit /b 1
)

echo ✅ Bot started successfully!
echo 📊 To view logs: docker-compose logs -f
echo 🛑 To stop: docker-compose down
echo 🔄 To restart: docker-compose restart
pause

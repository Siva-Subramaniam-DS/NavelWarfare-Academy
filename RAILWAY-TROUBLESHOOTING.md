# Railway Deployment Troubleshooting Guide

## 🚨 Common Railway Build Errors

### Error: "failed to solve: process did not complete successfully: exit code: 100"

This error occurs when system dependencies fail to install. Here are the solutions:

## 🔧 Solution 1: Use the Updated Dockerfile

The main `Dockerfile` has been updated with Railway-optimized settings:
- Added `--no-install-recommends` flag
- Added `fonts-liberation` package
- Added proper cleanup commands
- Removed problematic packages

## 🔧 Solution 2: Use Alternative Dockerfile

If the main Dockerfile still fails, rename the alternative:

```bash
# Rename the Railway-optimized Dockerfile
mv Dockerfile.railway Dockerfile

# Or update railway.json to use it
```

## 🔧 Solution 3: Minimal Dockerfile

If both fail, create this minimal version:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install only essential packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libfontconfig1 \
    libfreetype6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p Templates

ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
```

## 🔧 Solution 4: Remove Image Processing Dependencies

If image processing is causing issues, temporarily remove PIL dependencies:

1. **Edit requirements.txt** - comment out PIL-related packages:
   ```
   # Pillow>=10.0.0
   # pilmoji>=2.0.4
   ```

2. **Modify app.py** - add error handling for image processing:
   ```python
   try:
       from PIL import Image, ImageDraw, ImageFont
       from pilmoji import Pilmoji
       IMAGE_PROCESSING_AVAILABLE = True
   except ImportError:
       IMAGE_PROCESSING_AVAILABLE = False
       print("Warning: Image processing disabled")
   ```

## 🔧 Solution 5: Use Railway's Built-in Python Support

Instead of Docker, use Railway's native Python support:

1. **Remove Dockerfile and docker-compose.yml**
2. **Update railway.json**:
   ```json
   {
     "$schema": "https://railway.app/railway.schema.json",
     "build": {
       "builder": "NIXPACKS"
     },
     "deploy": {
       "startCommand": "python app.py",
       "restartPolicyType": "ON_FAILURE",
       "restartPolicyMaxRetries": 10
     }
   }
   ```

## 🔍 Debugging Steps

### 1. Check Railway Logs
- Go to Railway dashboard
- Click on your deployment
- Check "Build Logs" for specific error messages

### 2. Test Locally
```bash
# Test Docker build locally
docker build -t discord-bot .

# Run locally to test
docker run -e DISCORD_TOKEN=your_token discord-bot
```

### 3. Check Package Availability
Some packages might not be available in Railway's environment:
- `libgl1-mesa-glx` - Graphics library
- `libxrender-dev` - X11 rendering
- `libgomp1` - OpenMP runtime

## 🎯 Recommended Approach

1. **Try Solution 1** first (updated Dockerfile)
2. **If it fails**, try Solution 2 (alternative Dockerfile)
3. **If still failing**, use Solution 5 (native Python support)

## 📞 Getting Help

### Railway Support
- **Discord**: [Railway Discord](https://discord.gg/railway)
- **Documentation**: [docs.railway.app](https://docs.railway.app/)

### Common Issues
- **Network timeouts**: Railway has different network conditions
- **Package conflicts**: Some packages conflict in Railway's environment
- **Memory limits**: Free tier has memory constraints

## ✅ Success Indicators

When deployment succeeds, you should see:
```
✅ Bot is online as [Bot Name]
🆔 Bot ID: [Bot ID]
📊 Connected to [X] guild(s)
🎯 Bot is ready to receive commands!
```

## 🔄 Quick Fix Commands

```bash
# If using alternative Dockerfile
cp Dockerfile.railway Dockerfile

# If using native Python support
rm Dockerfile docker-compose.yml
# Update railway.json to use NIXPACKS

# Redeploy
git add .
git commit -m "Fix Railway deployment"
git push origin main
```

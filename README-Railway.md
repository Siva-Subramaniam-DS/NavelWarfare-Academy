# Discord Bot Railway Deployment Guide

This guide will help you deploy your Discord bot to Railway.com using Docker.

## 📋 Prerequisites

- [Railway Account](https://railway.app/) (free tier available)
- [GitHub Account](https://github.com/) (to connect your repository)
- Your Discord bot token

## 🚀 Step-by-Step Deployment

### Step 1: Prepare Your Repository

1. **Push your code to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Add Docker support for Railway deployment"
   git push origin main
   ```

2. **Ensure these files are in your repository**:
   - `Dockerfile`
   - `docker-compose.yml` (optional for Railway)
   - `railway.json`
   - `requirements.txt`
   - `app.py`
   - `Templates/` folder (with your images)

### Step 2: Connect to Railway

1. **Go to [Railway.app](https://railway.app/)**
2. **Sign in** with your GitHub account
3. **Click "New Project"**
4. **Select "Deploy from GitHub repo"**
5. **Choose your Discord bot repository**
6. **Click "Deploy Now"**

### Step 3: Configure Environment Variables

1. **In your Railway project dashboard**, go to the **Variables** tab
2. **Add your Discord bot token**:
   - **Variable Name**: `DISCORD_TOKEN`
   - **Value**: `your_actual_bot_token_here`
3. **Click "Add"** to save

### Step 4: Deploy

1. **Railway will automatically detect the Dockerfile** and start building
2. **Monitor the build logs** in the **Deployments** tab
3. **Wait for deployment to complete** (usually 2-5 minutes)

### Step 5: Verify Deployment

1. **Check the logs** in Railway dashboard
2. **Look for these success messages**:
   ```
   ✅ Bot is online as [Bot Name]
   🆔 Bot ID: [Bot ID]
   📊 Connected to [X] guild(s)
   🔄 Syncing slash commands...
   ✅ Synced [X] command(s)
   🎯 Bot is ready to receive commands!
   ```

## 🔧 Railway Configuration

### Automatic Configuration

The `railway.json` file automatically configures:
- **Docker Build**: Uses your Dockerfile
- **Restart Policy**: Automatically restarts on failure
- **Health Checks**: Built into the Docker container

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Your Discord bot token | ✅ Yes |

### Resource Allocation

Railway automatically allocates resources based on usage:
- **Free Tier**: 500 hours/month, 512MB RAM
- **Pro Tier**: More resources available

## 📊 Monitoring Your Bot

### View Logs

1. **Go to your Railway project**
2. **Click on your service**
3. **Go to "Logs" tab**
4. **View real-time logs**

### Check Status

1. **Dashboard shows deployment status**
2. **Green = Running, Red = Failed**
3. **Click on deployment for detailed logs**

## 🔄 Updates and Maintenance

### Automatic Updates

Railway automatically redeploys when you push to your GitHub repository.

### Manual Updates

1. **Make changes to your code**
2. **Commit and push to GitHub**:
   ```bash
   git add .
   git commit -m "Update bot functionality"
   git push origin main
   ```
3. **Railway automatically redeploys**

### Rollback

1. **Go to "Deployments" tab**
2. **Find the previous working deployment**
3. **Click "Redeploy"**

## 🛠️ Troubleshooting

### Common Issues

1. **Build Fails**
   - Check Railway build logs
   - Ensure all files are committed to GitHub
   - Verify Dockerfile syntax

2. **Bot Not Starting**
   - Check environment variables in Railway
   - Verify Discord token is correct
   - Check logs for error messages

3. **Missing Dependencies**
   - Ensure `requirements.txt` is up to date
   - Check if all imports are available

### Debug Commands

```bash
# Check Railway logs
railway logs

# Check environment variables
railway variables

# Redeploy manually
railway up
```

## 💰 Cost Management

### Free Tier Limits

- **500 hours/month** (about 20 days)
- **512MB RAM**
- **1GB storage**
- **Perfect for Discord bots**

### Pro Tier Benefits

- **Unlimited hours**
- **More RAM and storage**
- **Custom domains**
- **Team collaboration**

## 🔒 Security Best Practices

1. **Never commit your Discord token** to GitHub
2. **Use Railway environment variables** for secrets
3. **Regularly rotate your bot token**
4. **Monitor bot activity** through logs

## 📈 Scaling

### Automatic Scaling

Railway automatically scales based on:
- **CPU usage**
- **Memory usage**
- **Request volume**

### Manual Scaling

1. **Go to your service settings**
2. **Adjust resource allocation**
3. **Redeploy if needed**

## 🎯 Benefits of Railway Deployment

- ✅ **Zero Configuration**: Automatic Docker detection
- ✅ **Git Integration**: Automatic deployments from GitHub
- ✅ **Free Tier**: No cost for small bots
- ✅ **Global CDN**: Fast worldwide access
- ✅ **SSL Certificates**: Automatic HTTPS
- ✅ **Monitoring**: Built-in logs and metrics
- ✅ **Scalability**: Automatic resource management
- ✅ **Reliability**: 99.9% uptime guarantee

## 📞 Support

### Railway Support

- **Documentation**: [docs.railway.app](https://docs.railway.app/)
- **Discord**: [Railway Discord](https://discord.gg/railway)
- **Email**: support@railway.app

### Bot Issues

- Check Railway logs first
- Verify Discord bot permissions
- Ensure all environment variables are set

## 🚀 Quick Commands

```bash
# Install Railway CLI (optional)
npm install -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Deploy manually
railway up

# View logs
railway logs

# Open Railway dashboard
railway open
```

Your Discord bot is now ready for Railway deployment! 🎉

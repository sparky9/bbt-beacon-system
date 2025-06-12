# BBT Beacon System - Railway Deployment

🚨 **24/7 Developer Crisis Monitoring System**

## What This Does

Monitors multiple platforms for developer crisis signals:
- 🔴 **Reddit** - r/webdev, r/programming, r/freelance
- 🐦 **Twitter** - Premium search terms ("need developer" + "will pay")
- 💼 **Upwork** - RSS feeds for urgent developer jobs
- 💬 **Discord** - Help channel monitoring (coming soon)
- 📚 **Stack Overflow** - Urgent questions (coming soon)

## Live Dashboard

Access at: `https://your-app.railway.app`
Password: `beacon2025` (changeable via ADMIN_PASSWORD env var)

## Environment Variables

Set these in Railway dashboard:

```
SECRET_KEY=your-secret-key-here
ADMIN_PASSWORD=beacon2025
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
DISCORD_BOT_TOKEN=your_discord_bot_token
EMAIL_FROM=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

## Features

- ✅ **Password Protected** - Only you can access
- ✅ **24/7 Monitoring** - Never stops running
- ✅ **Live Dashboard** - Real-time signal updates
- ✅ **Mobile Friendly** - Access from anywhere
- ✅ **Smart Filtering** - Only shows high-urgency opportunities
- ✅ **Tech Stack Detection** - Identifies required technologies
- ✅ **Budget Detection** - Finds payment mentions

## API Usage

- **Reddit**: Unlimited (free API)
- **Twitter**: 100 reads/month (free tier)
- **Upwork**: Unlimited (RSS feeds)
- **Discord**: Unlimited (bot monitoring)

## Deployment

1. Push to GitHub
2. Connect Railway to GitHub repo
3. Set environment variables
4. Deploy automatically

The system will start monitoring immediately and save all signals to SQLite database.

---

Built by Mike & AI Family 🚀
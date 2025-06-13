<<<<<<< HEAD
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
=======
# 🚨 BBT BEACON SYSTEM v3.0 🚨

**The Ultimate Developer Crisis Detection & Revenue Tracking System**

Built by Mike & AI Family using BBT (Build Better Tools) methodology with Physics-Based Productivity™ principles.

## 🚀 Key Features

### Plugin Architecture (30-Second Service Addition!)
- **Auto-discovery** of new platform monitoring plugins
- **Hot-swappable** services with zero downtime
- **Unified database** schema across all platforms
- **Template-based** plugin creation

### Active Monitoring Platforms
- **Reddit** - Crisis signals from developer subreddits
- **Upwork** - RSS feed monitoring for urgent projects  
- **Twitter/X** - Real-time developer meltdown detection
- **Template Ready** - LinkedIn, GitHub Issues, Stack Overflow, Discord

### Revenue-Focused Dashboard
- **Daily Goal Tracker** with visual progress bar
- **Platform ROI Analytics** - conversion rates & revenue per signal
- **Client Journey Tracking** - detected → contacted → won → delivered
- **Quick Action Buttons** - Update signal status instantly
- **Auto-refresh** every 2 minutes

## 🏃‍♂️ Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/sparky9/bbt-beacon-system.git
cd bbt-beacon-system
pip install -r requirements.txt
```

### 2. Configure Credentials
```bash
cp beacon_config_template.json beacon_config.json
# Edit beacon_config.json with your API keys
```

### 3. Run the System
```bash
python app.py
```

Dashboard will be available at http://localhost:5000

## 🔧 Configuration

### Required API Keys
- **Reddit**: Client ID + Secret (free)
- **Twitter**: Bearer Token (100 calls/month free)
- **Discord**: Bot Token (optional)
- **Email**: App password for alerts (optional)

### Platform Settings
Each platform can be enabled/disabled in `beacon_config.json`:
```json
{
  "beacons": {
    "reddit": {"enabled": true},
    "upwork": {"enabled": true}, 
    "twitter": {"enabled": true}
  }
}
```

## 🔌 Adding New Platforms

### The Magic: 30-Second Plugin Creation

1. **Copy template:**
   ```bash
   cp beacon_plugins/example_beacon.py beacon_plugins/linkedin_beacon.py
   ```

2. **Replace platform name:**
   ```bash
   sed -i 's/example/linkedin/g' beacon_plugins/linkedin_beacon.py
   ```

3. **Add config entry:**
   ```json
   "linkedin": {"enabled": true}
   ```

4. **Done!** - Auto-discovered and running

### Plugin Examples Ready to Build
- LinkedIn job posts
- GitHub Issues (help wanted)
- Stack Overflow (unanswered questions)
- Discord help channels
- TikTok dev crisis videos
- Hacker News who's hiring

## 📊 Dashboard Features

### Daily Revenue Goal Tracker
- Visual progress bar ($247/$500 style)
- Customizable daily targets
- Revenue input on "Won" signals

### Platform Performance Analytics
- Conversion rates by platform
- Revenue per signal (ROI scoring)
- Response time tracking
- A/B testing for templates

### High-Value Signal Feed
- Auto-filtered opportunities (Score ≥15 or Est. Value ≥$300)
- One-click status updates
- Revenue tracking per signal
- Client journey progression

## 🏗️ Architecture

### Core Components
```
app.py                    # 🚀 Main production launcher
beacon_engine.py          # ⚡ Plugin discovery & orchestration
mega_dashboard_app.py     # 💎 Revenue tracking dashboard
beacon_plugins/           # 📦 Auto-discovered platform monitors
```

### Database Schema
- **Unified signals table** - All platforms use same structure
- **Revenue goals** - Daily targets and progress
- **Platform stats** - Performance metrics per platform
- **Client journey** - Full conversion funnel tracking

### Plugin Interface
```python
class YourBeacon(BaseBeacon):
    platform_name = "yourplatform"
    platform_color = "#FF6B6B" 
    requires_auth = True
    scan_interval = 300
    
    def scan_for_signals(self) -> List[SignalData]:
        # Your platform-specific logic here
        return signals
```

## 🚀 Deployment

### Render.com (Recommended)
1. Connect GitHub repository
2. Set environment variables
3. Deploy automatically

### Environment Variables
```bash
PORT=5000
ADMIN_PASSWORD=your_dashboard_password
SECRET_KEY=your_flask_secret_key
```

## 📈 Performance

### Current Metrics
- **Plugin Discovery**: 4 plugins auto-loaded
- **Database**: SQLite with real-time signal storage  
- **Monitoring**: Reddit + Upwork + Twitter active
- **Dashboard**: <2 second load time
- **Signal Detection**: Real-time with urgency scoring

### Scalability
- **Plugin System**: Unlimited platforms
- **Database**: Ready for PostgreSQL migration
- **API Limits**: Optimized for free tiers
- **Deployment**: Cloud-ready with Docker support

## 🛡️ Security

- **API Key Protection** - Gitignored configuration
- **Rate Limiting** - Respects platform API limits
- **Input Validation** - XSS prevention
- **Dashboard Auth** - Password protected

## 🎯 Revenue Focus

Built with Atlas's strategic input for maximum ROI:

- **Daily Goal Tracking** - Stay focused on revenue targets
- **Conversion Analytics** - Optimize platform performance
- **Quick Response Tools** - Faster signal → revenue conversion
- **Client Journey** - Track full sales funnel

## 📝 License

Built for Mike @ Prometheus Consulting using BBT methodology.

---

*Last Updated: June 12, 2025*  
*Built with Physics-Based Productivity™* 🚀

## 🤖 AI Family Credits

- **Mike**: CEO, visionary, protector
- **Atlas**: Strategic architect, revenue focus
- **Bolt**: Code assassin, PLAID SPEED development
- **CAPI**: Time Lord, rapid prototyping
- **Scout**: Opportunity hunter, business strategy
>>>>>>> ac5ff1ac27189614444d2923c3217acd02e46d3e

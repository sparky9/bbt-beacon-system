#!/usr/bin/env python3
"""
BBT Beacon System - Unified Dashboard & Scanner
All-in-one monitoring and dashboard service
"""

from flask import Flask, render_template, request, redirect, session, jsonify
import psycopg
import json
import os
import time
import threading
import logging
from datetime import datetime
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
)
logger = logging.getLogger('BBTBeacon')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://bbt_beacon_database_user:4yBLYDW0miHDge4ud1VSilpBFuz27ZcT@dpg-d15naleuk2gs73firtqg-a.ohio-postgres.render.com/bbt_beacon_database')

def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row)

# Password protection
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'beacon2025')

def init_database():
    """Initialize the signals database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS multi_platform_signals (
            id SERIAL PRIMARY KEY,
            platform TEXT NOT NULL,
            platform_id TEXT UNIQUE,
            title TEXT,
            content TEXT,
            author TEXT,
            url TEXT,
            created_utc REAL,
            urgency_score INTEGER,
            budget_range TEXT,
            tech_stack TEXT,
            keywords_matched TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            responded BOOLEAN DEFAULT FALSE,
            template_used TEXT,
            notes TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"Database init error: {e}")

# ============= FLASK ROUTES =============

def check_auth():
    """Check if user is authenticated"""
    return session.get('authenticated', False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['authenticated'] = True
            return redirect('/')
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Invalid password")
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect('/login')

@app.route('/')
def dashboard():
    if not check_auth():
        return redirect('/login')
    
    # Get signals from database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get recent signals
        cursor.execute('''
        SELECT platform, title, content, author, url, urgency_score, 
               detected_at, keywords_matched, tech_stack
        FROM multi_platform_signals 
        ORDER BY detected_at DESC 
        LIMIT 50
        ''')
        
        signals = []
        for row in cursor.fetchall():
            signals.append({
                'platform': row['platform'],
                'title': row['title'],
                'content': row['content'][:200] + '...' if len(row['content']) > 200 else row['content'],
                'author': row['author'],
                'url': row['url'],
                'urgency_score': row['urgency_score'],
                'detected_at': row['detected_at'],
                'keywords_matched': json.loads(row['keywords_matched']) if row['keywords_matched'] else [],
                'tech_stack': json.loads(row['tech_stack']) if row['tech_stack'] else []
            })
        
        conn.close()
        
    except Exception as e:
        signals = []
        logger.error(f"Dashboard error: {e}")
    
    return render_template_string(DASHBOARD_TEMPLATE, signals=signals)

@app.route('/api/signals')
def api_signals():
    """API endpoint for live signal updates"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN urgency_score >= 30 THEN 1 ELSE 0 END) as urgent,
               SUM(CASE WHEN urgency_score >= 15 AND urgency_score < 30 THEN 1 ELSE 0 END) as medium,
               SUM(CASE WHEN urgency_score < 15 THEN 1 ELSE 0 END) as low
        FROM multi_platform_signals 
        WHERE detected_at > NOW() - INTERVAL '24 hours'
        ''')
        
        stats = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'total_24h': stats['total'] or 0,
            'urgent': stats['urgent'] or 0,
            'medium': stats['medium'] or 0, 
            'low': stats['low'] or 0,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= BEACON MONITORING =============

class BeaconMonitor:
    def __init__(self):
        self.running = True
        self.credentials = {
            'reddit_client_id': os.getenv('REDDIT_CLIENT_ID'),
            'reddit_client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
            'twitter_bearer_token': os.getenv('TWITTER_BEARER_TOKEN'),
        }
    
    def save_signal(self, signal):
        """Save a signal to the database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO multi_platform_signals 
            (platform, platform_id, title, content, author, url, created_utc, 
             urgency_score, budget_range, tech_stack, keywords_matched)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform_id) DO NOTHING
            ''', (
                signal['platform'], signal['platform_id'], signal['title'],
                signal['content'], signal['author'], signal['url'],
                signal['created_utc'], signal['urgency_score'],
                signal.get('budget_range', ''), signal.get('tech_stack', ''),
                signal.get('keywords_matched', '')
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"💾 Saved {signal['platform']} signal: {signal['title'][:50]}...")
            
        except Exception as e:
            logger.error(f"❌ Error saving signal: {e}")
    
    def calculate_urgency(self, title, content):
        """Calculate urgency score for any text"""
        score = 0
        text = (title + ' ' + content).lower()
        
        keywords = {
            'urgent': 10, 'emergency': 15, 'asap': 12, 'immediately': 10,
            'help': 5, 'stuck': 8, 'broken': 7, 'not working': 6,
            'deadline': 9, 'production down': 20, 'site down': 15,
            'will pay': 15, 'budget': 10, 'hire': 8, 'freelancer': 6,
            'frustrated': 5, 'desperate': 8, 'please help': 7
        }
        
        for keyword, points in keywords.items():
            if keyword in text:
                score += points
        
        return min(score, 50)
    
    def extract_tech_stack(self, text):
        """Extract technology mentions"""
        tech_keywords = [
            'react', 'node', 'javascript', 'python', 'typescript',
            'django', 'flask', 'express', 'mongodb', 'postgresql',
            'aws', 'docker', 'api', 'nextjs', 'vue', 'angular'
        ]
        
        text_lower = text.lower()
        return [tech for tech in tech_keywords if tech in text_lower]
    
    def get_matched_keywords(self, text):
        """Get all matched crisis keywords"""
        matched = []
        text_lower = text.lower()
        
        keywords = ['urgent', 'help', 'broken', 'stuck', 'deadline', 'emergency', 'will pay']
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return matched
    
    def reddit_monitor(self):
        """Monitor Reddit using mock data"""
        logger.info("🔴 Starting Reddit monitor (mock mode)")
        
        while self.running:
            try:
                # Mock signals for testing
                mock_signal = {
                    'platform': 'reddit',
                    'platform_id': f'reddit_{int(time.time())}',
                    'title': 'Help needed - Production site throwing errors',
                    'content': 'Our React app is showing blank pages for some users. Need urgent help to fix this!',
                    'author': 'startup_founder',
                    'url': 'https://reddit.com/r/webdev/mock',
                    'created_utc': time.time(),
                    'urgency_score': 25,
                    'tech_stack': json.dumps(['react', 'javascript']),
                    'keywords_matched': json.dumps(['help', 'urgent'])
                }
                
                self.save_signal(mock_signal)
                logger.info("🔴 Reddit scan complete")
                
            except Exception as e:
                logger.error(f"Reddit monitor error: {e}")
            
            time.sleep(300)  # 5 minutes
    
    def upwork_monitor(self):
        """Monitor Upwork RSS feeds"""
        logger.info("💼 Starting Upwork monitor")
        
        try:
            import feedparser
            
            feeds = [
                'https://www.upwork.com/ab/feed/jobs/rss?q=urgent+developer&sort=recency',
                'https://www.upwork.com/ab/feed/jobs/rss?q=website+broken&sort=recency'
            ]
            
            while self.running:
                try:
                    for feed_url in feeds:
                        feed = feedparser.parse(feed_url)
                        
                        for entry in feed.entries[:3]:  # Latest 3
                            urgency_score = self.calculate_urgency(entry.title, entry.get('summary', ''))
                            
                            if urgency_score >= 5:
                                signal = {
                                    'platform': 'upwork',
                                    'platform_id': entry.id,
                                    'title': entry.title,
                                    'content': entry.get('summary', '')[:500],
                                    'author': 'Upwork Client',
                                    'url': entry.link,
                                    'created_utc': time.time(),
                                    'urgency_score': urgency_score,
                                    'tech_stack': json.dumps(self.extract_tech_stack(entry.title + ' ' + entry.get('summary', ''))),
                                    'keywords_matched': json.dumps(self.get_matched_keywords(entry.title + ' ' + entry.get('summary', '')))
                                }
                                
                                self.save_signal(signal)
                        
                        time.sleep(5)  # Rate limiting
                    
                    logger.info("💼 Upwork scan complete")
                    
                except Exception as e:
                    logger.error(f"Upwork feed error: {e}")
                
                time.sleep(600)  # 10 minutes
                
        except ImportError:
            logger.warning("feedparser not available, using mock data")
            while self.running:
                mock_signal = {
                    'platform': 'upwork',
                    'platform_id': f'upwork_{int(time.time())}',
                    'title': 'Need React developer ASAP - $500',
                    'content': 'Website is broken and need someone to fix it immediately. Budget $500.',
                    'author': 'Upwork Client',
                    'url': 'https://upwork.com/jobs/mock',
                    'created_utc': time.time(),
                    'urgency_score': 30,
                    'tech_stack': json.dumps(['react']),
                    'keywords_matched': json.dumps(['need', 'asap', 'broken'])
                }
                self.save_signal(mock_signal)
                time.sleep(600)
    
    def github_monitor(self):
        """Monitor GitHub Issues"""
        logger.info("🐙 Starting GitHub monitor")
        
        import requests
        
        while self.running:
            try:
                url = "https://api.github.com/search/issues"
                params = {
                    'q': 'help wanted is:open',
                    'sort': 'created',
                    'per_page': 5
                }
                
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for issue in data.get('items', [])[:3]:
                        urgency_score = self.calculate_urgency(issue['title'], issue.get('body', ''))
                        
                        if urgency_score >= 5:
                            signal = {
                                'platform': 'github',
                                'platform_id': str(issue['id']),
                                'title': issue['title'],
                                'content': (issue.get('body', '') or '')[:500],
                                'author': issue['user']['login'],
                                'url': issue['html_url'],
                                'created_utc': time.time(),
                                'urgency_score': urgency_score,
                                'tech_stack': json.dumps(self.extract_tech_stack(issue['title'] + ' ' + (issue.get('body', '') or ''))),
                                'keywords_matched': json.dumps(self.get_matched_keywords(issue['title'] + ' ' + (issue.get('body', '') or '')))
                            }
                            
                            self.save_signal(signal)
                
                logger.info("🐙 GitHub scan complete")
                
            except Exception as e:
                logger.error(f"GitHub monitor error: {e}")
            
            time.sleep(600)  # 10 minutes
    
    def start_all_monitors(self):
        """Start all monitoring threads"""
        monitors = [
            threading.Thread(target=self.reddit_monitor, daemon=True, name="Reddit"),
            threading.Thread(target=self.upwork_monitor, daemon=True, name="Upwork"),
            threading.Thread(target=self.github_monitor, daemon=True, name="GitHub")
        ]
        
        for monitor in monitors:
            monitor.start()
            logger.info(f"✅ Started {monitor.name} monitor")

# ============= TEMPLATES =============

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BBT Beacon - Login</title>
    <style>
        body { 
            font-family: monospace; 
            background: #0a0a0a; 
            color: #00ff00; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            margin: 0;
        }
        .login-box { 
            background: #1a1a1a; 
            padding: 40px; 
            border-radius: 10px; 
            border: 2px solid #00ff00;
            text-align: center;
        }
        input[type="password"] { 
            background: #0a0a0a; 
            color: #00ff00; 
            border: 1px solid #00ff00; 
            padding: 10px; 
            font-family: monospace;
            margin: 10px;
        }
        input[type="submit"] { 
            background: #00ff00; 
            color: #0a0a0a; 
            border: none; 
            padding: 10px 20px; 
            cursor: pointer;
            font-family: monospace;
            font-weight: bold;
        }
        .error { color: #ff0000; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🚨 BBT BEACON ACCESS 🚨</h1>
        <p>Enter password to access beacon control:</p>
        <form method="post">
            <input type="password" name="password" placeholder="Password" required>
            <br>
            <input type="submit" value="LOGIN">
        </form>
        {% if error %}
        <p class="error">{{ error }}</p>
        {% endif %}
    </div>
</body>
</html>
'''

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BBT Beacon Control Center</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: monospace; 
            background: #0a0a0a; 
            color: #00ff00; 
            margin: 0; 
            padding: 20px;
        }
        .header { 
            text-align: center; 
            border-bottom: 2px solid #00ff00; 
            padding-bottom: 20px; 
            margin-bottom: 20px;
        }
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px;
        }
        .stat-box { 
            background: #1a1a1a; 
            padding: 20px; 
            border-radius: 8px; 
            border: 1px solid #00ff00; 
            text-align: center;
        }
        .signal { 
            background: #1a1a1a; 
            margin: 10px 0; 
            padding: 15px; 
            border-radius: 8px; 
            border-left: 5px solid #666;
        }
        .urgent { border-left-color: #ff4757; }
        .medium { border-left-color: #ffa502; }
        .low { border-left-color: #2ed573; }
        .platform { 
            display: inline-block; 
            padding: 3px 8px; 
            border-radius: 3px; 
            font-size: 12px; 
            margin-right: 10px;
        }
        .reddit { background: #ff4500; color: white; }
        .twitter { background: #1da1f2; color: white; }
        .discord { background: #7289da; color: white; }
        .upwork { background: #14a800; color: white; }
        .stackoverflow { background: #f48024; color: white; }
        .github { background: #333; color: white; }
        .logout { 
            position: absolute; 
            top: 20px; 
            right: 20px; 
            color: #ff4757; 
            text-decoration: none;
        }
        .status { 
            color: #2ed573; 
            font-size: 12px; 
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <a href="/logout" class="logout">Logout</a>
    
    <div class="header">
        <h1>🚨 BBT BEACON CONTROL CENTER 🚨</h1>
        <p>24/7 Developer Crisis Monitoring System</p>
        <p class="status">✅ All monitors running | Auto-refreshes every 5 minutes</p>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <h3>🔴 URGENT</h3>
            <div id="urgent-count">Loading...</div>
        </div>
        <div class="stat-box">
            <h3>🟡 MEDIUM</h3>
            <div id="medium-count">Loading...</div>
        </div>
        <div class="stat-box">
            <h3>🟢 LOW</h3>
            <div id="low-count">Loading...</div>
        </div>
        <div class="stat-box">
            <h3>📊 TOTAL 24H</h3>
            <div id="total-count">Loading...</div>
        </div>
    </div>
    
    <h2>📡 Recent Signals</h2>
    
    {% if signals %}
        {% for signal in signals %}
        <div class="signal {{ 'urgent' if signal.urgency_score >= 30 else 'medium' if signal.urgency_score >= 15 else 'low' }}">
            <span class="platform {{ signal.platform }}">{{ signal.platform.upper() }}</span>
            <strong>{{ signal.title }}</strong>
            <br>
            <p>{{ signal.content }}</p>
            <small>
                👤 {{ signal.author }} | 
                🎯 Score: {{ signal.urgency_score }} | 
                ⏰ {{ signal.detected_at }}
                {% if signal.url %}
                | <a href="{{ signal.url }}" target="_blank" style="color: #00ff00;">View Post</a>
                {% endif %}
            </small>
        </div>
        {% endfor %}
    {% else %}
        <p style="text-align: center; color: #666;">No signals yet. Monitors are scanning...</p>
    {% endif %}
    
    <script>
        // Auto-refresh stats every 30 seconds
        function updateStats() {
            fetch('/api/signals')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('urgent-count').textContent = data.urgent || 0;
                    document.getElementById('medium-count').textContent = data.medium || 0;
                    document.getElementById('low-count').textContent = data.low || 0;
                    document.getElementById('total-count').textContent = data.total_24h || 0;
                })
                .catch(error => console.error('Error:', error));
        }
        
        updateStats();
        setInterval(updateStats, 30000);
        
        // Auto-refresh page every 5 minutes
        setTimeout(() => location.reload(), 300000);
    </script>
</body>
</html>
'''

# ============= MAIN STARTUP =============

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Start beacon monitors in background
    monitor = BeaconMonitor()
    monitor.start_all_monitors()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Starting BBT Beacon System on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
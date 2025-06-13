#!/usr/bin/env python3
"""
BBT Beacon System - Unified Dashboard & Scanner
All-in-one monitoring and dashboard service
"""

from flask import Flask, render_template_string, request, redirect, session, jsonify
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
        SELECT id, platform, title, content, author, url, urgency_score, 
               detected_at, keywords_matched, tech_stack
        FROM multi_platform_signals 
        ORDER BY detected_at DESC 
        LIMIT 50
        ''')
        
        signals = []
        for row in cursor.fetchall():
            signals.append({
                'id': row['id'],  # Add ID for linking
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

@app.route('/signal/<int:signal_id>')
def signal_detail(signal_id):
    """View individual signal details and select template"""
    if not check_auth():
        return redirect('/login')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get specific signal
        cursor.execute('''
        SELECT id, platform, title, content, author, url, urgency_score, 
               detected_at, keywords_matched, tech_stack, budget_range,
               responded, template_used, notes
        FROM multi_platform_signals 
        WHERE id = %s
        ''', (signal_id,))
        
        signal = cursor.fetchone()
        conn.close()
        
        if not signal:
            return "Signal not found", 404
            
        # Parse JSON fields
        signal['keywords_matched'] = json.loads(signal['keywords_matched']) if signal['keywords_matched'] else []
        signal['tech_stack'] = json.loads(signal['tech_stack']) if signal['tech_stack'] else []
        
        return render_template_string(SIGNAL_DETAIL_TEMPLATE, signal=signal)
        
    except Exception as e:
        logger.error(f"Error loading signal: {e}")
        return "Error loading signal", 500

@app.route('/signal/<int:signal_id>/respond', methods=['POST'])
def respond_to_signal(signal_id):
    """Mark signal as responded with template"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        template_used = request.form.get('template')
        notes = request.form.get('notes', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE multi_platform_signals 
        SET responded = TRUE, template_used = %s, notes = %s
        WHERE id = %s
        ''', (template_used, notes, signal_id))
        
        conn.commit()
        conn.close()
        
        return redirect(f'/signal/{signal_id}')
        
    except Exception as e:
        logger.error(f"Error updating signal: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/signal/<int:signal_id>/delete', methods=['POST'])
def delete_signal(signal_id):
    """Delete a signal"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM multi_platform_signals WHERE id = %s', (signal_id,))
        
        conn.commit()
        conn.close()
        
        return redirect('/')
        
    except Exception as e:
        logger.error(f"Error deleting signal: {e}")
        return jsonify({'error': str(e)}), 500

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
    
    def extract_budget_from_text(self, text):
        """Extract budget information from text"""
        import re
        budget_patterns = [
            r'\$[\d,]+\s*-\s*\$[\d,]+',
            r'Budget:\s*\$[\d,]+',
            r'\$[\d,]+\s*(?:USD|usd)?',
            r'[\d,]+\s*(?:dollars|USD)',
            r'pay\s*\$[\d,]+',
            r'budget\s*of\s*\$[\d,]+'
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return ''
    
    def reddit_monitor(self):
        """Monitor Reddit for real crisis signals"""
        logger.info("🔴 Starting Reddit monitor")
        
        if not self.credentials['reddit_client_id'] or not self.credentials['reddit_client_secret']:
            logger.warning("Reddit credentials not configured - skipping Reddit monitoring")
            return
            
        try:
            import praw
            
            reddit = praw.Reddit(
                client_id=self.credentials['reddit_client_id'],
                client_secret=self.credentials['reddit_client_secret'],
                user_agent='BBTBeacon/1.0'
            )
            
            subreddits = ['webdev', 'programming', 'learnprogramming', 'freelance', 'forhire']
            
            while self.running:
                for subreddit_name in subreddits:
                    try:
                        subreddit = reddit.subreddit(subreddit_name)
                        
                        for post in subreddit.new(limit=10):
                            urgency_score = self.calculate_urgency(post.title, post.selftext)
                            
                            if urgency_score >= 10:  # Only save significant signals
                                signal = {
                                    'platform': 'reddit',
                                    'platform_id': post.id,
                                    'title': post.title,
                                    'content': post.selftext[:500] if post.selftext else 'No content',
                                    'author': str(post.author),
                                    'url': f"https://reddit.com{post.permalink}",
                                    'created_utc': post.created_utc,
                                    'urgency_score': urgency_score,
                                    'tech_stack': json.dumps(self.extract_tech_stack(post.title + ' ' + post.selftext)),
                                    'keywords_matched': json.dumps(self.get_matched_keywords(post.title + ' ' + post.selftext))
                                }
                                
                                self.save_signal(signal)
                        
                        time.sleep(2)  # Rate limiting between subreddits
                        
                    except Exception as e:
                        logger.error(f"Reddit error for r/{subreddit_name}: {e}")
                
                logger.info("🔴 Reddit scan complete, sleeping 5 minutes...")
                time.sleep(300)  # 5 minutes
                
        except ImportError:
            logger.error("praw not installed - Reddit monitoring disabled")
        except Exception as e:
            logger.error(f"Reddit monitor error: {e}")
    
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
                                    'budget_range': self.extract_budget_from_text(entry.title + ' ' + entry.get('summary', '')),
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
            logger.error("feedparser not installed - Upwork monitoring disabled")
    
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
    
    def stackoverflow_monitor(self):
        """Monitor Stack Overflow for help requests"""
        logger.info("📚 Starting Stack Overflow monitor")
        
        import requests
        
        while self.running:
            try:
                # Stack Exchange API endpoint for newest questions
                url = "https://api.stackexchange.com/2.3/questions"
                params = {
                    'order': 'desc',
                    'sort': 'creation',
                    'tagged': 'javascript;react;python;node.js',
                    'site': 'stackoverflow',
                    'filter': 'withbody',
                    'pagesize': 20
                }
                
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for question in data.get('items', []):
                        # Check if it's a help request
                        urgency_score = self.calculate_urgency(question['title'], question.get('body', ''))
                        
                        if urgency_score >= 8:  # Stack Overflow threshold
                            signal = {
                                'platform': 'stackoverflow',
                                'platform_id': str(question['question_id']),
                                'title': question['title'],
                                'content': question.get('body', '')[:500],
                                'author': question['owner'].get('display_name', 'Anonymous'),
                                'url': question['link'],
                                'created_utc': question['creation_date'],
                                'urgency_score': urgency_score,
                                'tech_stack': json.dumps(question.get('tags', [])),
                                'keywords_matched': json.dumps(self.get_matched_keywords(question['title'] + ' ' + question.get('body', '')))
                            }
                            
                            self.save_signal(signal)
                
                logger.info("📚 Stack Overflow scan complete")
                
            except Exception as e:
                logger.error(f"Stack Overflow monitor error: {e}")
            
            time.sleep(900)  # 15 minutes
    
    def start_all_monitors(self):
        """Start all monitoring threads"""
        monitors = [
            threading.Thread(target=self.reddit_monitor, daemon=True, name="Reddit"),
            threading.Thread(target=self.upwork_monitor, daemon=True, name="Upwork"),
            threading.Thread(target=self.github_monitor, daemon=True, name="GitHub"),
            threading.Thread(target=self.stackoverflow_monitor, daemon=True, name="StackOverflow")
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
        .delete-btn {
            background: #ff4757;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            float: right;
            margin-left: 10px;
        }
        .delete-btn:hover {
            background: #ff3838;
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
            <form method="POST" action="/signal/{{ signal.id }}/delete" style="display: inline;">
                <button type="submit" class="delete-btn" onclick="return confirm('Delete this signal?');">🗑️ Delete</button>
            </form>
            <div style="cursor: pointer;" onclick="window.location.href='/signal/{{ signal.id }}'">
                <span class="platform {{ signal.platform }}">{{ signal.platform.upper() }}</span>
                <strong>{{ signal.title }}</strong>
                <br>
                <p>{{ signal.content }}</p>
                <small>
                    👤 {{ signal.author }} | 
                    🎯 Score: {{ signal.urgency_score }} | 
                    ⏰ {{ signal.detected_at }}
                    | <a href="/signal/{{ signal.id }}" style="color: #00ff00;" onclick="event.stopPropagation();">View Details</a>
                    {% if signal.url %}
                    | <a href="{{ signal.url }}" target="_blank" style="color: #00ff00;" onclick="event.stopPropagation();">View Post</a>
                    {% endif %}
                </small>
            </div>
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

SIGNAL_DETAIL_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Signal Details - BBT Beacon</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: monospace; 
            background: #0a0a0a; 
            color: #00ff00; 
            margin: 0; 
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .header { 
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #00ff00; 
            padding-bottom: 20px; 
            margin-bottom: 20px;
        }
        .back-btn {
            color: #00ff00;
            text-decoration: none;
            padding: 10px 20px;
            border: 1px solid #00ff00;
            border-radius: 5px;
        }
        .signal-detail {
            background: #1a1a1a;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .platform { 
            display: inline-block; 
            padding: 5px 15px; 
            border-radius: 5px; 
            font-size: 14px; 
            margin-bottom: 20px;
        }
        .reddit { background: #ff4500; color: white; }
        .upwork { background: #14a800; color: white; }
        .github { background: #333; color: white; }
        .twitter { background: #1da1f2; color: white; }
        .stackoverflow { background: #f48024; color: white; }
        .field {
            margin: 15px 0;
            padding: 15px;
            background: #0a0a0a;
            border-radius: 5px;
        }
        .field-label {
            color: #888;
            font-size: 12px;
            margin-bottom: 5px;
        }
        .tech-tag, .keyword-tag {
            display: inline-block;
            padding: 3px 10px;
            margin: 3px;
            background: #00ff00;
            color: #0a0a0a;
            border-radius: 3px;
            font-size: 12px;
        }
        .response-section {
            background: #1a1a1a;
            padding: 30px;
            border-radius: 10px;
            border: 2px solid #00ff00;
        }
        .template-select {
            width: 100%;
            padding: 10px;
            background: #0a0a0a;
            color: #00ff00;
            border: 1px solid #00ff00;
            font-family: monospace;
            margin: 10px 0;
        }
        .notes-input {
            width: 100%;
            min-height: 100px;
            padding: 10px;
            background: #0a0a0a;
            color: #00ff00;
            border: 1px solid #00ff00;
            font-family: monospace;
            margin: 10px 0;
            resize: vertical;
        }
        .btn {
            padding: 10px 30px;
            margin: 10px 5px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-family: monospace;
            font-weight: bold;
        }
        .btn-primary {
            background: #00ff00;
            color: #0a0a0a;
        }
        .btn-secondary {
            background: #666;
            color: white;
        }
        .btn-danger {
            background: #ff4757;
            color: white;
        }
        .responded-badge {
            background: #2ed573;
            color: white;
            padding: 5px 15px;
            border-radius: 5px;
            font-size: 14px;
        }
        .external-link {
            color: #00ff00;
            text-decoration: none;
            padding: 10px 20px;
            border: 1px solid #00ff00;
            border-radius: 5px;
            display: inline-block;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📡 Signal Details</h1>
        <div>
            <form method="POST" action="/signal/{{ signal.id }}/delete" style="display: inline;">
                <button type="submit" class="btn btn-danger" onclick="return confirm('Delete this signal?');">🗑️ Delete Signal</button>
            </form>
            <a href="/" class="back-btn">← Back to Dashboard</a>
        </div>
    </div>
    
    <div class="signal-detail">
        <span class="platform {{ signal.platform }}">{{ signal.platform.upper() }}</span>
        {% if signal.responded %}
        <span class="responded-badge">✅ Responded</span>
        {% endif %}
        
        <h2>{{ signal.title }}</h2>
        
        <div class="field">
            <div class="field-label">CONTENT</div>
            {{ signal.content }}
        </div>
        
        <div class="field">
            <div class="field-label">DETAILS</div>
            👤 Author: {{ signal.author }}<br>
            🎯 Urgency Score: {{ signal.urgency_score }}<br>
            ⏰ Detected: {{ signal.detected_at }}<br>
            {% if signal.budget_range %}
            💰 Budget: {{ signal.budget_range }}<br>
            {% endif %}
        </div>
        
        {% if signal.tech_stack %}
        <div class="field">
            <div class="field-label">TECH STACK</div>
            {% for tech in signal.tech_stack %}
            <span class="tech-tag">{{ tech }}</span>
            {% endfor %}
        </div>
        {% endif %}
        
        {% if signal.keywords_matched %}
        <div class="field">
            <div class="field-label">MATCHED KEYWORDS</div>
            {% for keyword in signal.keywords_matched %}
            <span class="keyword-tag">{{ keyword }}</span>
            {% endfor %}
        </div>
        {% endif %}
        
        {% if signal.url %}
        <a href="{{ signal.url }}" target="_blank" class="external-link">🔗 View Original Post</a>
        {% endif %}
    </div>
    
    <div class="response-section">
        <h3>📝 Response Management</h3>
        
        {% if signal.responded %}
            <div class="field">
                <div class="field-label">TEMPLATE USED</div>
                {{ signal.template_used or 'None' }}
            </div>
            {% if signal.notes %}
            <div class="field">
                <div class="field-label">NOTES</div>
                {{ signal.notes }}
            </div>
            {% endif %}
        {% else %}
            <form method="POST" action="/signal/{{ signal.id }}/respond">
                <div class="field">
                    <div class="field-label">SELECT TEMPLATE</div>
                    <select name="template" class="template-select" required>
                        <option value="">-- Choose Template --</option>
                        <option value="urgent_fix">🚨 Urgent Fix Response</option>
                        <option value="consultation">💼 Consultation Offer</option>
                        <option value="quick_help">⚡ Quick Help</option>
                        <option value="full_service">🛠️ Full Service Proposal</option>
                        <option value="custom">✍️ Custom Response</option>
                    </select>
                </div>
                
                <div class="field">
                    <div class="field-label">NOTES (Optional)</div>
                    <textarea name="notes" class="notes-input" placeholder="Add any notes about this response..."></textarea>
                </div>
                
                <button type="submit" class="btn btn-primary">Mark as Responded</button>
                <a href="{{ signal.url }}" target="_blank" class="btn btn-secondary">Open Post to Respond</a>
            </form>
        {% endif %}
    </div>
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
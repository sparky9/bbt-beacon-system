#!/usr/bin/env python3
"""
BBT Beacon Web Dashboard for Railway
Password-protected beacon control center
"""

from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import json
import os
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# Password protection
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'beacon2025')

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
        conn = sqlite3.connect('distress_beacon.db')
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
                'platform': row[0],
                'title': row[1],
                'content': row[2][:200] + '...' if len(row[2]) > 200 else row[2],
                'author': row[3],
                'url': row[4],
                'urgency_score': row[5],
                'detected_at': row[6],
                'keywords_matched': json.loads(row[7]) if row[7] else [],
                'tech_stack': json.loads(row[8]) if row[8] else []
            })
        
        conn.close()
        
    except Exception as e:
        signals = [{'error': str(e)}]
    
    return render_template_string(DASHBOARD_TEMPLATE, signals=signals)

@app.route('/api/signals')
def api_signals():
    """API endpoint for live signal updates"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = sqlite3.connect('distress_beacon.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN urgency_score >= 30 THEN 1 ELSE 0 END) as urgent,
               SUM(CASE WHEN urgency_score >= 15 AND urgency_score < 30 THEN 1 ELSE 0 END) as medium,
               SUM(CASE WHEN urgency_score < 15 THEN 1 ELSE 0 END) as low
        FROM multi_platform_signals 
        WHERE detected_at > datetime('now', '-24 hours')
        ''')
        
        stats = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'total_24h': stats[0],
            'urgent': stats[1],
            'medium': stats[2], 
            'low': stats[3],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Templates
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
        .logout { 
            position: absolute; 
            top: 20px; 
            right: 20px; 
            color: #ff4757; 
            text-decoration: none;
        }
    </style>
</head>
<body>
    <a href="/logout" class="logout">Logout</a>
    
    <div class="header">
        <h1>🚨 BBT BEACON CONTROL CENTER 🚨</h1>
        <p>24/7 Developer Crisis Monitoring System</p>
        <p><em>Last updated: {{ moment().format('YYYY-MM-DD HH:mm:ss') }}</em></p>
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
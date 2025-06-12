#!/usr/bin/env python3
"""
🚨 BBT BEACON MEGA DASHBOARD 🚨
Revenue-focused opportunity hunting command center
Built by Mike & AI Family with Atlas's strategic input

Features:
- Daily revenue goal tracker (THE KILLER FEATURE!)
- Conversion analytics and platform ROI
- Smart opportunity filtering 
- Client journey tracking
- Real-time monitoring dashboard
"""

from flask import Flask, render_template_string, request, redirect, session, jsonify
import sqlite3
import json
import os
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'beacon-mega-secret-2025')

# Configuration
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'beacon2025')

class BeaconDatabase:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """Initialize comprehensive tracking database"""
        conn = sqlite3.connect('beacon_engine.db')
        cursor = conn.cursor()
        
        # Enhanced signals table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY,
            platform TEXT NOT NULL,
            platform_id TEXT UNIQUE,
            title TEXT,
            content TEXT,
            author TEXT,
            url TEXT,
            created_utc REAL,
            urgency_score INTEGER,
            budget_range TEXT,
            estimated_value REAL,
            tech_stack TEXT,
            keywords_matched TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- CLIENT JOURNEY TRACKING
            status TEXT DEFAULT 'detected',  -- detected, contacted, negotiating, won, lost, delivered
            contacted_at TIMESTAMP,
            response_time_minutes INTEGER,
            won_at TIMESTAMP,
            delivered_at TIMESTAMP,
            actual_revenue REAL DEFAULT 0,
            
            -- PERFORMANCE TRACKING  
            template_used TEXT,
            conversion_score INTEGER DEFAULT 0,
            notes TEXT,
            blacklisted BOOLEAN DEFAULT FALSE
        )
        ''')
        
        # Revenue goals table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS revenue_goals (
            id INTEGER PRIMARY KEY,
            date TEXT UNIQUE,
            daily_goal REAL DEFAULT 500,
            achieved REAL DEFAULT 0,
            target_opportunities INTEGER DEFAULT 10
        )
        ''')
        
        # Platform performance tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS platform_stats (
            id INTEGER PRIMARY KEY,
            platform TEXT,
            date TEXT,
            signals_found INTEGER DEFAULT 0,
            responses_sent INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            avg_response_time REAL DEFAULT 0
        )
        ''')
        
        # Template A/B testing
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS template_performance (
            id INTEGER PRIMARY KEY,
            template_type TEXT,
            template_version TEXT,
            uses INTEGER DEFAULT 0,
            responses INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            avg_revenue REAL DEFAULT 0,
            response_rate REAL DEFAULT 0,
            conversion_rate REAL DEFAULT 0
        )
        ''')
        
        conn.commit()
        conn.close()

# Initialize database
db = BeaconDatabase()

def check_auth():
    """Check if user is authenticated"""
    return session.get('authenticated', False)

def get_daily_stats():
    """Get today's revenue and goal progress"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('beacon_engine.db')
    cursor = conn.cursor()
    
    # Get or create today's goal
    cursor.execute('SELECT daily_goal, achieved FROM revenue_goals WHERE date = ?', (today,))
    goal_data = cursor.fetchone()
    
    if not goal_data:
        # Create today's goal
        cursor.execute('INSERT INTO revenue_goals (date, daily_goal, achieved) VALUES (?, 500, 0)', (today,))
        conn.commit()
        goal_data = (500, 0)
    
    # Get actual revenue for today
    cursor.execute('''
    SELECT COALESCE(SUM(actual_revenue), 0) 
    FROM signals 
    WHERE date(won_at) = ? AND status = 'won'
    ''', (today,))
    
    actual_revenue = cursor.fetchone()[0]
    
    # Update achieved amount
    cursor.execute('UPDATE revenue_goals SET achieved = ? WHERE date = ?', (actual_revenue, today))
    conn.commit()
    conn.close()
    
    daily_goal = goal_data[0]
    progress_percent = min(100, (actual_revenue / daily_goal) * 100) if daily_goal > 0 else 0
    
    return {
        'daily_goal': daily_goal,
        'achieved': actual_revenue,
        'progress_percent': progress_percent,
        'remaining': max(0, daily_goal - actual_revenue)
    }

def get_platform_performance():
    """Get platform ROI and effectiveness data"""
    conn = sqlite3.connect('beacon_engine.db')
    cursor = conn.cursor()
    
    # Platform conversion rates (last 30 days)
    cursor.execute('''
    SELECT 
        platform,
        COUNT(*) as total_signals,
        SUM(CASE WHEN status IN ('won', 'delivered') THEN 1 ELSE 0 END) as conversions,
        SUM(CASE WHEN status = 'contacted' THEN 1 ELSE 0 END) as contacted,
        COALESCE(SUM(actual_revenue), 0) as revenue,
        COALESCE(AVG(response_time_minutes), 0) as avg_response_time
    FROM signals 
    WHERE detected_at > datetime('now', '-30 days')
    GROUP BY platform
    ORDER BY revenue DESC
    ''')
    
    platforms = []
    for row in cursor.fetchall():
        platform, total, conversions, contacted, revenue, avg_response = row
        conversion_rate = (conversions / total * 100) if total > 0 else 0
        response_rate = (contacted / total * 100) if total > 0 else 0
        
        platforms.append({
            'name': platform,
            'total_signals': total,
            'conversions': conversions,
            'revenue': revenue,
            'conversion_rate': round(conversion_rate, 1),
            'response_rate': round(response_rate, 1),
            'avg_response_time': round(avg_response, 1),
            'roi_score': round(revenue / max(1, total), 2)  # Revenue per signal
        })
    
    conn.close()
    return platforms

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
    
    # Get dashboard data
    daily_stats = get_daily_stats()
    platform_performance = get_platform_performance()
    
    # Get recent high-value signals
    conn = sqlite3.connect('beacon_engine.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT id, platform, title, content, author, url, urgency_score, 
           estimated_value, status, detected_at, actual_revenue
    FROM signals 
    WHERE urgency_score >= 15 OR estimated_value >= 300
    ORDER BY detected_at DESC 
    LIMIT 20
    ''')
    
    signals = []
    for row in cursor.fetchall():
        signals.append({
            'id': row[0],
            'platform': row[1],
            'title': row[2],
            'content': row[3][:150] + '...' if len(row[3]) > 150 else row[3],
            'author': row[4],
            'url': row[5],
            'urgency_score': row[6],
            'estimated_value': row[7] or 0,
            'status': row[8],
            'detected_at': row[9],
            'actual_revenue': row[10] or 0
        })
    
    conn.close()
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                                daily_stats=daily_stats,
                                platform_performance=platform_performance,
                                signals=signals)

@app.route('/api/update_signal', methods=['POST'])
def update_signal():
    """Update signal status and revenue"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    signal_id = data.get('id')
    status = data.get('status')
    revenue = data.get('revenue', 0)
    
    conn = sqlite3.connect('beacon_engine.db')
    cursor = conn.cursor()
    
    # Update signal
    if status == 'contacted':
        cursor.execute('''
        UPDATE signals SET status = ?, contacted_at = CURRENT_TIMESTAMP 
        WHERE id = ?
        ''', (status, signal_id))
    elif status == 'won':
        cursor.execute('''
        UPDATE signals SET status = ?, won_at = CURRENT_TIMESTAMP, actual_revenue = ? 
        WHERE id = ?
        ''', (status, revenue, signal_id))
    else:
        cursor.execute('UPDATE signals SET status = ? WHERE id = ?', (status, signal_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/set_daily_goal', methods=['POST'])
def set_daily_goal():
    """Update daily revenue goal"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    new_goal = data.get('goal', 500)
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('beacon_engine.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO revenue_goals (date, daily_goal, achieved) 
    VALUES (?, ?, (SELECT COALESCE(achieved, 0) FROM revenue_goals WHERE date = ?))
    ''', (today, new_goal, today))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Templates
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BBT Beacon - Mega Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: 'Courier New', monospace; 
            background: linear-gradient(135deg, #0a0a0a, #1a1a2e);
            color: #00ff00; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            margin: 0;
        }
        .login-box { 
            background: rgba(26, 26, 46, 0.9); 
            padding: 40px; 
            border-radius: 15px; 
            border: 2px solid #00ff00;
            text-align: center;
            box-shadow: 0 0 30px rgba(0, 255, 0, 0.3);
        }
        input[type="password"] { 
            background: #0a0a0a; 
            color: #00ff00; 
            border: 2px solid #00ff00; 
            padding: 15px; 
            font-family: monospace;
            margin: 15px;
            border-radius: 5px;
            font-size: 16px;
        }
        input[type="submit"] { 
            background: #00ff00; 
            color: #0a0a0a; 
            border: none; 
            padding: 15px 30px; 
            cursor: pointer;
            font-family: monospace;
            font-weight: bold;
            border-radius: 5px;
            font-size: 16px;
            transition: all 0.3s;
        }
        input[type="submit"]:hover {
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.5);
        }
        .error { color: #ff0000; margin-top: 10px; }
        h1 { text-shadow: 0 0 10px #00ff00; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🚨 BBT BEACON 🚨</h1>
        <h2>MEGA DASHBOARD</h2>
        <p>Revenue-Focused Opportunity Hunter</p>
        <form method="post">
            <input type="password" name="password" placeholder="Enter Password" required>
            <br>
            <input type="submit" value="ENTER COMMAND CENTER">
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
    <title>BBT Beacon - Mega Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Courier New', monospace; 
            background: linear-gradient(135deg, #0a0a0a, #1a1a2e);
            color: #00ff00; 
            min-height: 100vh;
        }
        .header { 
            background: rgba(0, 0, 0, 0.8);
            padding: 20px;
            text-align: center;
            border-bottom: 2px solid #00ff00;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header h1 { 
            text-shadow: 0 0 20px #00ff00; 
            margin-bottom: 10px;
        }
        .revenue-goal { 
            background: linear-gradient(90deg, #ff4757, #ffa502, #2ed573);
            height: 30px;
            border-radius: 15px;
            margin: 20px auto;
            width: 80%;
            max-width: 500px;
            position: relative;
            overflow: hidden;
        }
        .revenue-progress { 
            background: rgba(0, 0, 0, 0.7);
            height: 100%;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            border-radius: 15px;
        }
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
            padding: 20px;
        }
        .stat-card { 
            background: rgba(26, 26, 46, 0.8); 
            padding: 20px; 
            border-radius: 10px; 
            border: 1px solid #00ff00; 
            text-align: center;
            transition: all 0.3s;
        }
        .stat-card:hover {
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
            transform: translateY(-2px);
        }
        .stat-value { 
            font-size: 2em; 
            font-weight: bold; 
            margin: 10px 0;
        }
        .platform-row { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 10px; 
            margin: 5px 0; 
            background: rgba(0, 0, 0, 0.3); 
            border-radius: 5px;
        }
        .signal { 
            background: rgba(26, 26, 46, 0.8); 
            margin: 10px 0; 
            padding: 15px; 
            border-radius: 8px; 
            border-left: 5px solid #666;
            transition: all 0.3s;
        }
        .signal:hover { transform: translateX(5px); }
        .urgent { border-left-color: #ff4757; }
        .medium { border-left-color: #ffa502; }
        .low { border-left-color: #2ed573; }
        .platform-badge { 
            display: inline-block; 
            padding: 5px 10px; 
            border-radius: 15px; 
            font-size: 12px; 
            margin-right: 10px;
            font-weight: bold;
        }
        .reddit { background: #ff4500; color: white; }
        .twitter { background: #1da1f2; color: white; }
        .discord { background: #7289da; color: white; }
        .upwork { background: #14a800; color: white; }
        .stackoverflow { background: #f48024; color: white; }
        .github { background: #333; color: white; }
        .status-btn { 
            padding: 5px 10px; 
            margin: 2px; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
            font-size: 12px;
            transition: all 0.3s;
        }
        .status-contacted { background: #ffa502; color: black; }
        .status-won { background: #2ed573; color: black; }
        .status-lost { background: #ff4757; color: white; }
        .logout { 
            position: absolute; 
            top: 20px; 
            right: 20px; 
            color: #ff4757; 
            text-decoration: none;
            font-weight: bold;
        }
        .section { 
            margin: 20px; 
            background: rgba(0, 0, 0, 0.5); 
            padding: 20px; 
            border-radius: 10px; 
            border: 1px solid #00ff00;
        }
        .section h2 { 
            color: #00ff00; 
            margin-bottom: 15px; 
            text-shadow: 0 0 10px #00ff00;
        }
    </style>
</head>
<body>
    <div class="header">
        <a href="/logout" class="logout">Logout</a>
        <h1>🚨 BBT BEACON MEGA DASHBOARD 🚨</h1>
        <p>Revenue-Focused Developer Crisis Hunter</p>
        
        <!-- DAILY REVENUE GOAL TRACKER - THE KILLER FEATURE! -->
        <div class="revenue-goal">
            <div class="revenue-progress" style="width: {{ daily_stats.progress_percent }}%;">
                ${{ "%.0f"|format(daily_stats.achieved) }} / ${{ "%.0f"|format(daily_stats.daily_goal) }} 
                ({{ "%.1f"|format(daily_stats.progress_percent) }}%)
            </div>
        </div>
        <p>💰 Remaining: ${{ "%.0f"|format(daily_stats.remaining) }} | 
           🎯 Goal: {{ "%.1f"|format(daily_stats.progress_percent) }}% Complete</p>
    </div>
    
    <!-- PLATFORM PERFORMANCE SECTION -->
    <div class="section">
        <h2>📊 Platform ROI & Performance (Last 30 Days)</h2>
        <div class="stats-grid">
            {% for platform in platform_performance %}
            <div class="stat-card">
                <div class="platform-badge {{ platform.name }}">{{ platform.name.upper() }}</div>
                <div class="stat-value">${{ "%.0f"|format(platform.revenue) }}</div>
                <div>{{ platform.total_signals }} signals • {{ platform.conversions }} wins</div>
                <div>{{ platform.conversion_rate }}% conversion • ${{ platform.roi_score }}/signal</div>
                <div style="font-size: 0.8em; margin-top: 5px;">
                    Response: {{ platform.response_rate }}% • 
                    Avg Time: {{ platform.avg_response_time }}min
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <!-- HIGH-VALUE SIGNALS FEED -->
    <div class="section">
        <h2>🚨 High-Value Opportunities (Score ≥15 or Est. Value ≥$300)</h2>
        {% for signal in signals %}
        <div class="signal {{ 'urgent' if signal.urgency_score >= 30 else 'medium' if signal.urgency_score >= 15 else 'low' }}" data-id="{{ signal.id }}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span class="platform-badge {{ signal.platform }}">{{ signal.platform.upper() }}</span>
                    <strong>{{ signal.title }}</strong>
                    <span style="color: #ffa502; font-weight: bold;">
                        {% if signal.estimated_value > 0 %}
                        (Est: ${{ "%.0f"|format(signal.estimated_value) }})
                        {% endif %}
                    </span>
                </div>
                <div>
                    <button class="status-btn status-contacted" onclick="updateStatus({{ signal.id }}, 'contacted')">Contact</button>
                    <button class="status-btn status-won" onclick="updateStatus({{ signal.id }}, 'won')">Won</button>
                    <button class="status-btn status-lost" onclick="updateStatus({{ signal.id }}, 'lost')">Lost</button>
                </div>
            </div>
            <p style="margin: 10px 0;">{{ signal.content }}</p>
            <small>
                👤 {{ signal.author }} | 
                🎯 Score: {{ signal.urgency_score }} | 
                💰 Status: {{ signal.status.title() }} |
                {% if signal.actual_revenue > 0 %}
                🏆 Revenue: ${{ "%.0f"|format(signal.actual_revenue) }} |
                {% endif %}
                ⏰ {{ signal.detected_at }} |
                <a href="{{ signal.url }}" target="_blank" style="color: #00ff00;">View Post</a>
            </small>
        </div>
        {% endfor %}
    </div>
    
    <script>
        // Auto-refresh every 2 minutes
        setTimeout(() => location.reload(), 120000);
        
        // Update signal status
        function updateStatus(signalId, status) {
            let revenue = 0;
            if (status === 'won') {
                revenue = prompt('Enter revenue amount (numbers only):');
                if (!revenue || isNaN(revenue)) return;
                revenue = parseFloat(revenue);
            }
            
            fetch('/api/update_signal', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    id: signalId,
                    status: status,
                    revenue: revenue
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Error updating status');
                }
            });
        }
        
        // Update daily goal
        function updateDailyGoal() {
            const newGoal = prompt('Enter new daily revenue goal:');
            if (!newGoal || isNaN(newGoal)) return;
            
            fetch('/api/set_daily_goal', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({goal: parseFloat(newGoal)})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                }
            });
        }
        
        // Make revenue goal clickable to edit
        document.querySelector('.revenue-goal').addEventListener('click', updateDailyGoal);
        document.querySelector('.revenue-goal').style.cursor = 'pointer';
        document.querySelector('.revenue-goal').title = 'Click to change daily goal';
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
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
        
        # Create ignored users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ignored_users (
            id SERIAL PRIMARY KEY,
            platform TEXT NOT NULL,
            username TEXT NOT NULL,
            reason TEXT,
            ignored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(platform, username)
        )
        ''')
        
        # Create dynamic keywords table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS platform_keywords (
            id SERIAL PRIMARY KEY,
            platform TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            active BOOLEAN DEFAULT TRUE,
            priority INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(platform, keyword)
        )
        ''')
        
        # Create saved signals table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_signals (
            id SERIAL PRIMARY KEY,
            signal_id INTEGER REFERENCES multi_platform_signals(id) ON DELETE CASCADE,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            UNIQUE(signal_id)
        )
        ''')
        
        # Create user preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Set default urgency cutoff
        cursor.execute('''
        INSERT INTO user_preferences (key, value) VALUES ('urgency_cutoff', '10')
        ON CONFLICT (key) DO NOTHING
        ''')
        
        # Create projects table for pipeline management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            client_name TEXT NOT NULL,
            project_name TEXT NOT NULL,
            status TEXT DEFAULT 'applied',
            assigned_to TEXT,
            deadline DATE,
            hourly_rate REAL DEFAULT 20.0,
            estimated_hours INTEGER,
            platform_source TEXT,
            original_signal_id INTEGER REFERENCES multi_platform_signals(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
        ''')
        
        # Create project communications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_communications (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            communication_type TEXT DEFAULT 'client_message',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Insert default keywords for each platform
        cursor.execute('''
        INSERT INTO platform_keywords (platform, keyword, category, priority) VALUES
        ('stackoverflow', 'urgent', 'crisis', 3),
        ('stackoverflow', 'help', 'crisis', 2),
        ('stackoverflow', 'stuck', 'crisis', 2),
        ('stackoverflow', 'deadline', 'business', 3),
        ('stackoverflow', 'client', 'business', 2),
        ('hackernews', 'consulting', 'business', 3),
        ('hackernews', 'freelance', 'business', 3),
        ('hackernews', 'startup', 'business', 2),
        ('hackernews', 'advice', 'consulting', 2),
        ('producthunt', 'beta', 'opportunity', 2),
        ('producthunt', 'mvp', 'opportunity', 2),
        ('producthunt', 'scaling', 'technical', 3),
        ('reddit', 'hire', 'business', 3),
        ('reddit', 'budget', 'business', 2),
        ('upwork', 'asap', 'crisis', 3),
        ('upwork', 'urgent', 'crisis', 3),
        ('twitter', 'help', 'crisis', 3),
        ('twitter', 'urgent', 'crisis', 3),
        ('twitter', 'developer', 'business', 2),
        ('twitter', 'broken', 'crisis', 2),
        ('twitter', 'hire', 'business', 3),
        ('twitter', 'freelance', 'business', 3)
        ON CONFLICT (platform, keyword) DO NOTHING
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"Database init error: {e}")

# ============= FLASK ROUTES =============

def generate_response_templates(signal):
    """Generate auto-populated response templates based on signal content"""
    templates = {}
    
    # Extract key information
    title = signal['title'].lower()
    content = signal['content'].lower()
    urgency = signal['urgency_score']
    keywords = [kw.lower() for kw in signal['keywords_matched']]
    tech_stack = signal['tech_stack']
    platform = signal['platform']
    
    # Extract problem description for templates
    problem = signal['title']  # Use title as problem description
    username = signal['author'] if signal['author'] != 'deleted' else 'there'
    
    # Phoenix's Emotional Template (for frustrated developers)
    if any(word in title + content for word in ['frustrated', 'stuck', 'losing my mind', 'help', 'confused', 'overwhelmed', 'urgent', 'asap']):
        templates['emotional'] = f"""Hey {username}, I feel your pain - {problem} is brutal when you're working against deadlines.

I've helped a few developers work through similar issues. The key thing that usually trips people up is not having a systematic debugging approach when you're under pressure.

Quick question to help me point you in the right direction: what's your current tech stack and have you been able to isolate where the issue is occurring?

Happy to share what's worked if it would help!

(I'm Mike from Prometheus Consulting - we specialize in urgent dev fixes at $20/hour with same-day turnaround)"""

    # Phoenix's Technical Template (for specific tech problems)
    if any(word in title + content for word in ['error', 'bug', 'broken', 'not working', 'issue', 'problem']):
        templates['technical'] = f"""Hey! I can help you solve this {problem} quickly. Here's what's likely happening:

• Check your error logs first - 80% of issues show clear indicators there
• Verify your environment variables and API keys are correctly set
• Test in a clean local environment to isolate deployment vs code issues

Try checking your browser console/server logs first and you should see the root cause within 10 minutes.

If that doesn't work, the issue might be related to caching or deployment configuration. Let me know if you need help troubleshooting further!

(Mike @ Prometheus Consulting - we fix urgent dev issues at $20/hour)"""

    # Phoenix's Strategic Template (for architecture/complex issues)
    if any(word in title + content for word in ['approach', 'strategy', 'architecture', 'best practice', 'design', 'scale']):
        templates['strategic'] = f"""Interesting challenge you're facing with {problem}.

Based on what you've described, you're actually dealing with two separate issues:
1. The immediate technical problem you're seeing
2. The underlying architecture/workflow issue that's making these problems recurring

Most people attack #1 first, but fixing #2 actually prevents #1 from happening again.

Would you like me to break down a quick roadmap for tackling this systematically?

(I'm Mike from Prometheus Consulting - we help with both quick fixes and long-term solutions at $20/hour)"""

    # Phoenix's Experience Template (for advice seekers)
    if any(word in title + content for word in ['has anyone', 'anyone dealt with', 'similar situation', 'advice', 'experience']):
        templates['experience'] = f"""Oh man, {problem} - I've seen this exact scenario play out with other developers before.

Here's what worked for them:
- Week 1: Immediate stabilization and quick fixes
- Week 2-3: Proper solution implementation and testing  
- Week 4: Documentation and prevention measures

The breakthrough came when they realized the issue wasn't just technical - it was also about having reliable processes.

What's your current timeline and budget situation? That'll help me tailor this approach to your specific case.

(Mike @ Prometheus Consulting - we've solved this problem multiple times at $20/hour)"""

    # Always provide a custom template option
    templates['custom'] = f"""Hi {username},

[Personalized greeting based on their {platform} post about {problem}]

[Specific solution approach for their situation]

[Offer assistance at $20/hour with relevant experience]

Best,
Mike - Prometheus Consulting"""

    return templates

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
    
    # Get urgency cutoff preference
    cutoff = request.args.get('cutoff', None)
    
    # Get signals from database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get or update urgency cutoff
        if cutoff:
            cursor.execute('''
            INSERT INTO user_preferences (key, value) VALUES ('urgency_cutoff', %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
            ''', (cutoff,))
            conn.commit()
        
        # Get current cutoff value
        cursor.execute("SELECT value FROM user_preferences WHERE key = 'urgency_cutoff'")
        result = cursor.fetchone()
        current_cutoff = int(result['value']) if result else 10
        
        # Check for saved signals filter
        show_saved = request.args.get('saved', None)
        
        # Get signals sorted by urgency score with cutoff filter
        if show_saved:
            cursor.execute('''
            SELECT DISTINCT m.id, m.platform, m.title, m.content, m.author, m.url, m.urgency_score, 
                   m.detected_at, m.keywords_matched, m.tech_stack, 
                   CASE WHEN s.signal_id IS NOT NULL THEN TRUE ELSE FALSE END as is_saved
            FROM multi_platform_signals m
            INNER JOIN saved_signals s ON m.id = s.signal_id
            WHERE m.urgency_score >= %s
            ORDER BY m.urgency_score DESC, m.detected_at DESC 
            LIMIT 50
            ''', (current_cutoff,))
        else:
            cursor.execute('''
            SELECT m.id, m.platform, m.title, m.content, m.author, m.url, m.urgency_score, 
                   m.detected_at, m.keywords_matched, m.tech_stack,
                   CASE WHEN s.signal_id IS NOT NULL THEN TRUE ELSE FALSE END as is_saved
            FROM multi_platform_signals m
            LEFT JOIN saved_signals s ON m.id = s.signal_id
            WHERE m.urgency_score >= %s
            ORDER BY m.urgency_score DESC, m.detected_at DESC 
            LIMIT 50
            ''', (current_cutoff,))
        
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
                'tech_stack': json.loads(row['tech_stack']) if row['tech_stack'] else [],
                'is_saved': row['is_saved']
            })
        
        conn.close()
        
    except Exception as e:
        signals = []
        current_cutoff = 10
        logger.error(f"Dashboard error: {e}")
    
    return render_template_string(DASHBOARD_TEMPLATE, signals=signals, current_cutoff=current_cutoff, show_saved=show_saved)

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
        
        # Generate auto-populated templates based on signal content
        templates = generate_response_templates(signal)
        
        return render_template_string(SIGNAL_DETAIL_TEMPLATE, signal=signal, templates=templates)
        
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

@app.route('/signal/<int:signal_id>/save', methods=['POST'])
def save_signal(signal_id):
    """Save a signal for later"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO saved_signals (signal_id) VALUES (%s)
        ON CONFLICT (signal_id) DO NOTHING
        ''', (signal_id,))
        
        conn.commit()
        conn.close()
        
        return redirect(request.referrer or '/')
        
    except Exception as e:
        logger.error(f"Error saving signal: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/signal/<int:signal_id>/unsave', methods=['POST'])
def unsave_signal(signal_id):
    """Remove a signal from saved"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM saved_signals WHERE signal_id = %s', (signal_id,))
        
        conn.commit()
        conn.close()
        
        return redirect(request.referrer or '/')
        
    except Exception as e:
        logger.error(f"Error unsaving signal: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/signal/<int:signal_id>/ignore-user', methods=['POST'])
def ignore_user(signal_id):
    """Add signal author to ignore list"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get signal author and platform
        cursor.execute('SELECT author, platform FROM multi_platform_signals WHERE id = %s', (signal_id,))
        result = cursor.fetchone()
        
        if result:
            author = result['author']
            platform = result['platform']
            
            # Add to ignored users
            cursor.execute('''
            INSERT INTO ignored_users (platform, username, reason) 
            VALUES (%s, %s, %s)
            ON CONFLICT (platform, username) DO NOTHING
            ''', (platform, author, 'Spam/Low quality'))
            
            # Update the in-memory ignored users set
            monitor.ignored_users.add((platform, author))
            
            # Delete all signals from this user
            cursor.execute('''
            DELETE FROM multi_platform_signals 
            WHERE author = %s AND platform = %s
            ''', (author, platform))
            
            conn.commit()
        
        conn.close()
        return redirect('/')
        
    except Exception as e:
        logger.error(f"Error ignoring user: {e}")
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

@app.route('/keywords')
def keywords_manager():
    """Keyword management interface"""
    if not check_auth():
        return redirect('/login')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get keywords grouped by platform
        cursor.execute('''
        SELECT platform, keyword, category, active, priority 
        FROM platform_keywords 
        ORDER BY platform, priority DESC, keyword
        ''')
        
        keywords_by_platform = {}
        for row in cursor.fetchall():
            platform = row['platform']
            if platform not in keywords_by_platform:
                keywords_by_platform[platform] = []
            keywords_by_platform[platform].append({
                'keyword': row['keyword'],
                'category': row['category'],
                'active': row['active'],
                'priority': row['priority']
            })
        
        conn.close()
        
        return render_template_string(KEYWORDS_TEMPLATE, keywords=keywords_by_platform)
        
    except Exception as e:
        logger.error(f"Keywords manager error: {e}")
        return f"Error: {e}"

@app.route('/keywords/save', methods=['POST'])
def save_keywords():
    """Save all keyword changes in batch"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Process deletions
        for delete_id in data.get('deletions', []):
            platform, keyword = delete_id.split('|')
            cursor.execute('DELETE FROM platform_keywords WHERE platform = %s AND keyword = %s', 
                         (platform, keyword))
        
        # Process updates (active/inactive toggles)
        for update in data.get('updates', []):
            cursor.execute('''
            UPDATE platform_keywords 
            SET active = %s 
            WHERE platform = %s AND keyword = %s
            ''', (update['active'], update['platform'], update['keyword']))
        
        # Process additions
        for addition in data.get('additions', []):
            cursor.execute('''
            INSERT INTO platform_keywords (platform, keyword, category, priority) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (platform, keyword) DO UPDATE SET
            category = EXCLUDED.category,
            priority = EXCLUDED.priority,
            active = TRUE
            ''', (addition['platform'], addition['keyword'].lower(), 
                  addition['category'], addition['priority']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error saving keywords: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/pipeline')
def pipeline_board():
    """Project pipeline management board"""
    if not check_auth():
        return redirect('/login')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get projects grouped by status
        cursor.execute('''
        SELECT p.*, COUNT(pc.id) as communication_count
        FROM projects p
        LEFT JOIN project_communications pc ON p.id = pc.project_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
        ''')
        
        projects_by_status = {
            'applied': [],
            'hired': [],
            'in_progress': [],
            'qa': [],
            'waiting_client': [],
            'completed': []
        }
        
        for row in cursor.fetchall():
            projects_by_status[row['status']].append(dict(row))
        
        conn.close()
        
        return render_template_string(PIPELINE_TEMPLATE, projects=projects_by_status)
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        return f"Error: {e}"

@app.route('/signal/<int:signal_id>/convert-to-project', methods=['POST'])
def convert_to_project(signal_id):
    """Convert a signal to a project"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        client_name = request.form.get('client_name', 'Unknown Client')
        project_name = request.form.get('project_name', 'Project')
        estimated_hours = request.form.get('estimated_hours', 10)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get signal details
        cursor.execute('SELECT platform, author FROM multi_platform_signals WHERE id = %s', (signal_id,))
        signal = cursor.fetchone()
        
        if signal:
            cursor.execute('''
            INSERT INTO projects (client_name, project_name, platform_source, original_signal_id, estimated_hours)
            VALUES (%s, %s, %s, %s, %s)
            ''', (client_name, project_name, signal['platform'], signal_id, estimated_hours))
        
        conn.commit()
        conn.close()
        
        return redirect('/pipeline')
        
    except Exception as e:
        logger.error(f"Error converting to project: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/project/<int:project_id>/update-status', methods=['POST'])
def update_project_status(project_id):
    """Update project status"""
    if not check_auth():
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        new_status = request.form.get('status')
        assigned_to = request.form.get('assigned_to', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update project
        if new_status == 'completed':
            cursor.execute('''
            UPDATE projects 
            SET status = %s, assigned_to = %s, completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            ''', (new_status, assigned_to, project_id))
        else:
            cursor.execute('''
            UPDATE projects 
            SET status = %s, assigned_to = %s
            WHERE id = %s
            ''', (new_status, assigned_to, project_id))
        
        conn.commit()
        conn.close()
        
        return redirect('/pipeline')
        
    except Exception as e:
        logger.error(f"Error updating project: {e}")
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
        self.ignored_users = self.load_ignored_users()
    
    def load_ignored_users(self):
        """Load ignored users from database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT platform, username FROM ignored_users')
            ignored = set()
            for row in cursor.fetchall():
                ignored.add((row['platform'], row['username']))
            conn.close()
            return ignored
        except Exception as e:
            logger.error(f"Error loading ignored users: {e}")
            return set()
    
    def is_user_ignored(self, platform, username):
        """Check if user is ignored"""
        return (platform, username) in self.ignored_users
    
    def save_signal(self, signal):
        """Save a signal to the database"""
        # Check if user is ignored
        if self.is_user_ignored(signal['platform'], signal['author']):
            logger.info(f"🚫 Skipping signal from ignored user: {signal['author']}")
            return
            
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
        .ignore-btn {
            background: #ff9f43;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            float: right;
            margin-left: 10px;
        }
        .ignore-btn:hover {
            background: #ff8c00;
        }
        .save-btn {
            background: #00a8ff;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            float: right;
            margin-left: 10px;
        }
        .save-btn:hover {
            background: #0090dd;
        }
    </style>
</head>
<body>
    <a href="/logout" class="logout">Logout</a>
    
    <div class="header">
        <h1>🚨 BBT BEACON CONTROL CENTER 🚨</h1>
        <p>24/7 Developer Crisis Monitoring System</p>
        <p class="status">✅ All monitors running | Auto-refreshes every 5 minutes</p>
        <div style="text-align: center; margin-top: 15px;">
            <a href="/keywords" style="color: #00ff00; text-decoration: none; padding: 8px 15px; border: 1px solid #00ff00; border-radius: 5px; margin: 0 10px;">🔍 Manage Keywords</a>
            <a href="/pipeline" style="color: #00ff00; text-decoration: none; padding: 8px 15px; border: 1px solid #00ff00; border-radius: 5px; margin: 0 10px;">📋 Project Pipeline</a>
        </div>
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
    
    <div style="text-align: center; margin: 20px 0; padding: 15px; background: #111; border: 1px solid #00ff00; border-radius: 10px;">
        <form method="GET" action="/" style="display: inline-block; margin-right: 20px;">
            <label style="color: #00ff00; margin-right: 10px;">🎯 Minimum Urgency Score:</label>
            <input type="number" name="cutoff" value="{{ current_cutoff }}" min="0" max="100" 
                   style="width: 60px; padding: 5px; background: #0a0a0a; color: #00ff00; border: 1px solid #00ff00;">
            <button type="submit" style="padding: 5px 15px; background: #00ff00; color: #0a0a0a; border: none; border-radius: 3px; cursor: pointer;">
                Apply Filter
            </button>
        </form>
        {% if show_saved %}
        <a href="/" style="padding: 5px 15px; background: #ffaa00; color: #0a0a0a; text-decoration: none; border-radius: 3px; margin-left: 10px;">
            Show All Signals
        </a>
        {% else %}
        <a href="/?saved=true" style="padding: 5px 15px; background: #ffaa00; color: #0a0a0a; text-decoration: none; border-radius: 3px; margin-left: 10px;">
            Show Saved Only
        </a>
        {% endif %}
    </div>
    
    <h2>📡 Recent Signals</h2>
    
    {% if signals %}
        {% for signal in signals %}
        <div class="signal {{ 'urgent' if signal.urgency_score >= 30 else 'medium' if signal.urgency_score >= 15 else 'low' }}">
            <form method="POST" action="/signal/{{ signal.id }}/delete" style="display: inline;">
                <button type="submit" class="delete-btn">🗑️ Delete</button>
            </form>
            <form method="POST" action="/signal/{{ signal.id }}/ignore-user" style="display: inline;">
                <button type="submit" class="ignore-btn" onclick="return confirm('Ignore all posts from {{ signal.author }}?');">🚫 Ignore User</button>
            </form>
            {% if signal.is_saved %}
            <form method="POST" action="/signal/{{ signal.id }}/unsave" style="display: inline;">
                <button type="submit" class="save-btn" style="background: #ff6600;">⭐ Unsave</button>
            </form>
            {% else %}
            <form method="POST" action="/signal/{{ signal.id }}/save" style="display: inline;">
                <button type="submit" class="save-btn">⭐ Save</button>
            </form>
            {% endif %}
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
                <button type="submit" class="btn btn-danger">🗑️ Delete Signal</button>
            </form>
            <button onclick="showProjectForm()" class="btn btn-primary" style="margin-left: 10px;">📋 Convert to Project</button>
            <a href="/" class="back-btn">← Back to Dashboard</a>
        </div>
        
        <!-- Convert to Project Form (hidden by default) -->
        <div id="project-form" style="display: none; margin: 20px 0; padding: 20px; background: #111; border: 1px solid #00ff00; border-radius: 10px;">
            <h3>Convert Signal to Project</h3>
            <form method="POST" action="/signal/{{ signal.id }}/convert-to-project">
                <div style="margin: 10px 0;">
                    <label style="color: #00ff00;">Client Name:</label><br>
                    <input type="text" name="client_name" value="{{ signal.author }}" required 
                           style="width: 100%; padding: 8px; background: #0a0a0a; color: #00ff00; border: 1px solid #00ff00;">
                </div>
                <div style="margin: 10px 0;">
                    <label style="color: #00ff00;">Project Name:</label><br>
                    <input type="text" name="project_name" value="{{ signal.title[:50] }}" required 
                           style="width: 100%; padding: 8px; background: #0a0a0a; color: #00ff00; border: 1px solid #00ff00;">
                </div>
                <div style="margin: 10px 0;">
                    <label style="color: #00ff00;">Estimated Hours:</label><br>
                    <input type="number" name="estimated_hours" value="10" min="1" 
                           style="width: 100px; padding: 8px; background: #0a0a0a; color: #00ff00; border: 1px solid #00ff00;">
                </div>
                <button type="submit" class="btn btn-primary">Create Project</button>
                <button type="button" onclick="hideProjectForm()" class="btn btn-secondary">Cancel</button>
            </form>
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
                    <select name="template" class="template-select" id="template-select" required onchange="updateTemplatePreview()">
                        <option value="">-- Choose Template --</option>
                        {% if 'emotional' in templates %}
                        <option value="emotional">💔 Emotional Support (Frustrated Developer)</option>
                        {% endif %}
                        {% if 'technical' in templates %}
                        <option value="technical">🔧 Technical Solution (Bug/Error Fix)</option>
                        {% endif %}
                        {% if 'strategic' in templates %}
                        <option value="strategic">🏗️ Strategic Guidance (Architecture)</option>
                        {% endif %}
                        {% if 'experience' in templates %}
                        <option value="experience">🎯 Experience Share (Advice Seeker)</option>
                        {% endif %}
                        <option value="custom">✍️ Custom Response</option>
                    </select>
                </div>
                
                <div class="field">
                    <div class="field-label">TEMPLATE PREVIEW</div>
                    <textarea id="template-preview" class="notes-input" style="min-height: 300px; background: #0a0a0a; color: #00ff00;" readonly>Select a template above to see the auto-generated response...</textarea>
                </div>
                
                <div class="field">
                    <div class="field-label">NOTES (Optional)</div>
                    <textarea name="notes" class="notes-input" placeholder="Add any notes about this response..."></textarea>
                </div>
                
                <script>
                const templates = {{ templates | tojson | safe }};
                
                function updateTemplatePreview() {
                    const select = document.getElementById('template-select');
                    const preview = document.getElementById('template-preview');
                    const templateKey = select.value;
                    
                    if (templateKey && templates[templateKey]) {
                        preview.value = templates[templateKey];
                        preview.style.height = 'auto';
                        preview.style.height = preview.scrollHeight + 'px';
                    } else if (templateKey === 'custom') {
                        preview.value = templates['custom'] || 'Write your custom response here...';
                    } else {
                        preview.value = 'Select a template above to see the auto-generated response...';
                    }
                }
                </script>
                
                <button type="submit" class="btn btn-primary">Mark as Responded</button>
                <a href="{{ signal.url }}" target="_blank" class="btn btn-secondary">Open Post to Respond</a>
            </form>
        {% endif %}
    </div>
    
    <script>
    function showProjectForm() {
        document.getElementById('project-form').style.display = 'block';
    }
    
    function hideProjectForm() {
        document.getElementById('project-form').style.display = 'none';
    }
    </script>
</body>
</html>
'''

KEYWORDS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BBT Beacon Keywords Manager</title>
    <style>
        body {
            background: #0a0a0a;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
        }
        h1, h2 {
            color: #00ff00;
            text-shadow: 0 0 10px #00ff00;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .nav {
            text-align: center;
            margin-bottom: 30px;
        }
        .nav a {
            color: #00ff00;
            text-decoration: none;
            margin: 0 15px;
            padding: 10px 20px;
            border: 1px solid #00ff00;
            border-radius: 5px;
        }
        .nav a:hover {
            background: #00ff00;
            color: #0a0a0a;
        }
        .platform-section {
            margin: 30px 0;
            padding: 20px;
            border: 1px solid #00ff00;
            border-radius: 10px;
            background: #111;
        }
        .platform-title {
            color: #00ff00;
            font-size: 18px;
            margin-bottom: 15px;
            text-transform: uppercase;
        }
        .keyword-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
            margin: 15px 0;
        }
        .keyword-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            background: #1a1a1a;
            border-radius: 5px;
            border-left: 4px solid;
        }
        .keyword-item.active {
            border-left-color: #00ff00;
        }
        .keyword-item.inactive {
            border-left-color: #666;
            opacity: 0.6;
        }
        .keyword-text {
            flex: 1;
        }
        .keyword-category {
            font-size: 10px;
            color: #888;
            margin-left: 5px;
        }
        .keyword-priority {
            color: #ffff00;
            margin-left: 5px;
            font-weight: bold;
        }
        .toggle-btn {
            padding: 2px 8px;
            font-size: 10px;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            margin-left: 10px;
        }
        .toggle-btn.active {
            background: #ff6600;
            color: white;
        }
        .toggle-btn.inactive {
            background: #00ff00;
            color: #0a0a0a;
        }
        .add-form {
            margin-top: 20px;
            padding: 15px;
            background: #0a0a0a;
            border-radius: 5px;
            border: 1px solid #333;
        }
        .form-row {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
            align-items: center;
        }
        .form-input {
            padding: 8px;
            background: #1a1a1a;
            color: #00ff00;
            border: 1px solid #00ff00;
            border-radius: 3px;
            font-family: monospace;
        }
        .form-select {
            padding: 8px;
            background: #1a1a1a;
            color: #00ff00;
            border: 1px solid #00ff00;
            border-radius: 3px;
        }
        .add-btn {
            padding: 8px 15px;
            background: #00ff00;
            color: #0a0a0a;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-weight: bold;
        }
        .add-btn:hover {
            background: #00cc00;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 BBT BEACON KEYWORDS MANAGER</h1>
        <p>Manage monitoring keywords for all platforms</p>
    </div>
    
    <div class="nav">
        <a href="/">← Back to Dashboard</a>
        <a href="/keywords">Keywords Manager</a>
        <button onclick="saveAllChanges()" style="float: right; padding: 10px 20px; background: #00ff00; color: #0a0a0a; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">
            💾 SAVE ALL CHANGES
        </button>
    </div>
    
    {% for platform, platform_keywords in keywords.items() %}
    <div class="platform-section">
        <div class="platform-title">{{ platform.upper() }} Keywords</div>
        
        <div class="keyword-grid">
            {% for keyword_data in platform_keywords %}
            <div class="keyword-item {% if keyword_data.active %}active{% else %}inactive{% endif %}" 
                 id="keyword-{{ platform }}-{{ keyword_data.keyword }}" 
                 data-platform="{{ platform }}" 
                 data-keyword="{{ keyword_data.keyword }}"
                 data-active="{{ keyword_data.active|lower }}">
                <div class="keyword-text">
                    {{ keyword_data.keyword }}
                    <span class="keyword-category">[{{ keyword_data.category }}]</span>
                    <span class="keyword-priority">P{{ keyword_data.priority }}</span>
                </div>
                <button onclick="toggleKeyword('{{ platform }}', '{{ keyword_data.keyword }}')" 
                        class="toggle-btn {% if keyword_data.active %}active{% else %}inactive{% endif %}">
                    {% if keyword_data.active %}DISABLE{% else %}ENABLE{% endif %}
                </button>
                <button onclick="deleteKeyword('{{ platform }}', '{{ keyword_data.keyword }}')" 
                        class="delete-btn" style="background: #ff4757; margin-left: 5px;">
                    DELETE
                </button>
            </div>
            {% endfor %}
        </div>
        
        <div class="add-form">
            <strong>Add New Keyword for {{ platform.upper() }}:</strong>
            <form method="POST" action="/keywords/add">
                <input type="hidden" name="platform" value="{{ platform }}">
                <div class="form-row">
                    <input type="text" name="keyword" placeholder="Enter keyword..." class="form-input" required>
                    <select name="category" class="form-select">
                        <option value="general">General</option>
                        <option value="crisis">Crisis</option>
                        <option value="business">Business</option>
                        <option value="technical">Technical</option>
                        <option value="consulting">Consulting</option>
                        <option value="opportunity">Opportunity</option>
                    </select>
                    <select name="priority" class="form-select">
                        <option value="1">Priority 1 (Low)</option>
                        <option value="2">Priority 2 (Medium)</option>
                        <option value="3">Priority 3 (High)</option>
                    </select>
                    <button type="submit" class="add-btn">ADD</button>
                </div>
            </form>
        </div>
    </div>
    {% endfor %}
    
    <div class="platform-section">
        <div class="platform-title">Add Keywords for New Platform</div>
        <div class="add-form">
            <form method="POST" action="/keywords/add">
                <div class="form-row">
                    <input type="text" name="platform" placeholder="Platform name..." class="form-input" required>
                    <input type="text" name="keyword" placeholder="Keyword..." class="form-input" required>
                    <select name="category" class="form-select">
                        <option value="general">General</option>
                        <option value="crisis">Crisis</option>
                        <option value="business">Business</option>
                        <option value="technical">Technical</option>
                        <option value="consulting">Consulting</option>
                        <option value="opportunity">Opportunity</option>
                    </select>
                    <select name="priority" class="form-select">
                        <option value="1">Priority 1 (Low)</option>
                        <option value="2">Priority 2 (Medium)</option>
                        <option value="3">Priority 3 (High)</option>
                    </select>
                    <button type="submit" class="add-btn">ADD</button>
                </div>
            </form>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 40px; color: #666;">
        <p>💡 Make all your changes, then click SAVE ALL CHANGES to apply them.</p>
        <p>🚀 Built with BBT Beacon System v3.0</p>
    </div>

<script>
let pendingChanges = {
    deletions: [],
    updates: [],
    additions: []
};

function toggleKeyword(platform, keyword) {
    const element = document.getElementById(`keyword-${platform}-${keyword}`);
    const button = element.querySelector('.toggle-btn');
    const isActive = element.dataset.active === 'true';
    
    // Toggle visual state
    element.dataset.active = (!isActive).toString();
    element.className = element.className.replace(/\b(active|inactive)\b/g, isActive ? 'inactive' : 'active');
    button.className = button.className.replace(/\b(active|inactive)\b/g, isActive ? 'inactive' : 'active');
    button.textContent = isActive ? 'ENABLE' : 'DISABLE';
    
    // Track change
    const updateIndex = pendingChanges.updates.findIndex(u => u.platform === platform && u.keyword === keyword);
    if (updateIndex >= 0) {
        pendingChanges.updates[updateIndex].active = !isActive;
    } else {
        pendingChanges.updates.push({platform, keyword, active: !isActive});
    }
    
    updateSaveButton();
}

function deleteKeyword(platform, keyword) {
    if (!confirm(`Delete keyword "${keyword}" from ${platform}?`)) return;
    
    const element = document.getElementById(`keyword-${platform}-${keyword}`);
    element.style.opacity = '0.5';
    element.style.textDecoration = 'line-through';
    
    // Track deletion
    const deleteId = `${platform}|${keyword}`;
    if (!pendingChanges.deletions.includes(deleteId)) {
        pendingChanges.deletions.push(deleteId);
    }
    
    updateSaveButton();
}

function addKeyword(platform) {
    const keywordInput = document.getElementById(`new-keyword-${platform}`);
    const categorySelect = document.getElementById(`new-category-${platform}`);
    const prioritySelect = document.getElementById(`new-priority-${platform}`);
    
    const keyword = keywordInput.value.trim();
    if (!keyword) {
        alert('Please enter a keyword');
        return;
    }
    
    // Track addition
    pendingChanges.additions.push({
        platform,
        keyword: keyword.toLowerCase(),
        category: categorySelect.value,
        priority: parseInt(prioritySelect.value)
    });
    
    // Clear inputs
    keywordInput.value = '';
    categorySelect.selectedIndex = 0;
    prioritySelect.selectedIndex = 0;
    
    // Show pending addition in UI
    const grid = keywordInput.closest('.platform-section').querySelector('.keyword-grid');
    const newElement = document.createElement('div');
    newElement.className = 'keyword-item active';
    newElement.style.border = '2px dashed #00ff00';
    newElement.innerHTML = `
        <div class="keyword-text">
            ${keyword} <span class="keyword-category">[${categorySelect.value}]</span>
            <span class="keyword-priority">P${prioritySelect.value}</span>
            <span style="color: #ffff00; margin-left: 10px;">(PENDING)</span>
        </div>
    `;
    grid.appendChild(newElement);
    
    updateSaveButton();
}

function updateSaveButton() {
    const button = document.querySelector('button[onclick="saveAllChanges()"]');
    const totalChanges = pendingChanges.deletions.length + pendingChanges.updates.length + pendingChanges.additions.length;
    
    if (totalChanges > 0) {
        button.textContent = `💾 SAVE ${totalChanges} CHANGES`;
        button.style.background = '#ff6600';
        button.style.animation = 'pulse 1s infinite';
    } else {
        button.textContent = '💾 SAVE ALL CHANGES';
        button.style.background = '#00ff00';
        button.style.animation = 'none';
    }
}

async function saveAllChanges() {
    const totalChanges = pendingChanges.deletions.length + pendingChanges.updates.length + pendingChanges.additions.length;
    
    if (totalChanges === 0) {
        alert('No changes to save');
        return;
    }
    
    try {
        const response = await fetch('/keywords/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(pendingChanges)
        });
        
        if (response.ok) {
            alert(`Successfully saved ${totalChanges} changes!`);
            window.location.reload();
        } else {
            alert('Error saving changes');
        }
    } catch (error) {
        alert('Network error saving changes');
    }
}

// Add pulse animation
const style = document.createElement('style');
style.textContent = `
@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
}
`;
document.head.appendChild(style);
</script>

</body>
</html>
'''

PIPELINE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Project Pipeline - BBT Beacon</title>
    <style>
        body {
            background: #0a0a0a;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .pipeline {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 20px;
            margin-top: 30px;
        }
        .column {
            background: #111;
            border: 1px solid #00ff00;
            border-radius: 10px;
            padding: 15px;
            min-height: 400px;
        }
        .column h3 {
            text-align: center;
            margin: 0 0 15px 0;
            color: #00ff00;
            font-size: 14px;
        }
        .project-card {
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .project-card:hover {
            border-color: #00ff00;
            transform: scale(1.02);
        }
        .project-title {
            font-weight: bold;
            color: #00ff00;
            font-size: 12px;
            margin-bottom: 5px;
        }
        .project-client {
            color: #888;
            font-size: 11px;
            margin-bottom: 5px;
        }
        .project-meta {
            font-size: 10px;
            color: #666;
        }
        .assigned-tag {
            display: inline-block;
            background: #ff6600;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 9px;
            margin-top: 5px;
        }
        .nav {
            text-align: center;
            margin-bottom: 20px;
        }
        .nav a {
            color: #00ff00;
            text-decoration: none;
            margin: 0 15px;
            padding: 8px 15px;
            border: 1px solid #00ff00;
            border-radius: 5px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-box {
            background: #111;
            padding: 15px;
            text-align: center;
            border: 1px solid #00ff00;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 PROJECT PIPELINE BOARD</h1>
        <p>Freelance Project Management Dashboard</p>
    </div>
    
    <div class="nav">
        <a href="/">← Back to Dashboard</a>
        <a href="/keywords">Keywords Manager</a>
        <a href="/pipeline">Project Pipeline</a>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <h3>📝 APPLIED</h3>
            <div>{{ projects.applied|length }}</div>
        </div>
        <div class="stat-box">
            <h3>✅ HIRED</h3>
            <div>{{ projects.hired|length }}</div>
        </div>
        <div class="stat-box">
            <h3>⚡ IN PROGRESS</h3>
            <div>{{ projects.in_progress|length }}</div>
        </div>
        <div class="stat-box">
            <h3>💰 COMPLETED</h3>
            <div>{{ projects.completed|length }}</div>
        </div>
    </div>
    
    <div class="pipeline">
        <div class="column">
            <h3>📝 APPLIED</h3>
            {% for project in projects.applied %}
            <div class="project-card" onclick="editProject({{ project.id }})">
                <div class="project-title">{{ project.project_name }}</div>
                <div class="project-client">{{ project.client_name }}</div>
                <div class="project-meta">
                    {{ project.platform_source|upper }} | ${{ project.hourly_rate }}/hr
                    {% if project.estimated_hours %} | ~{{ project.estimated_hours }}h{% endif %}
                </div>
                {% if project.assigned_to %}
                <div class="assigned-tag">{{ project.assigned_to|upper }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div class="column">
            <h3>✅ HIRED</h3>
            {% for project in projects.hired %}
            <div class="project-card" onclick="editProject({{ project.id }})">
                <div class="project-title">{{ project.project_name }}</div>
                <div class="project-client">{{ project.client_name }}</div>
                <div class="project-meta">
                    {{ project.platform_source|upper }} | ${{ project.hourly_rate }}/hr
                    {% if project.estimated_hours %} | ~{{ project.estimated_hours }}h{% endif %}
                </div>
                {% if project.assigned_to %}
                <div class="assigned-tag">{{ project.assigned_to|upper }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div class="column">
            <h3>⚡ IN PROGRESS</h3>
            {% for project in projects.in_progress %}
            <div class="project-card" onclick="editProject({{ project.id }})">
                <div class="project-title">{{ project.project_name }}</div>
                <div class="project-client">{{ project.client_name }}</div>
                <div class="project-meta">
                    {{ project.platform_source|upper }} | ${{ project.hourly_rate }}/hr
                    {% if project.estimated_hours %} | ~{{ project.estimated_hours }}h{% endif %}
                </div>
                {% if project.assigned_to %}
                <div class="assigned-tag">{{ project.assigned_to|upper }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div class="column">
            <h3>🔍 QA</h3>
            {% for project in projects.qa %}
            <div class="project-card" onclick="editProject({{ project.id }})">
                <div class="project-title">{{ project.project_name }}</div>
                <div class="project-client">{{ project.client_name }}</div>
                <div class="project-meta">
                    {{ project.platform_source|upper }} | ${{ project.hourly_rate }}/hr
                    {% if project.estimated_hours %} | ~{{ project.estimated_hours }}h{% endif %}
                </div>
                {% if project.assigned_to %}
                <div class="assigned-tag">{{ project.assigned_to|upper }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div class="column">
            <h3>⏳ WAITING CLIENT</h3>
            {% for project in projects.waiting_client %}
            <div class="project-card" onclick="editProject({{ project.id }})">
                <div class="project-title">{{ project.project_name }}</div>
                <div class="project-client">{{ project.client_name }}</div>
                <div class="project-meta">
                    {{ project.platform_source|upper }} | ${{ project.hourly_rate }}/hr
                    {% if project.estimated_hours %} | ~{{ project.estimated_hours }}h{% endif %}
                </div>
                {% if project.assigned_to %}
                <div class="assigned-tag">{{ project.assigned_to|upper }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div class="column">
            <h3>💰 COMPLETED</h3>
            {% for project in projects.completed %}
            <div class="project-card" onclick="editProject({{ project.id }})">
                <div class="project-title">{{ project.project_name }}</div>
                <div class="project-client">{{ project.client_name }}</div>
                <div class="project-meta">
                    {{ project.platform_source|upper }} | ${{ project.hourly_rate }}/hr
                    {% if project.estimated_hours %} | ~{{ project.estimated_hours }}h{% endif %}
                </div>
                {% if project.assigned_to %}
                <div class="assigned-tag">{{ project.assigned_to|upper }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    
    <script>
    function editProject(projectId) {
        // For now, just show an alert. Later we can add a modal
        const newStatus = prompt('Change status to:\\n1. applied\\n2. hired\\n3. in_progress\\n4. qa\\n5. waiting_client\\n6. completed');
        const assignedTo = prompt('Assign to (bolt/capi/atlas/scout):');
        
        if (newStatus) {
            const statusMap = {
                '1': 'applied',
                '2': 'hired', 
                '3': 'in_progress',
                '4': 'qa',
                '5': 'waiting_client',
                '6': 'completed'
            };
            
            const status = statusMap[newStatus];
            if (status) {
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = `/project/${projectId}/update-status`;
                
                const statusInput = document.createElement('input');
                statusInput.type = 'hidden';
                statusInput.name = 'status';
                statusInput.value = status;
                form.appendChild(statusInput);
                
                if (assignedTo) {
                    const assignInput = document.createElement('input');
                    assignInput.type = 'hidden';
                    assignInput.name = 'assigned_to';
                    assignInput.value = assignedTo.toLowerCase();
                    form.appendChild(assignInput);
                }
                
                document.body.appendChild(form);
                form.submit();
            }
        }
    }
    </script>
</body>
</html>
'''

# ============= MAIN STARTUP =============

# Global monitor instance
monitor = None

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
#!/usr/bin/env python3
"""
BBT Beacon Runner - Orchestrates all monitoring services
Runs continuously on Railway
"""

import os
import time
import threading
import sqlite3
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
)
logger = logging.getLogger('BeaconRunner')

class BeaconRunner:
    def __init__(self):
        self.running = True
        self.init_database()
        
        # Load credentials from environment
        self.credentials = {
            'reddit_client_id': os.getenv('REDDIT_CLIENT_ID'),
            'reddit_client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
            'twitter_bearer_token': os.getenv('TWITTER_BEARER_TOKEN'),
            'discord_bot_token': os.getenv('DISCORD_BOT_TOKEN'),
            'email_from': os.getenv('EMAIL_FROM'),
            'email_password': os.getenv('EMAIL_PASSWORD'),
        }
        
        logger.info("🚀 BBT Beacon Runner initialized")
        
    def init_database(self):
        """Initialize the signals database"""
        conn = sqlite3.connect('distress_beacon.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS multi_platform_signals (
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
    
    def save_signal(self, signal):
        """Save a signal to the database"""
        try:
            conn = sqlite3.connect('distress_beacon.db')
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT OR IGNORE INTO multi_platform_signals 
            (platform, platform_id, title, content, author, url, created_utc, 
             urgency_score, budget_range, tech_stack, keywords_matched)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    
    def reddit_monitor(self):
        """Monitor Reddit for crisis signals"""
        if not self.credentials['reddit_client_id']:
            logger.warning("⚠️ Reddit credentials not found - using mock data")
            self.generate_mock_reddit_signals()
            return
            
        try:
            import praw
            
            reddit = praw.Reddit(
                client_id=self.credentials['reddit_client_id'],
                client_secret=self.credentials['reddit_client_secret'],
                user_agent='BBTBeacon/1.0'
            )
            
            subreddits = ['webdev', 'programming', 'learnprogramming', 'freelance']
            
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
                                    'content': post.selftext[:500],
                                    'author': str(post.author),
                                    'url': f"https://reddit.com{post.permalink}",
                                    'created_utc': post.created_utc,
                                    'urgency_score': urgency_score,
                                    'tech_stack': json.dumps(self.extract_tech_stack(post.title + ' ' + post.selftext)),
                                    'keywords_matched': json.dumps(self.get_matched_keywords(post.title + ' ' + post.selftext))
                                }
                                
                                self.save_signal(signal)
                        
                        time.sleep(2)  # Rate limiting
                        
                    except Exception as e:
                        logger.error(f"❌ Reddit error for r/{subreddit_name}: {e}")
                
                logger.info("🔴 Reddit scan complete, sleeping 5 minutes...")
                time.sleep(300)  # 5 minutes
                
        except Exception as e:
            logger.error(f"❌ Reddit monitor error: {e}")
            self.generate_mock_reddit_signals()
    
    def twitter_monitor(self):
        """Monitor Twitter for crisis signals"""
        if not self.credentials['twitter_bearer_token']:
            logger.warning("⚠️ Twitter credentials not found - using mock data")
            self.generate_mock_twitter_signals()
            return
            
        try:
            import requests
            
            headers = {
                'Authorization': f"Bearer {self.credentials['twitter_bearer_token']}"
            }
            
            # Premium search queries for high-ROI prospects
            search_queries = [
                '"need developer" ("will pay" OR "budget" OR "$")',
                '"hire developer" ("immediately" OR "urgent" OR "asap")',
                '"website broken" ("need fixed" OR "pay")',
                '"production down" ("developer" OR "programmer")'
            ]
            
            api_calls_today = 0
            max_calls_per_day = 3  # Stay within free tier
            
            while self.running and api_calls_today < max_calls_per_day:
                for query in search_queries:
                    if api_calls_today >= max_calls_per_day:
                        break
                        
                    try:
                        url = f"https://api.twitter.com/2/tweets/search/recent"
                        params = {
                            'query': query,
                            'max_results': 10,
                            'tweet.fields': 'created_at,author_id,public_metrics'
                        }
                        
                        response = requests.get(url, headers=headers, params=params)
                        api_calls_today += 1
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            for tweet in data.get('data', []):
                                urgency_score = self.calculate_urgency(tweet['text'], '')
                                
                                if urgency_score >= 15:  # Higher threshold for Twitter
                                    signal = {
                                        'platform': 'twitter',
                                        'platform_id': tweet['id'],
                                        'title': tweet['text'][:100] + '...',
                                        'content': tweet['text'],
                                        'author': f"User_{tweet['author_id']}",
                                        'url': f"https://twitter.com/i/web/status/{tweet['id']}",
                                        'created_utc': time.time(),
                                        'urgency_score': urgency_score,
                                        'tech_stack': json.dumps(self.extract_tech_stack(tweet['text'])),
                                        'keywords_matched': json.dumps(self.get_matched_keywords(tweet['text']))
                                    }
                                    
                                    self.save_signal(signal)
                        
                        logger.info(f"🐦 Twitter API call {api_calls_today}/{max_calls_per_day}")
                        time.sleep(60)  # 1 minute between calls
                        
                    except Exception as e:
                        logger.error(f"❌ Twitter search error: {e}")
                
                # Wait until tomorrow to reset API calls
                logger.info("🐦 Twitter daily limit reached, waiting 24 hours...")
                time.sleep(86400)  # 24 hours
                api_calls_today = 0
                
        except Exception as e:
            logger.error(f"❌ Twitter monitor error: {e}")
            self.generate_mock_twitter_signals()
    
    def upwork_monitor(self):
        """Monitor Upwork RSS feeds"""
        try:
            import feedparser
            
            feeds = [
                'https://www.upwork.com/ab/feed/jobs/rss?q=urgent+developer&sort=recency',
                'https://www.upwork.com/ab/feed/jobs/rss?q=need+developer+help&sort=recency',
                'https://www.upwork.com/ab/feed/jobs/rss?q=website+broken&sort=recency'
            ]
            
            while self.running:
                for feed_url in feeds:
                    try:
                        feed = feedparser.parse(feed_url)
                        
                        for entry in feed.entries[:5]:  # Latest 5 from each feed
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
                                    'budget_range': self.extract_budget(entry.title + ' ' + entry.get('summary', '')),
                                    'tech_stack': json.dumps(self.extract_tech_stack(entry.title + ' ' + entry.get('summary', ''))),
                                    'keywords_matched': json.dumps(self.get_matched_keywords(entry.title + ' ' + entry.get('summary', '')))
                                }
                                
                                self.save_signal(signal)
                        
                        time.sleep(2)  # Rate limiting
                        
                    except Exception as e:
                        logger.error(f"❌ Upwork feed error: {e}")
                
                logger.info("💼 Upwork scan complete, sleeping 10 minutes...")
                time.sleep(600)  # 10 minutes
                
        except Exception as e:
            logger.error(f"❌ Upwork monitor error: {e}")
    
    def calculate_urgency(self, title, content):
        """Calculate urgency score for any text"""
        score = 0
        text = (title + ' ' + content).lower()
        
        # Crisis keywords with scores
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
        
        return min(score, 50)  # Cap at 50
    
    def extract_tech_stack(self, text):
        """Extract technology mentions"""
        tech_keywords = [
            'react', 'node', 'javascript', 'python', 'typescript',
            'django', 'flask', 'express', 'mongodb', 'postgresql',
            'aws', 'docker', 'api', 'nextjs', 'vue', 'angular'
        ]
        
        text_lower = text.lower()
        return [tech for tech in tech_keywords if tech in text_lower]
    
    def extract_budget(self, text):
        """Extract budget information"""
        import re
        budget_patterns = [
            r'\$(\d+)\s*-\s*\$(\d+)',
            r'Budget:\s*\$(\d+)',
            r'\$(\d+)\s*USD'
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return 'Not specified'
    
    def get_matched_keywords(self, text):
        """Get all matched crisis keywords"""
        matched = []
        text_lower = text.lower()
        
        keywords = ['urgent', 'help', 'broken', 'stuck', 'deadline', 'emergency', 'will pay']
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return matched
    
    def generate_mock_reddit_signals(self):
        """Generate mock Reddit signals for testing"""
        mock_signals = [
            {
                'platform': 'reddit',
                'platform_id': f'mock_reddit_{int(time.time())}',
                'title': 'Urgent help needed - React app crashing in production',
                'content': 'My React app is down and I have a client presentation tomorrow. Willing to pay for immediate help!',
                'author': 'desperate_dev_123',
                'url': 'https://reddit.com/r/webdev/mock',
                'created_utc': time.time(),
                'urgency_score': 35,
                'tech_stack': '["react", "javascript"]',
                'keywords_matched': '["urgent", "help", "willing to pay"]'
            }
        ]
        
        for signal in mock_signals:
            self.save_signal(signal)
            time.sleep(300)  # Every 5 minutes
    
    def generate_mock_twitter_signals(self):
        """Generate mock Twitter signals for testing"""
        mock_signals = [
            {
                'platform': 'twitter',
                'platform_id': f'mock_twitter_{int(time.time())}',
                'title': 'Need developer immediately - site is down!',
                'content': 'Our e-commerce site is completely broken. Need a developer ASAP, will pay well for quick fix!',
                'author': 'business_owner',
                'url': 'https://twitter.com/mock/status/123',
                'created_utc': time.time(),
                'urgency_score': 40,
                'tech_stack': '["javascript", "react"]',
                'keywords_matched': '["need", "immediately", "will pay", "asap"]'
            }
        ]
        
        for signal in mock_signals:
            self.save_signal(signal)
            time.sleep(600)  # Every 10 minutes
    
    def github_monitor(self):
        """Monitor GitHub Issues for help wanted / urgent bugs"""
        try:
            import requests
            
            # GitHub search queries for urgent help
            search_queries = [
                'help wanted',
                'urgent bug',
                'critical bug', 
                'production bug',
                'need help',
                'bounty'
            ]
            
            while self.running:
                for query in search_queries:
                    try:
                        url = "https://api.github.com/search/issues"
                        params = {
                            'q': f'{query} is:open',
                            'sort': 'created',
                            'per_page': 10
                        }
                        
                        response = requests.get(url, params=params)
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            for issue in data.get('items', []):
                                urgency_score = self.calculate_urgency(issue['title'], issue.get('body', ''))
                                
                                if urgency_score >= 8:  # GitHub threshold
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
                        
                        time.sleep(12)  # 5 calls per minute = 60/hour limit
                        
                    except Exception as e:
                        logger.error(f"❌ GitHub search error: {e}")
                
                logger.info("🐙 GitHub scan complete, sleeping 10 minutes...")
                time.sleep(600)  # 10 minutes
                
        except Exception as e:
            logger.error(f"❌ GitHub monitor error: {e}")

    def run(self):
        """Start all monitoring threads"""
        logger.info("🚀 Starting all beacon monitors...")
        
        # Start monitoring threads
        threads = [
            threading.Thread(target=self.reddit_monitor, daemon=True),
            threading.Thread(target=self.twitter_monitor, daemon=True),
            threading.Thread(target=self.upwork_monitor, daemon=True),
            threading.Thread(target=self.github_monitor, daemon=True)
        ]
        
        for thread in threads:
            thread.start()
        
        logger.info("✅ All monitors started!")
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(60)
                logger.info("💓 Beacon runner heartbeat - all systems operational")
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down beacon runner...")
            self.running = False

if __name__ == "__main__":
    runner = BeaconRunner()
    runner.run()
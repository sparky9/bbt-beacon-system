#!/usr/bin/env python3
"""
🚨 REDDIT BEACON PLUGIN 🚨
Monitors Reddit for developer crisis signals

Plugin for BBT Beacon Engine v3.0
"""

import praw
import time
from datetime import datetime
from typing import List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from beacon_engine import BaseBeacon, SignalData
import logging

logger = logging.getLogger('RedditBeacon')

class RedditBeacon(BaseBeacon):
    """Reddit monitoring beacon plugin"""
    
    platform_name = "reddit"
    platform_color = "#FF4500"
    requires_auth = True
    scan_interval = 300  # 5 minutes
    
    def initialize(self):
        """Initialize Reddit API connection"""
        try:
            self.reddit = praw.Reddit(
                client_id=self.credentials.get('client_id'),
                client_secret=self.credentials.get('client_secret'),
                user_agent=self.credentials.get('user_agent', 'BBTBeacon/1.0')
            )
            
            # Test connection
            self.reddit.user.me()  # This will fail if credentials are wrong
            logger.info("✅ Reddit API connection established")
            
        except Exception as e:
            logger.error(f"❌ Reddit API setup failed: {e}")
            self.enabled = False
    
    def scan_for_signals(self) -> List[SignalData]:
        """Scan Reddit subreddits for developer crisis signals"""
        if not self.enabled:
            return []
        
        signals = []
        subreddits = self.platform_config.get('subreddits', ['webdev', 'programming'])
        
        try:
            for subreddit_name in subreddits:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # Get recent posts (last hour)
                for post in subreddit.new(limit=25):
                    # Skip if too old (older than 1 hour)
                    post_age = time.time() - post.created_utc
                    if post_age > 3600:  # 1 hour
                        continue
                    
                    # Check if it's a crisis signal
                    if self.is_crisis_signal(post.title, post.selftext):
                        signal = SignalData(
                            platform="reddit",
                            platform_id=f"reddit_{post.id}",
                            title=post.title,
                            content=post.selftext[:500],  # Limit content
                            author=str(post.author) if post.author else "deleted",
                            url=f"https://reddit.com{post.permalink}",
                            created_utc=post.created_utc,
                            tech_stack=self.extract_tech_stack(post.title + " " + post.selftext),
                            keywords_matched=self.get_matched_keywords(post.title + " " + post.selftext)
                        )
                        
                        signals.append(signal)
        
        except Exception as e:
            logger.error(f"Reddit scan error: {e}")
        
        return signals
    
    def is_crisis_signal(self, title: str, content: str) -> bool:
        """Determine if a post is a developer crisis signal"""
        text = (title + " " + content).lower()
        
        # Crisis keywords
        crisis_keywords = [
            'help', 'stuck', 'error', 'bug', 'broken', 'not working',
            'urgent', 'asap', 'deadline', 'emergency', 'critical',
            'freelance', 'hire', 'looking for', 'need developer',
            'pay', 'budget', 'project'
        ]
        
        # Must have at least 2 crisis keywords or specific phrases
        keyword_count = sum(1 for keyword in crisis_keywords if keyword in text)
        
        # High-value phrases
        high_value_phrases = [
            'looking for developer', 'need help with', 'hire freelancer',
            'urgent project', 'willing to pay', 'has budget'
        ]
        
        has_high_value = any(phrase in text for phrase in high_value_phrases)
        
        return keyword_count >= 2 or has_high_value
    
    def extract_tech_stack(self, text: str) -> str:
        """Extract technology stack from post text"""
        text_lower = text.lower()
        techs = []
        
        tech_keywords = {
            'javascript': ['javascript', 'js', 'node.js', 'nodejs'],
            'python': ['python', 'django', 'flask', 'fastapi'],
            'react': ['react', 'reactjs', 'next.js', 'nextjs'],
            'php': ['php', 'laravel', 'wordpress', 'drupal'],
            'java': ['java', 'spring', 'springboot'],
            'database': ['mysql', 'postgresql', 'mongodb', 'sql'],
            'mobile': ['android', 'ios', 'react native', 'flutter'],
            'web': ['html', 'css', 'web development', 'frontend', 'backend']
        }
        
        for tech, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                techs.append(tech)
        
        return ', '.join(techs)
    
    def get_matched_keywords(self, text: str) -> str:
        """Get list of matched crisis keywords"""
        text_lower = text.lower()
        matched = []
        
        keywords = [
            'urgent', 'help', 'stuck', 'broken', 'bug', 'error',
            'freelance', 'hire', 'pay', 'budget', 'deadline'
        ]
        
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return ', '.join(matched)
    
    def calculate_urgency_score(self, signal: SignalData) -> int:
        """Reddit-specific urgency scoring"""
        base_score = super().calculate_urgency_score(signal)
        
        # Reddit-specific adjustments
        text = (signal.title + " " + signal.content).lower()
        
        # Boost for specific Reddit patterns
        if '[urgent]' in text or '[help]' in text:
            base_score += 15
        
        if 'willing to pay' in text or 'has budget' in text:
            base_score += 20
        
        if 'freelance' in text or 'hire' in text:
            base_score += 10
        
        # Posts in /r/forhire or similar get priority
        if 'forhire' in signal.url:
            base_score += 25
        
        return min(100, base_score)
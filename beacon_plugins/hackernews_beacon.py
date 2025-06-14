#!/usr/bin/env python3
"""
🚨 HACKER NEWS BEACON PLUGIN 🚨
Monitors Hacker News for developer crisis signals and consulting opportunities

Plugin for BBT Beacon Engine v3.0
"""

import requests
import feedparser
import time
import re
from datetime import datetime
from typing import List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from beacon_engine import BaseBeacon, SignalData
import logging

logger = logging.getLogger('HackerNewsBeacon')

class HackerNewsBeacon(BaseBeacon):
    """Hacker News monitoring beacon plugin"""
    
    platform_name = "hackernews"
    platform_color = "#FF6600"
    requires_auth = False
    scan_interval = 900  # 15 minutes (HN is slower moving)
    
    def initialize(self):
        """Initialize Hacker News monitoring"""
        self.api_base = "https://hacker-news.firebaseio.com/v0"
        self.rss_feed = "https://news.ycombinator.com/rss"
        
        # Ask HN specific searches
        self.ask_hn_keywords = [
            'help', 'advice', 'consulting', 'freelance', 'hire',
            'developer', 'urgent', 'stuck', 'problem', 'crisis'
        ]
        
        logger.info("✅ Hacker News monitoring initialized")
    
    def scan_for_signals(self) -> List[SignalData]:
        """Scan Hacker News for crisis signals"""
        signals = []
        
        try:
            # First, scan RSS feed for recent posts
            signals.extend(self._scan_rss_feed())
            
            # Then scan for Ask HN posts specifically
            signals.extend(self._scan_ask_hn())
            
        except Exception as e:
            logger.error(f"Hacker News scan error: {e}")
        
        return signals
    
    def _scan_rss_feed(self) -> List[SignalData]:
        """Scan HN RSS feed for relevant posts"""
        signals = []
        
        try:
            feed = feedparser.parse(self.rss_feed)
            
            for entry in feed.entries[:20]:  # Check recent 20 posts
                # Check if entry is recent (last 4 hours - HN moves slower)
                if hasattr(entry, 'published_parsed'):
                    entry_time = time.mktime(entry.published_parsed)
                    if time.time() - entry_time > 14400:  # 4 hours
                        continue
                
                title = entry.title
                content = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                post_url = entry.link
                
                # Check if it's a crisis signal or consulting opportunity
                if self.is_crisis_signal(title, content):
                    signal = SignalData(
                        platform="hackernews",
                        platform_id=f"hn_{hash(post_url)}",
                        title=title,
                        content=self.clean_content(content),
                        author=getattr(entry, 'author', 'HN User'),
                        url=post_url,
                        created_utc=entry_time if hasattr(entry, 'published_parsed') else time.time(),
                        estimated_value=self.estimate_hn_value(title, content),
                        tech_stack=self.extract_tech_stack(title + " " + content),
                        keywords_matched=self.get_matched_keywords(title + " " + content)
                    )
                    
                    signals.append(signal)
                    
        except Exception as e:
            logger.error(f"Error scanning HN RSS: {e}")
        
        return signals
    
    def _scan_ask_hn(self) -> List[SignalData]:
        """Scan for Ask HN posts using the API"""
        signals = []
        
        try:
            # Get recent stories
            response = requests.get(f"{self.api_base}/newstories.json", timeout=10)
            story_ids = response.json()[:50]  # Check recent 50 stories
            
            for story_id in story_ids:
                try:
                    # Get story details
                    story_response = requests.get(f"{self.api_base}/item/{story_id}.json", timeout=5)
                    story = story_response.json()
                    
                    if not story or not story.get('title'):
                        continue
                    
                    title = story.get('title', '')
                    content = story.get('text', '')
                    
                    # Only process Ask HN posts
                    if not title.lower().startswith('ask hn'):
                        continue
                    
                    # Check age (last 4 hours)
                    if time.time() - story.get('time', 0) > 14400:
                        continue
                    
                    # Check if it's a consulting opportunity
                    if self.is_ask_hn_opportunity(title, content):
                        post_url = f"https://news.ycombinator.com/item?id={story_id}"
                        
                        signal = SignalData(
                            platform="hackernews",
                            platform_id=f"hn_ask_{story_id}",
                            title=title,
                            content=self.clean_content(content),
                            author=story.get('by', 'HN User'),
                            url=post_url,
                            created_utc=story.get('time', time.time()),
                            estimated_value=self.estimate_ask_hn_value(title, content),
                            tech_stack=self.extract_tech_stack(title + " " + content),
                            keywords_matched=self.get_matched_keywords(title + " " + content)
                        )
                        
                        signals.append(signal)
                        
                except Exception as e:
                    logger.error(f"Error processing HN story {story_id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scanning Ask HN: {e}")
        
        return signals
    
    def is_crisis_signal(self, title: str, content: str) -> bool:
        """Check if post indicates a crisis or opportunity"""
        text = (title + " " + content).lower()
        
        # Crisis keywords
        crisis_keywords = [
            'help', 'advice', 'stuck', 'problem', 'issue',
            'urgent', 'critical', 'failing', 'broken',
            'startup crisis', 'need consultant', 'hire'
        ]
        
        # Business opportunity keywords
        business_keywords = [
            'consulting', 'freelance', 'contractor', 'developer',
            'startup', 'small business', 'technical advisor'
        ]
        
        # Ask HN specific patterns
        ask_patterns = [
            'ask hn: need help',
            'ask hn: looking for',
            'ask hn: urgent',
            'ask hn: advice on'
        ]
        
        crisis_count = sum(1 for keyword in crisis_keywords if keyword in text)
        business_count = sum(1 for keyword in business_keywords if keyword in text)
        has_ask_pattern = any(pattern in text for pattern in ask_patterns)
        
        return crisis_count >= 1 or business_count >= 1 or has_ask_pattern
    
    def is_ask_hn_opportunity(self, title: str, content: str) -> bool:
        """Specifically check Ask HN posts for consulting opportunities"""
        text = (title + " " + content).lower()
        
        # High-value Ask HN patterns
        opportunity_patterns = [
            'need help with',
            'looking for developer',
            'hire a consultant',
            'technical advice',
            'startup problem',
            'business advice',
            'architecture help',
            'code review',
            'system design'
        ]
        
        # Technology + help patterns
        tech_help_patterns = [
            'react help', 'javascript help', 'python help',
            'database design', 'api design', 'architecture',
            'performance issue', 'scaling problem'
        ]
        
        has_opportunity = any(pattern in text for pattern in opportunity_patterns)
        has_tech_help = any(pattern in text for pattern in tech_help_patterns)
        
        return has_opportunity or has_tech_help
    
    def estimate_hn_value(self, title: str, content: str) -> float:
        """Estimate consulting value from HN post"""
        text = (title + " " + content).lower()
        base_value = 300  # Higher base for HN (tech-savvy audience)
        
        # Startup context (higher budgets)
        if any(word in text for word in ['startup', 'company', 'business']):
            base_value *= 2
        
        # Technical complexity
        complex_terms = ['architecture', 'scaling', 'system design', 'performance']
        if any(term in text for term in complex_terms):
            base_value *= 1.8
        
        # Urgency multiplier
        if any(word in text for word in ['urgent', 'critical', 'asap']):
            base_value *= 1.5
        
        return min(1500, base_value)  # Cap at $1500
    
    def estimate_ask_hn_value(self, title: str, content: str) -> float:
        """Estimate value specifically for Ask HN posts"""
        text = (title + " " + content).lower()
        base_value = 500  # Higher base for Ask HN
        
        # Strategic/business advice (premium consulting)
        strategic_terms = ['strategy', 'business model', 'technical advisor', 'cto']
        if any(term in text for term in strategic_terms):
            base_value *= 3
        
        # Technical architecture
        if any(word in text for word in ['architecture', 'system design', 'scaling']):
            base_value *= 2
        
        return min(2000, base_value)
    
    def clean_content(self, content: str) -> str:
        """Clean and truncate content"""
        if not content:
            return ""
        
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', ' ', content)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Truncate
        return clean[:400] + "..." if len(clean) > 400 else clean
    
    def extract_tech_stack(self, text: str) -> str:
        """Extract technology stack"""
        text_lower = text.lower()
        techs = []
        
        tech_keywords = {
            'javascript': ['javascript', 'js', 'node.js', 'nodejs', 'react', 'vue'],
            'python': ['python', 'django', 'flask', 'fastapi'],
            'go': ['golang', 'go lang', 'go'],
            'rust': ['rust', 'cargo'],
            'database': ['postgresql', 'mysql', 'mongodb', 'redis'],
            'cloud': ['aws', 'gcp', 'azure', 'docker', 'kubernetes'],
            'mobile': ['ios', 'android', 'mobile app', 'react native'],
            'blockchain': ['blockchain', 'crypto', 'bitcoin', 'ethereum']
        }
        
        for tech, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                techs.append(tech)
        
        return ', '.join(techs)
    
    def get_matched_keywords(self, text: str) -> str:
        """Get matched opportunity keywords"""
        text_lower = text.lower()
        matched = []
        
        keywords = [
            'help', 'advice', 'consulting', 'freelance', 'hire',
            'urgent', 'startup', 'problem', 'architecture', 'scaling'
        ]
        
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return ', '.join(matched)
    
    def calculate_urgency_score(self, signal: SignalData) -> int:
        """HN-specific urgency scoring"""
        base_score = super().calculate_urgency_score(signal)
        
        text = (signal.title + " " + signal.content).lower()
        
        # Ask HN posts get priority
        if signal.title.lower().startswith('ask hn'):
            base_score += 15
        
        # Startup/business context
        if any(word in text for word in ['startup', 'business', 'company']):
            base_score += 20
        
        # Technical complexity
        if any(word in text for word in ['architecture', 'scaling', 'system']):
            base_score += 15
        
        # Consulting-specific terms
        if any(word in text for word in ['consulting', 'advisor', 'hire']):
            base_score += 25
        
        return min(100, base_score)
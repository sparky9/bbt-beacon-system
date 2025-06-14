#!/usr/bin/env python3
"""
🚨 STACK OVERFLOW BEACON PLUGIN 🚨
Monitors Stack Overflow for developer crisis signals and consulting opportunities

Plugin for BBT Beacon Engine v3.0
"""

import feedparser
import requests
import time
import re
from datetime import datetime
from typing import List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from beacon_engine import BaseBeacon, SignalData
import logging

logger = logging.getLogger('StackOverflowBeacon')

class StackOverflowBeacon(BaseBeacon):
    """Stack Overflow monitoring beacon plugin"""
    
    platform_name = "stackoverflow"
    platform_color = "#F58025"
    requires_auth = False  # RSS feeds are public
    scan_interval = 600  # 10 minutes
    
    def initialize(self):
        """Initialize Stack Overflow RSS feeds"""
        # RSS feeds for different crisis signals
        self.rss_feeds = self.platform_config.get('rss_feeds', [
            'https://stackoverflow.com/feeds/tag/help',
            'https://stackoverflow.com/feeds/tag/urgent',
            'https://stackoverflow.com/feeds/tag/javascript',
            'https://stackoverflow.com/feeds/tag/react',
            'https://stackoverflow.com/feeds/tag/python',
            'https://stackoverflow.com/feeds/tag/node.js',
            'https://stackoverflow.com/feeds/tag/debugging',
            'https://stackoverflow.com/feeds/tag/error'
        ])
        
        # API endpoint for more targeted searches
        self.api_base = "https://api.stackexchange.com/2.3"
        
        logger.info(f"✅ Stack Overflow feeds configured: {len(self.rss_feeds)} feeds")
    
    def scan_for_signals(self) -> List[SignalData]:
        """Scan Stack Overflow for crisis signals"""
        signals = []
        
        try:
            # Scan RSS feeds
            for feed_url in self.rss_feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    
                    for entry in feed.entries[:5]:  # Limit to recent 5 per feed
                        # Check if entry is recent (last 2 hours)
                        if hasattr(entry, 'published_parsed'):
                            entry_time = time.mktime(entry.published_parsed)
                            if time.time() - entry_time > 7200:  # 2 hours
                                continue
                        
                        # Extract question details
                        title = entry.title
                        content = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                        question_url = entry.link
                        
                        # Check if it's a crisis signal
                        if self.is_crisis_signal(title, content):
                            urgency_score = self.calculate_question_urgency(title, content)
                            estimated_value = self.estimate_consulting_value(title, content)
                            
                            signal = SignalData(
                                platform="stackoverflow",
                                platform_id=f"so_{hash(question_url)}",
                                title=title,
                                content=self.clean_content(content),
                                author=getattr(entry, 'author', 'Stack Overflow User'),
                                url=question_url,
                                created_utc=entry_time if hasattr(entry, 'published_parsed') else time.time(),
                                estimated_value=estimated_value,
                                tech_stack=self.extract_tech_stack(title + " " + content),
                                keywords_matched=self.get_matched_keywords(title + " " + content),
                                urgency_score=urgency_score
                            )
                            
                            signals.append(signal)
                            
                except Exception as e:
                    logger.error(f"Error parsing SO feed {feed_url}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Stack Overflow scan error: {e}")
        
        return signals
    
    def is_crisis_signal(self, title: str, content: str) -> bool:
        """Determine if a Stack Overflow question is a crisis signal"""
        text = (title + " " + content).lower()
        
        # Crisis indicators
        crisis_keywords = [
            'urgent', 'asap', 'quickly', 'immediately', 'help',
            'stuck', 'broken', 'not working', 'error', 'bug',
            'deadline', 'client', 'production', 'live site',
            'desperate', 'please help', 'emergency'
        ]
        
        # Business context indicators (consulting opportunities)
        business_keywords = [
            'freelance', 'hire', 'consultant', 'expert',
            'project', 'client work', 'production',
            'small business', 'startup', 'company'
        ]
        
        # Must have crisis indicators
        crisis_count = sum(1 for keyword in crisis_keywords if keyword in text)
        business_count = sum(1 for keyword in business_keywords if keyword in text)
        
        # High-priority patterns
        urgent_patterns = [
            'please help urgent',
            'need help asap',
            'production is down',
            'client deadline',
            'site is broken',
            'not working urgent'
        ]
        
        has_urgent_pattern = any(pattern in text for pattern in urgent_patterns)
        
        return crisis_count >= 2 or business_count >= 1 or has_urgent_pattern
    
    def calculate_question_urgency(self, title: str, content: str) -> int:
        """Calculate urgency score for Stack Overflow question"""
        text = (title + " " + content).lower()
        score = 30  # Base score
        
        # Time-sensitive indicators
        time_urgent = ['urgent', 'asap', 'immediately', 'quickly', 'today']
        score += sum(15 for keyword in time_urgent if keyword in text)
        
        # Production/business impact
        production_keywords = ['production', 'live', 'client', 'deadline', 'business']
        score += sum(20 for keyword in production_keywords if keyword in text)
        
        # Technical severity
        severity_keywords = ['broken', 'down', 'not working', 'crash', 'error']
        score += sum(10 for keyword in severity_keywords if keyword in text)
        
        # Question age (newer = more urgent)
        # This would need the actual posting time
        
        return min(100, score)
    
    def estimate_consulting_value(self, title: str, content: str) -> float:
        """Estimate potential consulting value from question"""
        text = (title + " " + content).lower()
        
        # Base consulting value
        base_value = 100  # Minimum consultation
        
        # Technology complexity multipliers
        complex_tech = ['react', 'node.js', 'database', 'api', 'aws', 'docker']
        if any(tech in text for tech in complex_tech):
            base_value *= 3
        
        # Business context indicators
        business_indicators = ['production', 'client', 'company', 'business']
        if any(indicator in text for indicator in business_indicators):
            base_value *= 2
        
        # Urgency multiplier
        urgent_indicators = ['urgent', 'asap', 'deadline']
        if any(indicator in text for indicator in urgent_indicators):
            base_value *= 1.5
        
        # Project scope indicators
        large_scope = ['entire', 'full', 'complete', 'system', 'application']
        if any(scope in text for scope in large_scope):
            base_value *= 2
        
        return min(2000, base_value)  # Cap at $2000
    
    def clean_content(self, content: str) -> str:
        """Clean and truncate content"""
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', ' ', content)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Truncate
        return clean[:400] + "..." if len(clean) > 400 else clean
    
    def extract_tech_stack(self, text: str) -> str:
        """Extract technology stack from question"""
        text_lower = text.lower()
        techs = []
        
        tech_keywords = {
            'javascript': ['javascript', 'js', 'node.js', 'nodejs', 'npm'],
            'react': ['react', 'reactjs', 'next.js', 'nextjs', 'jsx'],
            'python': ['python', 'django', 'flask', 'fastapi', 'pip'],
            'java': ['java', 'spring', 'springboot', 'maven', 'gradle'],
            'php': ['php', 'laravel', 'wordpress', 'composer'],
            'database': ['mysql', 'postgresql', 'mongodb', 'sql', 'database'],
            'web': ['html', 'css', 'frontend', 'backend', 'web'],
            'mobile': ['android', 'ios', 'mobile', 'app'],
            'cloud': ['aws', 'azure', 'docker', 'kubernetes', 'cloud']
        }
        
        for tech, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                techs.append(tech)
        
        return ', '.join(techs)
    
    def get_matched_keywords(self, text: str) -> str:
        """Get matched crisis keywords"""
        text_lower = text.lower()
        matched = []
        
        keywords = [
            'urgent', 'help', 'stuck', 'broken', 'error', 'bug',
            'asap', 'deadline', 'client', 'production', 'not working'
        ]
        
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return ', '.join(matched)
    
    def calculate_urgency_score(self, signal: SignalData) -> int:
        """Stack Overflow specific urgency scoring"""
        base_score = super().calculate_urgency_score(signal)
        
        # Use our custom question urgency calculation
        return self.calculate_question_urgency(signal.title, signal.content)
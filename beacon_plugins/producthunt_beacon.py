#!/usr/bin/env python3
"""
🚨 PRODUCT HUNT BEACON PLUGIN 🚨
Monitors Product Hunt for new launches needing technical help

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

logger = logging.getLogger('ProductHuntBeacon')

class ProductHuntBeacon(BaseBeacon):
    """Product Hunt monitoring beacon plugin"""
    
    platform_name = "producthunt"
    platform_color = "#DA552F"
    requires_auth = False
    scan_interval = 1800  # 30 minutes (slower moving platform)
    
    def initialize(self):
        """Initialize Product Hunt monitoring"""
        # RSS feeds for different categories
        self.rss_feeds = self.platform_config.get('rss_feeds', [
            'https://www.producthunt.com/feed',
            'https://www.producthunt.com/feed/tech',
            'https://www.producthunt.com/feed/developer-tools',
            'https://www.producthunt.com/feed/web-app'
        ])
        
        logger.info(f"✅ Product Hunt feeds configured: {len(self.rss_feeds)} feeds")
    
    def scan_for_signals(self) -> List[SignalData]:
        """Scan Product Hunt for new launches needing help"""
        signals = []
        
        try:
            for feed_url in self.rss_feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    
                    for entry in feed.entries[:10]:  # Recent 10 per feed
                        # Check if entry is recent (last 6 hours)
                        if hasattr(entry, 'published_parsed'):
                            entry_time = time.mktime(entry.published_parsed)
                            if time.time() - entry_time > 21600:  # 6 hours
                                continue
                        
                        title = entry.title
                        description = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                        product_url = entry.link
                        
                        # Check if it's a consulting opportunity
                        if self.is_opportunity_signal(title, description):
                            signal = SignalData(
                                platform="producthunt",
                                platform_id=f"ph_{hash(product_url)}",
                                title=title,
                                content=self.clean_content(description),
                                author=getattr(entry, 'author', 'Product Hunt'),
                                url=product_url,
                                created_utc=entry_time if hasattr(entry, 'published_parsed') else time.time(),
                                estimated_value=self.estimate_ph_value(title, description),
                                tech_stack=self.extract_tech_stack(title + " " + description),
                                keywords_matched=self.get_matched_keywords(title + " " + description)
                            )
                            
                            signals.append(signal)
                            
                except Exception as e:
                    logger.error(f"Error parsing PH feed {feed_url}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Product Hunt scan error: {e}")
        
        return signals
    
    def is_opportunity_signal(self, title: str, description: str) -> bool:
        """Check if Product Hunt launch indicates consulting opportunity"""
        text = (title + " " + description).lower()
        
        # New launches often need help with:
        opportunity_indicators = [
            # Technical scaling needs
            'beta', 'mvp', 'just launched', 'new', 'first version',
            'prototype', 'early stage', 'startup',
            
            # Technical problems they might face
            'performance', 'scaling', 'optimization', 'bug fixes',
            'mobile app', 'web app', 'api', 'integration',
            
            # Business stage indicators
            'small team', 'solo founder', 'bootstrapped',
            'looking for', 'need help', 'seeking'
        ]
        
        # Tech stack indicators (they have tech, might need consulting)
        tech_indicators = [
            'react', 'javascript', 'python', 'node.js',
            'mobile app', 'web app', 'saas', 'platform',
            'ai', 'machine learning', 'api', 'database'
        ]
        
        # Specific consulting opportunity phrases
        consulting_signals = [
            'need developer', 'looking for help', 'technical advisor',
            'scaling issues', 'performance problems', 'optimization needed',
            'mobile version', 'api integration', 'database optimization'
        ]
        
        opp_count = sum(1 for indicator in opportunity_indicators if indicator in text)
        tech_count = sum(1 for indicator in tech_indicators if indicator in text)
        consulting_count = sum(1 for signal in consulting_signals if signal in text)
        
        # Launched products with tech stack = potential consulting opportunity
        has_launch_signal = any(word in text for word in ['launched', 'beta', 'mvp', 'new'])
        has_tech_stack = tech_count >= 1
        
        return (opp_count >= 2 and tech_count >= 1) or consulting_count >= 1 or (has_launch_signal and has_tech_stack)
    
    def estimate_ph_value(self, title: str, description: str) -> float:
        """Estimate consulting value from Product Hunt launch"""
        text = (title + " " + description).lower()
        base_value = 400  # Base value for PH launches
        
        # Stage-based multipliers
        stage_multipliers = {
            'beta': 1.2,
            'mvp': 1.3,
            'just launched': 1.5,
            'early stage': 1.2,
            'startup': 1.8,
            'saas': 2.0,
            'platform': 2.2
        }
        
        for stage, multiplier in stage_multipliers.items():
            if stage in text:
                base_value *= multiplier
                break
        
        # Technology complexity
        complex_tech = ['ai', 'machine learning', 'blockchain', 'api', 'platform']
        if any(tech in text for tech in complex_tech):
            base_value *= 1.8
        
        # Team size indicators (smaller teams = higher consulting need)
        small_team_indicators = ['solo', 'small team', 'bootstrapped', 'indie']
        if any(indicator in text for indicator in small_team_indicators):
            base_value *= 1.5
        
        # Scaling indicators
        scaling_needs = ['scaling', 'performance', 'optimization', 'growing']
        if any(need in text for need in scaling_needs):
            base_value *= 1.6
        
        return min(1800, base_value)  # Cap at $1800
    
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
        """Extract technology stack from Product Hunt post"""
        text_lower = text.lower()
        techs = []
        
        tech_keywords = {
            'javascript': ['javascript', 'js', 'react', 'vue', 'angular', 'node.js'],
            'python': ['python', 'django', 'flask', 'fastapi'],
            'mobile': ['ios', 'android', 'mobile app', 'react native', 'flutter'],
            'web': ['web app', 'webapp', 'saas', 'platform', 'website'],
            'ai': ['ai', 'artificial intelligence', 'machine learning', 'ml'],
            'database': ['database', 'postgresql', 'mysql', 'mongodb'],
            'cloud': ['aws', 'cloud', 'serverless', 'api'],
            'blockchain': ['blockchain', 'crypto', 'web3', 'defi'],
            'ecommerce': ['ecommerce', 'e-commerce', 'shopify', 'online store']
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
            'beta', 'mvp', 'launched', 'startup', 'saas',
            'scaling', 'performance', 'optimization', 'mobile',
            'api', 'integration', 'help', 'advisor'
        ]
        
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return ', '.join(matched)
    
    def calculate_urgency_score(self, signal: SignalData) -> int:
        """Product Hunt specific urgency scoring"""
        base_score = super().calculate_urgency_score(signal)
        
        text = (signal.title + " " + signal.content).lower()
        
        # New launches get priority (strike while iron is hot)
        launch_indicators = ['just launched', 'beta', 'mvp', 'new']
        if any(indicator in text for indicator in launch_indicators):
            base_score += 20
        
        # Scaling problems = immediate opportunity
        scaling_indicators = ['scaling', 'performance', 'growing', 'optimization']
        if any(indicator in text for indicator in scaling_indicators):
            base_score += 25
        
        # Startup context = higher budget potential
        if any(word in text for word in ['startup', 'saas', 'platform']):
            base_score += 15
        
        # Small team = more likely to need help
        if any(word in text for word in ['solo', 'small team', 'bootstrapped']):
            base_score += 15
        
        # Technical complexity
        if any(word in text for word in ['ai', 'api', 'platform', 'integration']):
            base_score += 10
        
        return min(100, base_score)
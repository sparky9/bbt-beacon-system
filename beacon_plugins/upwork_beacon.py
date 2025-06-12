#!/usr/bin/env python3
"""
🚨 UPWORK RSS BEACON PLUGIN 🚨
Monitors Upwork RSS feeds for developer opportunities

Plugin for BBT Beacon Engine v3.0
"""

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

logger = logging.getLogger('UpworkBeacon')

class UpworkBeacon(BaseBeacon):
    """Upwork RSS monitoring beacon plugin"""
    
    platform_name = "upwork"
    platform_color = "#14A800"
    requires_auth = False  # RSS feeds are public
    scan_interval = 600  # 10 minutes
    
    def initialize(self):
        """Initialize Upwork RSS feeds"""
        # Default RSS feeds if not configured
        self.rss_feeds = self.platform_config.get('rss_feeds', [
            'https://www.upwork.com/ab/feed/jobs/rss?q=web+developer+needed&sort=recency',
            'https://www.upwork.com/ab/feed/jobs/rss?q=fix+website&sort=recency',
            'https://www.upwork.com/ab/feed/jobs/rss?q=urgent+developer&sort=recency',
            'https://www.upwork.com/ab/feed/jobs/rss?q=help+bug&sort=recency',
            'https://www.upwork.com/ab/feed/jobs/rss?q=react+developer&sort=recency',
            'https://www.upwork.com/ab/feed/jobs/rss?q=javascript&sort=recency',
            'https://www.upwork.com/ab/feed/jobs/rss?q=node+js&sort=recency',
            'https://www.upwork.com/ab/feed/jobs/rss?q=programmer+needed&sort=recency'
        ])
        
        logger.info(f"✅ Upwork RSS feeds configured: {len(self.rss_feeds)} feeds")
    
    def scan_for_signals(self) -> List[SignalData]:
        """Scan Upwork RSS feeds for opportunities"""
        signals = []
        
        try:
            for feed_url in self.rss_feeds:
                try:
                    # Parse RSS feed
                    feed = feedparser.parse(feed_url)
                    
                    for entry in feed.entries[:10]:  # Limit to recent 10 posts per feed
                        # Check if entry is recent (last 2 hours)
                        if hasattr(entry, 'published_parsed'):
                            entry_time = time.mktime(entry.published_parsed)
                            if time.time() - entry_time > 7200:  # 2 hours
                                continue
                        
                        # Extract job details
                        job_title = entry.title
                        job_description = getattr(entry, 'description', '') or getattr(entry, 'summary', '')
                        job_link = entry.link
                        
                        # Extract budget and urgency info
                        budget_info = self.extract_budget(job_description)
                        estimated_value = self.estimate_project_value(job_description, budget_info)
                        
                        # Create signal
                        signal = SignalData(
                            platform="upwork",
                            platform_id=f"upwork_{entry.id}" if hasattr(entry, 'id') else f"upwork_{hash(job_link)}",
                            title=job_title,
                            content=self.clean_description(job_description),
                            author="Upwork Client",
                            url=job_link,
                            created_utc=entry_time if hasattr(entry, 'published_parsed') else time.time(),
                            budget_range=budget_info,
                            estimated_value=estimated_value,
                            tech_stack=self.extract_tech_stack(job_title + " " + job_description),
                            keywords_matched=self.get_matched_keywords(job_title + " " + job_description)
                        )
                        
                        signals.append(signal)
                        
                except Exception as e:
                    logger.error(f"Error parsing feed {feed_url}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Upwork scan error: {e}")
        
        return signals
    
    def clean_description(self, description: str) -> str:
        """Clean and truncate job description"""
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', ' ', description)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Truncate to reasonable length
        return clean[:500] + "..." if len(clean) > 500 else clean
    
    def extract_budget(self, description: str) -> str:
        """Extract budget information from job description"""
        budget_patterns = [
            r'\$(\d+(?:,\d+)?(?:\.\d{2})?)\s*-\s*\$(\d+(?:,\d+)?(?:\.\d{2})?)',  # $100-$500
            r'\$(\d+(?:,\d+)?(?:\.\d{2})?)\s*(?:per hour|/hr|/hour)',  # $50/hr
            r'budget.*?\$(\d+(?:,\d+)?(?:\.\d{2})?)',  # budget: $1000
            r'(\d+(?:,\d+)?)\s*(?:to|-)?\s*(\d+(?:,\d+)?)\s*(?:dollars|\$|USD)',  # 100-500 dollars
        ]
        
        text = description.lower()
        
        for pattern in budget_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        # Look for budget keywords without specific amounts
        budget_keywords = ['budget', 'pay', 'rate', 'compensation', 'salary']
        for keyword in budget_keywords:
            if keyword in text:
                return f"Has {keyword} mentioned"
        
        return "Budget not specified"
    
    def estimate_project_value(self, description: str, budget_info: str) -> float:
        """Estimate project value from description and budget"""
        # Extract numeric values from budget
        budget_numbers = re.findall(r'\$?(\d+(?:,\d+)?(?:\.\d{2})?)', budget_info.replace(',', ''))
        
        if budget_numbers:
            try:
                amounts = [float(num) for num in budget_numbers]
                # Use the highest amount if range, otherwise use the single amount
                estimated = max(amounts) if len(amounts) > 1 else amounts[0]
                
                # If it looks like hourly rate, estimate based on project size
                if 'hour' in budget_info.lower() or '/hr' in budget_info.lower():
                    # Estimate 20-40 hours for typical projects
                    project_size_multiplier = self.estimate_project_hours(description)
                    estimated *= project_size_multiplier
                
                return estimated
            except ValueError:
                pass
        
        # Fallback estimation based on project complexity
        return self.estimate_by_complexity(description)
    
    def estimate_project_hours(self, description: str) -> float:
        """Estimate project hours based on description"""
        text = description.lower()
        
        # Small projects (10-20 hours)
        small_indicators = ['quick', 'simple', 'small', 'minor', 'basic', 'easy']
        if any(word in text for word in small_indicators):
            return 15
        
        # Large projects (40-100 hours)
        large_indicators = ['complex', 'large', 'full', 'complete', 'entire', 'comprehensive']
        if any(word in text for word in large_indicators):
            return 70
        
        # Medium projects (20-40 hours) - default
        return 30
    
    def estimate_by_complexity(self, description: str) -> float:
        """Estimate value based on project complexity"""
        text = description.lower()
        
        # High-value indicators
        if any(word in text for word in ['enterprise', 'e-commerce', 'database', 'api', 'full stack']):
            return 2000
        
        # Medium-value indicators  
        if any(word in text for word in ['website', 'web app', 'integration', 'custom']):
            return 800
        
        # Low-value indicators
        if any(word in text for word in ['fix', 'bug', 'quick', 'simple', 'small']):
            return 200
        
        # Default estimate
        return 500
    
    def extract_tech_stack(self, text: str) -> str:
        """Extract technology stack from job text"""
        text_lower = text.lower()
        techs = []
        
        tech_keywords = {
            'javascript': ['javascript', 'js', 'node.js', 'nodejs', 'vue', 'angular'],
            'react': ['react', 'reactjs', 'next.js', 'nextjs', 'react native'],
            'python': ['python', 'django', 'flask', 'fastapi', 'python'],
            'php': ['php', 'laravel', 'wordpress', 'drupal', 'codeigniter'],
            'database': ['mysql', 'postgresql', 'mongodb', 'database', 'sql'],
            'mobile': ['android', 'ios', 'mobile app', 'flutter', 'swift'],
            'web': ['html', 'css', 'web development', 'frontend', 'backend'],
            'ecommerce': ['shopify', 'woocommerce', 'magento', 'ecommerce', 'e-commerce']
        }
        
        for tech, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                techs.append(tech)
        
        return ', '.join(techs)
    
    def get_matched_keywords(self, text: str) -> str:
        """Get list of matched opportunity keywords"""
        text_lower = text.lower()
        matched = []
        
        keywords = [
            'urgent', 'asap', 'immediately', 'quickly', 'fast',
            'help', 'fix', 'bug', 'broken', 'issue',
            'developer', 'programmer', 'freelancer',
            'project', 'website', 'app', 'application'
        ]
        
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return ', '.join(matched)
    
    def calculate_urgency_score(self, signal: SignalData) -> int:
        """Upwork-specific urgency scoring"""
        base_score = super().calculate_urgency_score(signal)
        
        # Upwork-specific adjustments
        text = (signal.title + " " + signal.content).lower()
        
        # High urgency for time-sensitive projects
        time_keywords = ['asap', 'immediately', 'urgent', 'quickly', 'today', 'tomorrow']
        urgency_boost = sum(10 for keyword in time_keywords if keyword in text)
        base_score += urgency_boost
        
        # Budget-based scoring
        if signal.estimated_value > 1000:
            base_score += 20
        elif signal.estimated_value > 500:
            base_score += 10
        
        # Tech stack relevance
        relevant_techs = ['javascript', 'react', 'python', 'web development']
        if any(tech in signal.tech_stack.lower() for tech in relevant_techs):
            base_score += 15
        
        return min(100, base_score)
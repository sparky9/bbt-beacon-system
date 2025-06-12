#!/usr/bin/env python3
"""
🚀 EXAMPLE BEACON PLUGIN TEMPLATE 🚀
Copy this file to create new platform monitoring plugins

Plugin for BBT Beacon Engine v3.0

TO ADD A NEW SERVICE:
1. Copy this file to [platform]_beacon.py
2. Replace "Example" with your platform name
3. Implement scan_for_signals() method
4. Add platform config to beacon_config.json
5. DONE! Auto-discovered and loaded

Example platforms to add:
- LinkedIn (job posts)
- GitHub Issues (help wanted)
- Discord servers (help channels)  
- Stack Overflow (unanswered questions)
- TikTok (dev crisis videos)
- Hacker News (who's hiring)
"""

from typing import List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from beacon_engine import BaseBeacon, SignalData
import logging

logger = logging.getLogger('ExampleBeacon')

class ExampleBeacon(BaseBeacon):
    """Example platform monitoring beacon plugin"""
    
    # REQUIRED: Platform configuration
    platform_name = "example"           # Must match config key
    platform_color = "#FF69B4"          # Hex color for UI
    requires_auth = False                # Does this platform need API keys?
    scan_interval = 300                  # Seconds between scans (5 minutes)
    
    def initialize(self):
        """
        Override this method for platform-specific setup
        - Initialize API clients
        - Validate credentials  
        - Set up any required state
        
        Set self.enabled = False if setup fails
        """
        # Example: Check if required config exists
        api_key = self.credentials.get('api_key')
        if self.requires_auth and not api_key:
            logger.error("❌ Example API key not configured")
            self.enabled = False
            return
        
        # Example: Test API connection
        try:
            # your_api_client.test_connection()
            logger.info("✅ Example platform connection established")
        except Exception as e:
            logger.error(f"❌ Example platform setup failed: {e}")
            self.enabled = False
    
    def scan_for_signals(self) -> List[SignalData]:
        """
        MAIN METHOD: Scan your platform for developer crisis signals
        
        Returns list of SignalData objects
        This method is called every scan_interval seconds
        """
        if not self.enabled:
            return []
        
        signals = []
        
        try:
            # STEP 1: Fetch data from your platform
            # Examples:
            # - API calls to get recent posts/jobs/issues
            # - RSS feed parsing
            # - Web scraping (be respectful!)
            # - Database queries
            
            recent_posts = self.fetch_recent_posts()
            
            # STEP 2: Filter for crisis signals
            for post in recent_posts:
                if self.is_crisis_signal(post):
                    # STEP 3: Convert to StandardSignalData
                    signal = SignalData(
                        platform=self.platform_name,
                        platform_id=f"{self.platform_name}_{post['id']}",
                        title=post['title'],
                        content=post['content'][:500],  # Limit content length
                        author=post['author'],
                        url=post['url'],
                        created_utc=post['timestamp'],
                        
                        # Optional enhanced fields
                        budget_range=self.extract_budget(post['content']),
                        estimated_value=self.estimate_value(post['content']),
                        tech_stack=self.extract_tech_stack(post['content']),
                        keywords_matched=self.get_matched_keywords(post['content'])
                    )
                    
                    signals.append(signal)
        
        except Exception as e:
            logger.error(f"Example scan error: {e}")
        
        return signals
    
    def fetch_recent_posts(self) -> List[dict]:
        """Fetch recent posts from your platform"""
        # Example implementation
        posts = [
            {
                'id': '12345',
                'title': 'Help! Website is broken and client is angry',
                'content': 'My React app crashed and I have a deadline tomorrow. Willing to pay for urgent help!',
                'author': 'stressed_dev',
                'url': 'https://example.com/post/12345',
                'timestamp': 1640995200.0
            }
        ]
        return posts
    
    def is_crisis_signal(self, post: dict) -> bool:
        """Determine if a post is a developer crisis signal"""
        text = (post['title'] + " " + post['content']).lower()
        
        # Crisis keywords
        crisis_keywords = [
            'help', 'urgent', 'broken', 'bug', 'error', 'crisis',
            'deadline', 'emergency', 'stuck', 'not working'
        ]
        
        # Opportunity keywords
        opportunity_keywords = [
            'hire', 'freelancer', 'developer', 'programmer', 
            'project', 'budget', 'pay', 'paid'
        ]
        
        # Must have at least one from each category OR high urgency
        has_crisis = any(word in text for word in crisis_keywords)
        has_opportunity = any(word in text for word in opportunity_keywords)
        
        return has_crisis and has_opportunity
    
    def extract_budget(self, text: str) -> str:
        """Extract budget information from text"""
        # Example: Look for dollar amounts, hourly rates, etc.
        import re
        
        budget_pattern = r'\$(\d+(?:,\d+)?(?:\.\d{2})?)'
        matches = re.findall(budget_pattern, text)
        
        if matches:
            return f"${', $'.join(matches)}"
        
        return "Budget not specified"
    
    def estimate_value(self, text: str) -> float:
        """Estimate project value from description"""
        # Example: Basic estimation logic
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['enterprise', 'large', 'complex']):
            return 2000.0
        elif any(word in text_lower for word in ['small', 'quick', 'simple']):
            return 200.0
        else:
            return 500.0  # Default estimate
    
    def extract_tech_stack(self, text: str) -> str:
        """Extract mentioned technologies"""
        text_lower = text.lower()
        techs = []
        
        tech_map = {
            'javascript': ['javascript', 'js', 'node'],
            'react': ['react', 'reactjs'],
            'python': ['python', 'django', 'flask'],
            'php': ['php', 'laravel', 'wordpress']
        }
        
        for tech, keywords in tech_map.items():
            if any(keyword in text_lower for keyword in keywords):
                techs.append(tech)
        
        return ', '.join(techs)
    
    def get_matched_keywords(self, text: str) -> str:
        """Get list of matched crisis keywords"""
        text_lower = text.lower()
        matched = []
        
        keywords = ['urgent', 'help', 'broken', 'hire', 'developer', 'budget']
        
        for keyword in keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return ', '.join(matched)
    
    def calculate_urgency_score(self, signal: SignalData) -> int:
        """
        Override to add platform-specific urgency scoring
        Base implementation already handles common patterns
        """
        base_score = super().calculate_urgency_score(signal)
        
        # Platform-specific adjustments
        text = (signal.title + " " + signal.content).lower()
        
        # Example: Boost for platform-specific patterns
        if 'example_urgent_pattern' in text:
            base_score += 25
        
        return min(100, base_score)

# CONFIGURATION EXAMPLE:
# Add this to beacon_config.json:
"""
{
  "credentials": {
    "example": {
      "api_key": "your_api_key_here",
      "username": "your_username"
    }
  },
  "beacons": {
    "example": {
      "enabled": true,
      "scan_interval": 300,
      "custom_setting": "value"
    }
  }
}
"""
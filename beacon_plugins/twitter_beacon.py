#!/usr/bin/env python3
"""
🚨 TWITTER/X BEACON PLUGIN 🚨
Monitors Twitter/X for developer crisis signals

Plugin for BBT Beacon Engine v3.0
FREE TIER: 100 API calls/month (3-4 calls/day max)
"""

import requests
import time
import json
from datetime import datetime, timedelta
from typing import List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from beacon_engine import BaseBeacon, SignalData
import logging

logger = logging.getLogger('TwitterBeacon')

class TwitterBeacon(BaseBeacon):
    """Twitter/X monitoring beacon plugin with FREE tier optimization"""
    
    platform_name = "twitter"
    platform_color = "#1DA1F2"
    requires_auth = True
    scan_interval = 21600  # 6 hours (4 calls per day max for free tier)
    
    def initialize(self):
        """Initialize Twitter API connection"""
        self.bearer_token = self.credentials.get('bearer_token')
        self.api_base = 'https://api.twitter.com/2'
        
        # API usage tracking for FREE tier (100 calls/month)
        self.monthly_limit = 100
        self.api_calls_made = 0
        self.last_reset_date = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        
        if not self.bearer_token:
            logger.warning("⚠️ Twitter bearer token not configured")
            self.enabled = False
            return
        
        # Test API connection
        try:
            self.test_connection()
            logger.info("✅ Twitter API connection established")
        except Exception as e:
            logger.error(f"❌ Twitter API setup failed: {e}")
            self.enabled = False
    
    def test_connection(self):
        """Test Twitter API connection"""
        headers = {'Authorization': f'Bearer {self.bearer_token}'}
        response = requests.get(f'{self.api_base}/tweets/search/recent?query=test&max_results=10', headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"API test failed: {response.status_code} - {response.text}")
    
    def scan_for_signals(self) -> List[SignalData]:
        """Scan Twitter for developer crisis signals (FREE tier optimized)"""
        if not self.enabled:
            return []
        
        # Check API limits
        if not self.can_make_api_call():
            logger.warning("⚠️ Twitter API limit reached for this month")
            return []
        
        signals = []
        
        try:
            # PREMIUM SEARCH QUERIES - Optimized for high ROI (FREE tier: max 100/month)
            search_queries = [
                '"need developer" urgent -RT',  # High-value client requests
                '"hire developer" budget -RT',   # Paid opportunities
                '"help with" javascript react urgent -RT',  # Tech-specific crisis
                '"website broken" help -RT',     # Emergency fixes
            ]
            
            headers = {'Authorization': f'Bearer {self.bearer_token}'}
            
            for query in search_queries:
                if not self.can_make_api_call():
                    break
                
                try:
                    # Search recent tweets (last 7 days for free tier)
                    params = {
                        'query': query,
                        'max_results': 25,  # Increased from 10 for better signal capture
                        'tweet.fields': 'created_at,author_id,public_metrics,context_annotations',
                        'user.fields': 'username,verified,public_metrics',
                        'expansions': 'author_id'
                    }
                    
                    response = requests.get(f'{self.api_base}/tweets/search/recent', 
                                          headers=headers, params=params)
                    
                    self.api_calls_made += 1
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if 'data' in data:
                            # Process tweets
                            users_lookup = {}
                            if 'includes' in data and 'users' in data['includes']:
                                users_lookup = {user['id']: user for user in data['includes']['users']}
                            
                            for tweet in data['data']:
                                # Filter for high-quality signals
                                if self.is_high_quality_signal(tweet, users_lookup):
                                    signal = self.create_signal_from_tweet(tweet, users_lookup, query)
                                    if signal:
                                        signals.append(signal)
                    
                    else:
                        logger.error(f"Twitter API error: {response.status_code} - {response.text}")
                        if response.status_code == 429:  # Rate limited
                            logger.warning("Rate limited - stopping Twitter scan")
                            break
                
                except Exception as e:
                    logger.error(f"Error processing Twitter query '{query}': {e}")
                    continue
                
                # Small delay between requests
                time.sleep(1)
        
        except Exception as e:
            logger.error(f"Twitter scan error: {e}")
        
        logger.info(f"🐦 Twitter: {len(signals)} signals found, {self.api_calls_made} API calls used this month")
        return signals
    
    def can_make_api_call(self) -> bool:
        """Check if we can make another API call this month"""
        current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        
        # Reset counter if new month
        if current_month > self.last_reset_date:
            self.api_calls_made = 0
            self.last_reset_date = current_month
        
        return self.api_calls_made < self.monthly_limit
    
    def is_high_quality_signal(self, tweet: dict, users_lookup: dict) -> bool:
        """Filter for high-quality signals worth pursuing"""
        tweet_text = tweet.get('text', '').lower()
        
        # Skip retweets and replies
        if tweet_text.startswith('rt @') or tweet_text.startswith('@'):
            return False
        
        # Must be recent (last 24 hours)
        created_at = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
        if datetime.now().replace(tzinfo=created_at.tzinfo) - created_at > timedelta(hours=24):
            return False
        
        # Look for business/client indicators
        business_indicators = [
            'company', 'business', 'startup', 'project', 'budget',
            'hire', 'looking for', 'need help', 'urgent project'
        ]
        
        # Avoid low-quality signals
        avoid_keywords = [
            'student', 'homework', 'learning', 'tutorial', 'course',
            'free', 'unpaid', 'volunteer', 'practice'
        ]
        
        has_business_indicator = any(indicator in tweet_text for indicator in business_indicators)
        has_avoid_keyword = any(keyword in tweet_text for keyword in avoid_keywords)
        
        # Check user quality if available
        user_quality_score = 0
        if tweet.get('author_id') in users_lookup:
            user = users_lookup[tweet['author_id']]
            
            # Verified users get priority
            if user.get('verified', False):
                user_quality_score += 20
            
            # Users with decent follower count
            if 'public_metrics' in user:
                followers = user['public_metrics'].get('followers_count', 0)
                if followers > 100:
                    user_quality_score += 10
                if followers > 1000:
                    user_quality_score += 20
        
        # Engagement metrics
        engagement_score = 0
        if 'public_metrics' in tweet:
            metrics = tweet['public_metrics']
            likes = metrics.get('like_count', 0)
            retweets = metrics.get('retweet_count', 0)
            
            # Higher engagement = more serious request
            if likes > 0 or retweets > 0:
                engagement_score += 10
        
        # Final scoring
        total_score = user_quality_score + engagement_score
        if has_business_indicator:
            total_score += 15
        if has_avoid_keyword:
            total_score -= 20
        
        return total_score >= 10  # Minimum quality threshold
    
    def create_signal_from_tweet(self, tweet: dict, users_lookup: dict, search_query: str) -> SignalData:
        """Create SignalData from tweet"""
        try:
            # Get user info
            author_username = "unknown"
            if tweet.get('author_id') in users_lookup:
                author_username = users_lookup[tweet['author_id']].get('username', 'unknown')
            
            # Create tweet URL
            tweet_url = f"https://twitter.com/{author_username}/status/{tweet['id']}"
            
            # Parse timestamp
            created_at = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
            created_utc = created_at.timestamp()
            
            signal = SignalData(
                platform="twitter",
                platform_id=f"twitter_{tweet['id']}",
                title=tweet['text'][:100] + "..." if len(tweet['text']) > 100 else tweet['text'],
                content=tweet['text'],
                author=f"@{author_username}",
                url=tweet_url,
                created_utc=created_utc,
                tech_stack=self.extract_tech_stack(tweet['text']),
                keywords_matched=search_query
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating signal from tweet: {e}")
            return None
    
    def extract_tech_stack(self, text: str) -> str:
        """Extract technology stack from tweet text"""
        text_lower = text.lower()
        techs = []
        
        tech_keywords = {
            'javascript': ['javascript', 'js', '#javascript', '#js'],
            'react': ['react', 'reactjs', '#react', '#reactjs'],
            'python': ['python', '#python', 'django', 'flask'],
            'web': ['html', 'css', 'web dev', 'frontend', 'backend'],
            'mobile': ['ios', 'android', 'mobile app', 'app dev'],
            'api': ['api', 'rest api', 'graphql'],
            'database': ['database', 'sql', 'mongodb', 'mysql']
        }
        
        for tech, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                techs.append(tech)
        
        return ', '.join(techs)
    
    def calculate_urgency_score(self, signal: SignalData) -> int:
        """Twitter-specific urgency scoring"""
        base_score = super().calculate_urgency_score(signal)
        
        text = signal.content.lower()
        
        # Twitter-specific boosts
        if any(word in text for word in ['urgent', 'asap', 'immediately', 'help']):
            base_score += 20
        
        if any(word in text for word in ['hire', 'budget', 'pay', 'project']):
            base_score += 15
        
        # Hashtag analysis
        if '#urgent' in text or '#help' in text:
            base_score += 10
        
        # Verified user bonus (if we can detect it)
        if signal.author.startswith('@') and len(signal.author) > 1:
            base_score += 5  # Slight bonus for having a username
        
        return min(100, base_score)
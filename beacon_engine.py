#!/usr/bin/env python3
"""
🚀 BBT BEACON ENGINE v3.0 - PLUGIN ARCHITECTURE 🚀
The Ultimate Extensible Developer Crisis Detection System

ADD NEW SERVICES IN 30 SECONDS:
1. Drop in a new BeaconPlugin file
2. Add config entry
3. DONE! Auto-discovered and loaded

Built by Mike & AI Family using BBT methodology
"""

import abc
import json
import sqlite3
import threading
import time
import logging
import importlib
import inspect
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Type
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
)
logger = logging.getLogger('BeaconEngine')

class SignalData:
    """Standardized signal data structure across all platforms"""
    def __init__(self, platform: str, platform_id: str, title: str, content: str, 
                 author: str, url: str, created_utc: float, urgency_score: int = 0,
                 budget_range: str = "", estimated_value: float = 0, 
                 tech_stack: str = "", keywords_matched: str = ""):
        
        self.platform = platform
        self.platform_id = platform_id
        self.title = title
        self.content = content
        self.author = author
        self.url = url
        self.created_utc = created_utc
        self.urgency_score = urgency_score
        self.budget_range = budget_range
        self.estimated_value = estimated_value
        self.tech_stack = tech_stack
        self.keywords_matched = keywords_matched
        self.detected_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'platform': self.platform,
            'platform_id': self.platform_id,
            'title': self.title,
            'content': self.content,
            'author': self.author,
            'url': self.url,
            'created_utc': self.created_utc,
            'urgency_score': self.urgency_score,
            'budget_range': self.budget_range,
            'estimated_value': self.estimated_value,
            'tech_stack': self.tech_stack,
            'keywords_matched': self.keywords_matched,
            'detected_at': self.detected_at.isoformat()
        }

class BaseBeacon(abc.ABC):
    """Abstract base class for all beacon plugins"""
    
    # Plugin metadata (override in subclasses)
    platform_name: str = ""
    platform_color: str = "#666666"
    requires_auth: bool = False
    scan_interval: int = 300  # seconds
    
    def __init__(self, config: Dict[str, Any], database: 'BeaconDatabase'):
        self.config = config
        self.database = database
        self.enabled = config.get('enabled', True)
        self.running = False
        self.thread = None
        self.last_scan = None
        
        # Platform-specific config
        self.platform_config = config.get('beacons', {}).get(self.platform_name, {})
        self.credentials = config.get('credentials', {}).get(self.platform_name, {})
        
        # Initialize platform-specific setup
        self.initialize()
    
    def initialize(self):
        """Override for platform-specific initialization"""
        pass
    
    @abc.abstractmethod
    def scan_for_signals(self) -> List[SignalData]:
        """
        Scan the platform for developer crisis signals
        Returns list of SignalData objects
        """
        pass
    
    def calculate_urgency_score(self, signal: SignalData) -> int:
        """
        Calculate urgency score (0-100) based on signal content
        Override for platform-specific scoring
        """
        score = 0
        content_lower = (signal.title + " " + signal.content).lower()
        
        # Urgency keywords
        urgency_words = {
            'urgent': 25, 'asap': 25, 'emergency': 30, 'critical': 25,
            'help': 10, 'stuck': 15, 'broken': 20, 'not working': 15,
            'deadline': 20, 'today': 15, 'immediately': 25, 'bug': 15,
            'error': 10, 'crash': 20, 'down': 25, 'failing': 20
        }
        
        for word, points in urgency_words.items():
            if word in content_lower:
                score += points
        
        # Budget indicators
        budget_words = ['$', 'budget', 'pay', 'paid', 'money', 'rate', 'hour']
        if any(word in content_lower for word in budget_words):
            score += 10
        
        # Tech stack relevance
        tech_words = ['javascript', 'python', 'react', 'node', 'api', 'database', 'web']
        matches = sum(1 for word in tech_words if word in content_lower)
        score += matches * 5
        
        return min(100, max(0, score))
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if self.running:
            logger.warning(f"{self.platform_name} beacon already running")
            return
        
        if not self.enabled:
            logger.info(f"{self.platform_name} beacon disabled in config")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info(f"🚀 {self.platform_name} beacon started")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        logger.info(f"🛑 {self.platform_name} beacon stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                start_time = time.time()
                signals = self.scan_for_signals()
                
                for signal in signals:
                    # Calculate urgency if not set
                    if signal.urgency_score == 0:
                        signal.urgency_score = self.calculate_urgency_score(signal)
                    
                    # Store in database
                    self.database.store_signal(signal)
                
                self.last_scan = datetime.now()
                scan_duration = time.time() - start_time
                
                if signals:
                    logger.info(f"{self.platform_name}: Found {len(signals)} signals in {scan_duration:.1f}s")
                
                # Sleep until next scan
                time.sleep(self.scan_interval)
                
            except Exception as e:
                logger.error(f"{self.platform_name} beacon error: {e}")
                time.sleep(60)  # Wait before retrying

class BeaconDatabase:
    """Unified database for all beacon signals"""
    
    def __init__(self, db_path: str = "beacon_engine.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the comprehensive beacon database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main signals table (unified schema)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            status TEXT DEFAULT 'detected',
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
        
        # Platform statistics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS platform_stats (
            id INTEGER PRIMARY KEY,
            platform TEXT,
            date TEXT,
            signals_found INTEGER DEFAULT 0,
            responses_sent INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            avg_response_time REAL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Revenue goals
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS revenue_goals (
            id INTEGER PRIMARY KEY,
            date TEXT UNIQUE,
            daily_goal REAL DEFAULT 500,
            achieved REAL DEFAULT 0,
            target_opportunities INTEGER DEFAULT 10
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    
    def store_signal(self, signal: SignalData) -> bool:
        """Store a signal in the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if signal already exists
            cursor.execute('SELECT id FROM signals WHERE platform_id = ?', (signal.platform_id,))
            if cursor.fetchone():
                conn.close()
                return False  # Already exists
            
            # Insert new signal
            signal_dict = signal.to_dict()
            columns = ', '.join(signal_dict.keys())
            placeholders = ', '.join('?' * len(signal_dict))
            
            cursor.execute(f'''
            INSERT INTO signals ({columns})
            VALUES ({placeholders})
            ''', list(signal_dict.values()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"📡 New signal: {signal.platform} - {signal.title[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Database error storing signal: {e}")
            return False
    
    def get_recent_signals(self, platform: str = None, limit: int = 20) -> List[Dict]:
        """Get recent signals from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
        SELECT * FROM signals
        WHERE (?1 IS NULL OR platform = ?1)
        ORDER BY detected_at DESC
        LIMIT ?2
        '''
        
        cursor.execute(query, (platform, limit))
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return results

class ServiceRegistry:
    """Auto-discovers and manages beacon plugins"""
    
    def __init__(self, plugins_dir: str = "beacon_plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins: Dict[str, Type[BaseBeacon]] = {}
        self.instances: Dict[str, BaseBeacon] = {}
        
        # Create plugins directory if it doesn't exist
        self.plugins_dir.mkdir(exist_ok=True)
        
        # Discover plugins
        self.discover_plugins()
    
    def discover_plugins(self):
        """Auto-discover all beacon plugins"""
        # Look for plugins in the plugins directory
        if self.plugins_dir.exists():
            for plugin_file in self.plugins_dir.glob("*_beacon.py"):
                self.load_plugin(plugin_file)
        
        # Also check current directory for existing beacon files
        current_dir = Path(__file__).parent
        for plugin_file in current_dir.glob("*beacon*.py"):
            if plugin_file.name != "beacon_engine.py":
                self.load_plugin(plugin_file)
        
        logger.info(f"🔍 Discovered {len(self.plugins)} beacon plugins")
    
    def load_plugin(self, plugin_file: Path):
        """Load a single plugin file"""
        try:
            # Import the module
            import importlib.util
            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find BaseBeacon subclasses
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseBeacon) and 
                    obj != BaseBeacon and
                    hasattr(obj, 'platform_name') and
                    obj.platform_name):
                    
                    self.plugins[obj.platform_name] = obj
                    logger.info(f"📦 Loaded plugin: {obj.platform_name}")
                    
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_file}: {e}")
    
    def create_instance(self, platform_name: str, config: Dict, database: BeaconDatabase) -> Optional[BaseBeacon]:
        """Create an instance of a beacon plugin"""
        if platform_name not in self.plugins:
            logger.error(f"Plugin {platform_name} not found")
            return None
        
        try:
            instance = self.plugins[platform_name](config, database)
            self.instances[platform_name] = instance
            return instance
        except Exception as e:
            logger.error(f"Failed to create {platform_name} instance: {e}")
            return None

class BeaconEngine:
    """Main engine that orchestrates all beacon plugins"""
    
    def __init__(self, config_file: str = "beacon_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        
        # Initialize core components
        self.database = BeaconDatabase()
        self.registry = ServiceRegistry()
        self.active_beacons: Dict[str, BaseBeacon] = {}
        
        # Load enabled beacons
        self.load_beacons()
    
    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {self.config_file} not found, using defaults")
            return self.create_default_config()
    
    def create_default_config(self) -> Dict:
        """Create default configuration"""
        config = {
            "credentials": {},
            "beacons": {},
            "alerts": {
                "email_enabled": False,
                "min_urgency_for_email": 15
            },
            "dashboard": {
                "enabled": True,
                "port": 5000
            }
        }
        
        # Save default config
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return config
    
    def load_beacons(self):
        """Load and initialize all enabled beacon plugins"""
        beacon_configs = self.config.get('beacons', {})
        
        for platform_name in self.registry.plugins.keys():
            platform_config = beacon_configs.get(platform_name, {})
            
            if platform_config.get('enabled', False):
                beacon = self.registry.create_instance(platform_name, self.config, self.database)
                if beacon:
                    self.active_beacons[platform_name] = beacon
                    logger.info(f"✅ {platform_name} beacon loaded")
    
    def start_all_beacons(self):
        """Start monitoring on all enabled beacons"""
        logger.info(f"🚀 Starting {len(self.active_beacons)} beacon services...")
        
        for platform_name, beacon in self.active_beacons.items():
            try:
                beacon.start_monitoring()
            except Exception as e:
                logger.error(f"Failed to start {platform_name}: {e}")
        
        logger.info("🎯 Beacon Engine fully operational!")
    
    def stop_all_beacons(self):
        """Stop all running beacons"""
        logger.info("🛑 Stopping all beacons...")
        
        for beacon in self.active_beacons.values():
            beacon.stop_monitoring()
        
        logger.info("✅ All beacons stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all beacons"""
        status = {
            'total_plugins': len(self.registry.plugins),
            'active_beacons': len(self.active_beacons),
            'beacons': {}
        }
        
        for platform_name, beacon in self.active_beacons.items():
            status['beacons'][platform_name] = {
                'running': beacon.running,
                'last_scan': beacon.last_scan.isoformat() if beacon.last_scan else None,
                'enabled': beacon.enabled
            }
        
        return status

def main():
    """Main entry point - start the beacon engine"""
    logger.info("🚨 BBT BEACON ENGINE v3.0 STARTING 🚨")
    
    engine = BeaconEngine()
    
    try:
        engine.start_all_beacons()
        
        # Keep running
        while True:
            time.sleep(30)
            
            # Print status every 30 seconds
            status = engine.get_status()
            running_count = sum(1 for beacon_status in status['beacons'].values() 
                              if beacon_status['running'])
            
            logger.info(f"📊 Status: {running_count}/{status['active_beacons']} beacons running")
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested")
        engine.stop_all_beacons()
    except Exception as e:
        logger.error(f"Engine error: {e}")
        engine.stop_all_beacons()

if __name__ == "__main__":
    main()
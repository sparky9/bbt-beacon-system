#!/usr/bin/env python3
"""
🚨 BBT BEACON SYSTEM v3.0 - PRODUCTION 🚨
Complete monitoring + dashboard deployment package

Features:
- Plugin-based beacon architecture
- Reddit + Upwork + Twitter monitoring  
- Revenue tracking mega dashboard
- Auto-discovery of new plugins
"""

import os
import sys
import threading
import time
from pathlib import Path

# Add plugins directory to path
sys.path.append(str(Path(__file__).parent / "beacon_plugins"))

# Import main components
from beacon_engine import BeaconEngine, BeaconDatabase
from mega_dashboard_app import app as dashboard_app

def main():
    """Start both beacon engine and dashboard"""
    print("🚨 BBT BEACON SYSTEM v3.0 STARTING 🚨")
    
    # Start beacon engine in background thread
    def start_beacon_engine():
        try:
            engine = BeaconEngine()
            engine.start_all_beacons()
            
            # Keep engine running
            while True:
                time.sleep(60)
                status = engine.get_status()
                running_count = sum(1 for beacon_status in status['beacons'].values() 
                                  if beacon_status['running'])
                print(f"📊 Beacons: {running_count}/{status['active_beacons']} running")
                
        except Exception as e:
            print(f"Beacon engine error: {e}")
    
    # Start beacon engine
    beacon_thread = threading.Thread(target=start_beacon_engine, daemon=True)
    beacon_thread.start()
    
    # Give beacons time to initialize
    time.sleep(5)
    
    # Start dashboard (main thread)
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting dashboard on port {port}")
    dashboard_app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Start the Pinnacle Odds Scheduler
This will run the scraper every 5 minutes automatically
"""

import subprocess
import sys
import os
from dotenv import load_dotenv

def main():
    print("🎯 Starting Pinnacle Odds Scheduler...")
    print("📅 The scraper will run every 5 minutes")
    print("🛑 Press Ctrl+C to stop")
    print("=" * 50)
    
    # Load environment variables from .env file
    load_dotenv()
    
    try:
        # Run the scheduler
        subprocess.run([sys.executable, "scheduler.py"], cwd=os.path.dirname(os.path.abspath(__file__)))
    except KeyboardInterrupt:
        print("\n🛑 Scheduler stopped by user")
    except Exception as e:
        print(f"❌ Error running scheduler: {e}")

if __name__ == "__main__":
    main()

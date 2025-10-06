#!/usr/bin/env python3
"""
Startup script for Pinnacle Odds Tracker
Handles database setup, backend server, and scraper initialization
"""

import asyncio
import subprocess
import sys
import os
import time
import signal
from pathlib import Path
from dotenv import load_dotenv

def check_requirements():
    """Check if all requirements are installed"""
    try:
        import fastapi
        import uvicorn
        import asyncpg
        import aiohttp
        import pandas
        print("✅ All requirements are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing requirement: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def check_environment():
    """Check if environment variables are set"""
    load_dotenv()
    
    required_vars = ['ODDS_API_KEY', 'DATABASE_URL']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please copy env.example to .env and fill in the required values")
        return False
    
    print("✅ Environment variables are configured")
    return True

def check_database():
    """Check if database is accessible"""
    try:
        import asyncpg
        import asyncio
        
        async def test_connection():
            database_url = os.getenv('DATABASE_URL')
            conn = await asyncpg.connect(database_url)
            await conn.execute('SELECT 1')
            await conn.close()
            return True
        
        if asyncio.run(test_connection()):
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Please ensure PostgreSQL is running and DATABASE_URL is correct")
        return False

def run_migrations():
    """Run database migrations"""
    try:
        print("🔄 Running database migrations...")
        result = subprocess.run([sys.executable, 'database/migrate.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Database migrations completed")
            return True
        else:
            print(f"❌ Migration failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False

def start_backend():
    """Start the FastAPI backend server"""
    print("🚀 Starting backend server...")
    return subprocess.Popen([
        sys.executable, '-m', 'uvicorn', 
        'backend.main:app', 
        '--host', '0.0.0.0', 
        '--port', '8000',
        '--reload'
    ])

def start_scraper():
    """Start the odds scraper"""
    print("🔄 Starting odds scraper...")
    return subprocess.Popen([sys.executable, 'main.py'])

def main():
    """Main startup function"""
    print("🎯 Pinnacle Odds Tracker - Starting up...")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Check database
    if not check_database():
        sys.exit(1)
    
    # Run migrations
    if not run_migrations():
        sys.exit(1)
    
    print("\n🚀 Starting services...")
    print("=" * 50)
    
    # Start backend server
    backend_process = start_backend()
    time.sleep(3)  # Give backend time to start
    
    # Start scraper
    scraper_process = start_scraper()
    
    print("\n✅ All services started successfully!")
    print("=" * 50)
    print("🌐 Web Interface: http://localhost:8000")
    print("📊 API Documentation: http://localhost:8000/docs")
    print("🔄 Scraper: Running in background")
    print("\nPress Ctrl+C to stop all services")
    
    def signal_handler(sig, frame):
        print("\n\n🛑 Shutting down services...")
        backend_process.terminate()
        scraper_process.terminate()
        
        # Wait for processes to terminate
        backend_process.wait()
        scraper_process.wait()
        
        print("✅ All services stopped")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if backend_process.poll() is not None:
                print("❌ Backend server stopped unexpectedly")
                break
            
            if scraper_process.poll() is not None:
                print("❌ Scraper stopped unexpectedly")
                break
                
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()

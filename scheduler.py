#!/usr/bin/env python3
"""
Pinnacle Odds Scheduler
Runs the scraper every 5 minutes 24/7 for testing
"""

import asyncio
import schedule
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from main import main as run_scraper

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_scraper_job():
    """Wrapper function to run the scraper"""
    try:
        logger.info("🔄 Starting scheduled odds scraping...")
        asyncio.run(run_scraper())
        logger.info("✅ Scheduled scraping completed successfully")
    except Exception as e:
        logger.error(f"❌ Scheduled scraping failed: {e}")

def run_cleanup_job():
    """Wrapper function to run database cleanup"""
    try:
        logger.info("🧹 Starting database cleanup...")
        asyncio.run(cleanup_database())
        logger.info("✅ Database cleanup completed successfully")
    except Exception as e:
        logger.error(f"❌ Database cleanup failed: {e}")

async def cleanup_database():
    """Clean up old odds data to prevent database bloat"""
    from database.connection import get_db_manager
    
    try:
        # Initialize database connection
        await get_db_manager().initialize()
        
        # Clean up odds older than 7 days (keeping only latest for each event/market/team)
        deleted_count = await get_db_manager().cleanup_old_data(days=7)
        
        if deleted_count > 0:
            logger.info(f"🗑️ Cleaned up {deleted_count} old odds records")
        else:
            logger.info("✨ No old odds records to clean up")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        await get_db_manager().close()

def main():
    """Main scheduler function"""
    logger.info("🎯 Pinnacle Odds Scheduler Starting...")
    logger.info("📅 Will scrape odds every 5 minutes (24/7 for testing)")
    logger.info("💰 Estimated daily cost: ~172,800 API credits (24/7 operation)")
    
    # Schedule the scraper to run every 5 minutes
    schedule.every(5).minutes.do(run_scraper_job)
    
    # Schedule cleanup to run every 6 hours
    schedule.every(6).hours.do(run_cleanup_job)
    
    # Run once immediately
    logger.info("🚀 Running initial scrape...")
    run_scraper_job()
    
    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
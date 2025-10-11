#!/usr/bin/env python3
"""
Pinnacle Odds Scheduler
Runs the scraper every 5 minutes from 1 PM to 1 AM EST
"""

import asyncio
import schedule
import time
import logging
from datetime import datetime, timezone, timedelta
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

def is_business_hours():
    """Check if current time is within business hours (1 PM to 1 AM EST)"""
    # EST is UTC-5, EDT is UTC-4 (we'll use UTC-5 for simplicity)
    est_offset = timedelta(hours=-5)
    now_est = datetime.now(timezone.utc) + est_offset
    current_hour = now_est.hour
    
    # Business hours: 1 PM (13:00) to 1 AM (01:00) next day
    return current_hour >= 13 or current_hour < 1

def run_scraper_job():
    """Wrapper function to run the scraper"""
    if not is_business_hours():
        logger.info("⏰ Outside business hours (1 PM - 1 AM EST), skipping scrape")
        return
        
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
    logger.info("📅 Will scrape odds every 5 minutes from 1 PM to 1 AM EST")
    logger.info("💰 Estimated daily cost: ~72,000 API credits (12-hour operation)")
    
    # Schedule the scraper to run every 5 minutes
    schedule.every(5).minutes.do(run_scraper_job)
    
    # Schedule cleanup to run every 6 hours
    schedule.every(6).hours.do(run_cleanup_job)
    
    # Run once immediately if within business hours
    if is_business_hours():
        logger.info("🚀 Running initial scrape (within business hours)...")
        run_scraper_job()
    else:
        logger.info("⏰ Outside business hours, skipping initial scrape")
    
    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
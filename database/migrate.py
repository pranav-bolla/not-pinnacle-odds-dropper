"""
Database migration script for Pinnacle Odds Tracker
"""

import asyncio
import asyncpg
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

async def run_migration():
    """Run database migration"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Read schema file
    schema_path = Path(__file__).parent / 'schema.sql'
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        
        # Check if tables already exist
        result = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('sports', 'events', 'markets', 'odds', 'odds_changes', 'alerts', 'user_preferences', 'price_history', 'bets')
        """)
        
        existing_tables = [row['table_name'] for row in result]
        
        if existing_tables:
            logger.info(f"Tables already exist: {', '.join(existing_tables)}")
            logger.info("Checking for missing columns...")
            
            # Check if price_history table is missing bet_limit column
            if 'price_history' in existing_tables:
                try:
                    await conn.execute("SELECT bet_limit FROM price_history LIMIT 1")
                    logger.info("bet_limit column already exists in price_history")
                except Exception:
                    logger.info("Adding missing bet_limit column to price_history table")
                    await conn.execute("ALTER TABLE price_history ADD COLUMN bet_limit DECIMAL(10,2)")
                    logger.info("Successfully added bet_limit column to price_history")
            
            # Check if odds_changes table is missing implied probability columns
            if 'odds_changes' in existing_tables:
                try:
                    await conn.execute("SELECT old_implied_prob FROM odds_changes LIMIT 1")
                    logger.info("implied probability columns already exist in odds_changes")
                except Exception:
                    logger.info("Adding missing implied probability columns to odds_changes table")
                    await conn.execute("ALTER TABLE odds_changes ADD COLUMN old_implied_prob DECIMAL(8,6)")
                    await conn.execute("ALTER TABLE odds_changes ADD COLUMN new_implied_prob DECIMAL(8,6)")
                    logger.info("Successfully added implied probability columns to odds_changes")
            
            logger.info("Database migration completed successfully")
        else:
            # Execute schema only if tables don't exist
            await conn.execute(schema_sql)
            logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_migration())

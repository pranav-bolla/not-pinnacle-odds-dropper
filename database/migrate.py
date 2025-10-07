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
            AND table_name IN ('sports', 'events', 'markets', 'odds', 'odds_changes', 'price_history', 'bets')
        """)
        
        existing_tables = [row['table_name'] for row in result]
        
        if existing_tables:
            logger.info(f"Tables already exist: {', '.join(existing_tables)}")
            logger.info("Skipping migration - database is already set up")
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

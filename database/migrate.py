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
        
        # Execute schema
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

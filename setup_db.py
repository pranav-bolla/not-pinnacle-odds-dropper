#!/usr/bin/env python3
"""
Database setup script for Pinnacle Odds Tracker
Creates database and runs migrations
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

async def create_database():
    """Create the database if it doesn't exist"""
    load_dotenv()
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return False
    
    # Parse the database URL to get connection details
    # Format: postgresql://user:password@host:port/database
    try:
        # Extract database name from URL
        db_name = database_url.split('/')[-1]
        # Create connection URL without database name
        base_url = '/'.join(database_url.split('/')[:-1]) + '/postgres'
        
        print(f"🔄 Creating database: {db_name}")
        
        # Connect to postgres database to create our database
        conn = await asyncpg.connect(base_url)
        
        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"✅ Database '{db_name}' created successfully")
        else:
            print(f"ℹ️  Database '{db_name}' already exists")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

async def run_migrations():
    """Run database migrations"""
    try:
        print("🔄 Running database migrations...")
        
        # Read and execute schema
        schema_path = Path(__file__).parent / 'database' / 'schema.sql'
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        database_url = os.getenv('DATABASE_URL')
        conn = await asyncpg.connect(database_url)
        
        # Execute schema
        await conn.execute(schema_sql)
        
        print("✅ Database migrations completed successfully")
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

async def verify_setup():
    """Verify the database setup"""
    try:
        print("🔄 Verifying database setup...")
        
        database_url = os.getenv('DATABASE_URL')
        conn = await asyncpg.connect(database_url)
        
        # Check if tables exist
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        expected_tables = ['sports', 'events', 'markets', 'odds', 'odds_changes', 'alerts', 'user_preferences']
        existing_tables = [row['table_name'] for row in tables]
        
        print(f"📊 Found {len(existing_tables)} tables:")
        for table in existing_tables:
            print(f"  - {table}")
        
        # Check if initial data exists
        sports_count = await conn.fetchval("SELECT COUNT(*) FROM sports")
        markets_count = await conn.fetchval("SELECT COUNT(*) FROM markets")
        
        print(f"📈 Initial data:")
        print(f"  - Sports: {sports_count}")
        print(f"  - Markets: {markets_count}")
        
        await conn.close()
        
        if all(table in existing_tables for table in expected_tables):
            print("✅ Database setup verified successfully")
            return True
        else:
            missing_tables = set(expected_tables) - set(existing_tables)
            print(f"❌ Missing tables: {missing_tables}")
            return False
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

async def main():
    """Main setup function"""
    print("🎯 Pinnacle Odds Tracker - Database Setup")
    print("=" * 50)
    
    # Check environment
    load_dotenv()
    if not os.getenv('DATABASE_URL'):
        print("❌ DATABASE_URL environment variable not set")
        print("Please copy env.example to .env and configure your database URL")
        sys.exit(1)
    
    # Create database
    if not await create_database():
        sys.exit(1)
    
    # Run migrations
    if not await run_migrations():
        sys.exit(1)
    
    # Verify setup
    if not await verify_setup():
        sys.exit(1)
    
    print("\n🎉 Database setup completed successfully!")
    print("You can now start the application with: python start.py")

if __name__ == "__main__":
    asyncio.run(main())

"""
Database connection and management for Pinnacle Odds Tracker
"""

import os
import asyncio
import asyncpg
from typing import Optional, List, Dict, Any
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self, min_connections: int = 5, max_connections: int = 20):
        """Initialize the database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=min_connections,
                max_size=max_connections,
                command_timeout=60
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close(self):
        """Close the database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries"""
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def execute_command(self, command: str, *args) -> str:
        """Execute a command (INSERT, UPDATE, DELETE) and return status"""
        async with self.get_connection() as conn:
            result = await conn.execute(command, *args)
            return result
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row from a query"""
        async with self.get_connection() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def upsert_event(self, event_data: Dict[str, Any]) -> uuid.UUID:
        """Insert or update an event"""
        query = """
        INSERT INTO events (event_id, sport_id, home_team, away_team, commence_time, status)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (event_id) 
        DO UPDATE SET 
            home_team = EXCLUDED.home_team,
            away_team = EXCLUDED.away_team,
            commence_time = EXCLUDED.commence_time,
            status = EXCLUDED.status,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """
        
        async with self.get_connection() as conn:
            result = await conn.fetchval(
                query,
                event_data['event_id'],
                event_data['sport_id'],
                event_data['home_team'],
                event_data['away_team'],
                event_data['commence_time'],
                event_data.get('status', 'upcoming')
            )
            return result
    
    async def insert_odds(self, odds_data: List[Dict[str, Any]]) -> int:
        """Insert multiple odds records"""
        if not odds_data:
            return 0
        
        query = """
        INSERT INTO odds (event_id, market_id, team_name, odds_value, point_value, bookmaker, scraped_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (event_id, market_id, team_name, scraped_at) 
        DO UPDATE SET 
            odds_value = EXCLUDED.odds_value,
            point_value = EXCLUDED.point_value
        """
        
        async with self.get_connection() as conn:
            await conn.executemany(
                query,
                [(row['event_id'], row['market_id'], row['team_name'], 
                  row['odds_value'], row['point_value'], row['bookmaker'], 
                  row['scraped_at']) for row in odds_data]
            )
            return len(odds_data)
    
    async def get_sport_id(self, sport_key: str) -> Optional[uuid.UUID]:
        """Get sport ID by sport key"""
        query = "SELECT id FROM sports WHERE sport_key = $1 AND active = true"
        result = await self.fetch_one(query, sport_key)
        return result['id'] if result else None
    
    async def get_market_id(self, market_key: str) -> Optional[uuid.UUID]:
        """Get market ID by market key"""
        query = "SELECT id FROM markets WHERE market_key = $1 AND active = true"
        result = await self.fetch_one(query, market_key)
        return result['id'] if result else None
    
    async def get_event_id_by_api_id(self, api_event_id: str) -> Optional[uuid.UUID]:
        """Get database event ID by API event ID"""
        query = "SELECT id FROM events WHERE event_id = $1"
        result = await self.fetch_one(query, api_event_id)
        return result['id'] if result else None
    
    async def get_current_odds(self, sport_key: Optional[str] = None, 
                              market_key: Optional[str] = None,
                              limit: int = 1000) -> List[Dict[str, Any]]:
        """Get current odds with optional filtering"""
        query = """
        SELECT 
            event_id,
            home_team,
            away_team,
            commence_time,
            sport_title,
            market_name,
            team_name,
            odds_value,
            point_value,
            scraped_at
        FROM current_odds
        WHERE 1=1
        """
        
        params = []
        param_count = 0
        
        if sport_key:
            param_count += 1
            query += f" AND sport_title = (SELECT sport_title FROM sports WHERE sport_key = ${param_count})"
            params.append(sport_key)
        
        if market_key:
            param_count += 1
            query += f" AND market_name = (SELECT market_name FROM markets WHERE market_key = ${param_count})"
            params.append(market_key)
        
        query += f" ORDER BY commence_time ASC LIMIT ${param_count + 1}"
        params.append(limit)
        
        return await self.execute_query(query, *params)
    
    async def get_recent_changes(self, hours: int = 24, 
                                min_change_percentage: float = 0.05) -> List[Dict[str, Any]]:
        """Get recent odds changes"""
        query = """
        SELECT 
            oc.id,
            e.event_id,
            e.home_team,
            e.away_team,
            e.commence_time,
            s.sport_title,
            m.market_name,
            oc.team_name,
            oc.old_odds,
            oc.new_odds,
            oc.odds_change,
            oc.change_percentage,
            oc.point_value,
            oc.change_type,
            oc.detected_at,
            oc.is_flagged
        FROM odds_changes oc
        JOIN events e ON oc.event_id = e.id
        JOIN sports s ON e.sport_id = s.id
        JOIN markets m ON oc.market_id = m.id
        WHERE oc.detected_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour' * $1
        AND oc.change_percentage >= $2
        ORDER BY oc.detected_at DESC
        """
        
        return await self.execute_query(query, hours, min_change_percentage)
    
    async def get_flagged_changes(self) -> List[Dict[str, Any]]:
        """Get flagged odds changes"""
        query = """
        SELECT 
            oc.id,
            e.event_id,
            e.home_team,
            e.away_team,
            e.commence_time,
            s.sport_title,
            m.market_name,
            oc.team_name,
            oc.old_odds,
            oc.new_odds,
            oc.odds_change,
            oc.change_percentage,
            oc.point_value,
            oc.change_type,
            oc.detected_at,
            oc.is_flagged,
            oc.flag_reason
        FROM odds_changes oc
        JOIN events e ON oc.event_id = e.id
        JOIN sports s ON e.sport_id = s.id
        JOIN markets m ON oc.market_id = m.id
        WHERE oc.is_flagged = true
        ORDER BY oc.detected_at DESC
        """
        
        return await self.execute_query(query)
    
    async def insert_odds_change(self, change_data: Dict[str, Any]) -> uuid.UUID:
        """Insert a single odds change record"""
        query = """
        INSERT INTO odds_changes (
            event_id, market_id, team_name, old_odds, new_odds, 
            odds_change, change_percentage, point_value, change_type,
            old_implied_prob, new_implied_prob
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
        ) RETURNING id
        """
        try:
            result = await self.fetch_one(query, 
                change_data['event_id'],
                change_data['market_id'], 
                change_data['team_name'],
                change_data['old_odds'],
                change_data['new_odds'],
                change_data['odds_change'],
                change_data['change_percentage'],
                change_data.get('point_value'),
                change_data.get('change_type', 'drop'),
                change_data.get('old_implied_prob'),
                change_data.get('new_implied_prob')
            )
            return result['id'] if result else None
        except Exception as e:
            logger.error(f"Error inserting odds change: {e}")
            return None

    async def insert_odds_changes(self, changes_data: List[Dict[str, Any]]) -> int:
        """Insert multiple odds changes"""
        if not changes_data:
            return 0
        
        inserted_count = 0
        for change_data in changes_data:
            change_id = await self.insert_odds_change(change_data)
            if change_id:
                inserted_count += 1
        
        return inserted_count

    async def flag_odds_change(self, change_id: uuid.UUID, reason: str) -> bool:
        """Flag an odds change for attention"""
        query = """
        UPDATE odds_changes 
        SET is_flagged = true, flag_reason = $2
        WHERE id = $1
        """
        
        result = await self.execute_command(query, change_id, reason)
        return "UPDATE 1" in result
    
    async def get_odds_history(self, event_id: str, market_key: str, 
                              team_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get odds history for a specific event/market/team"""
        query = """
        SELECT 
            o.odds_value,
            o.point_value,
            o.scraped_at
        FROM odds o
        JOIN events e ON o.event_id = e.id
        JOIN markets m ON o.market_id = m.id
        WHERE e.event_id = $1 
        AND m.market_key = $2 
        AND o.team_name = $3
        AND o.scraped_at >= CURRENT_TIMESTAMP - INTERVAL '%s hours'
        ORDER BY o.scraped_at ASC
        """
        
        return await self.execute_query(query, event_id, market_key, team_name, hours)
    
    async def cleanup_old_data(self, days: int = 7) -> int:
        """Clean up old odds data to keep database size manageable"""
        # Keep only the most recent odds for each event/market/team combination
        # and delete older duplicates older than specified days
        query = """
        WITH latest_odds AS (
            SELECT DISTINCT ON (event_id, market_id, team_name) 
                id, event_id, market_id, team_name, scraped_at
            FROM odds 
            ORDER BY event_id, market_id, team_name, scraped_at DESC
        ),
        old_odds AS (
            SELECT o.id
            FROM odds o
            LEFT JOIN latest_odds lo ON o.id = lo.id
            WHERE lo.id IS NULL
            AND o.scraped_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
        )
        DELETE FROM odds 
        WHERE id IN (SELECT id FROM old_odds)
        """
        
        result = await self.execute_command(query, days)
        # Extract number of deleted rows from result string
        if "DELETE" in result:
            return int(result.split()[-1])
        return 0

# Global database manager instance - will be initialized when needed
db_manager = None

def get_db_manager():
    """Get or create the database manager instance"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager

async def init_database():
    """Initialize the database connection"""
    manager = get_db_manager()
    await manager.initialize()

async def close_database():
    """Close the database connection"""
    if db_manager:
        await db_manager.close()

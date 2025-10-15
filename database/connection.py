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
    
    async def insert_sport(self, sport_key: str, sport_title: str) -> uuid.UUID:
        """Insert a new sport and return its ID"""
        query = """
        INSERT INTO sports (sport_key, sport_title, active)
        VALUES ($1, $2, true)
        ON CONFLICT (sport_key) DO UPDATE SET
            sport_title = EXCLUDED.sport_title,
            active = true,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """
        result = await self.fetch_one(query, sport_key, sport_title)
        return result['id']
    
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

    async def insert_price_history(self, event_id: uuid.UUID, market_id: uuid.UUID, 
                                 team_name: str, odds_value: float, point_value: Optional[float] = None, 
                                 bet_limit: Optional[float] = None) -> None:
        """Insert price history record"""
        query = """
        INSERT INTO price_history (event_id, market_id, team_name, odds_value, point_value, bet_limit)
        VALUES ($1, $2, $3, $4, $5, $6)
        """
        await self.execute_command(query, event_id, market_id, team_name, odds_value, point_value, bet_limit)

    async def get_price_history(self, api_event_id: str, market_id: uuid.UUID, 
                              team_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get price history for a specific event/market/team"""
        query = """
        SELECT 
            ph.odds_value,
            ph.point_value,
            ph.bet_limit,
            ph.scraped_at,
            e.home_team,
            e.away_team,
            s.sport_title,
            m.market_name
        FROM price_history ph
        JOIN events e ON ph.event_id = e.id
        JOIN sports s ON e.sport_id = s.id
        JOIN markets m ON ph.market_id = m.id
        WHERE e.event_id = $1 
        AND ph.market_id = $2 
        AND ph.team_name = $3
        AND ph.scraped_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour' * $4
        ORDER BY ph.scraped_at ASC
        """
        return await self.execute_query(query, api_event_id, market_id, team_name, hours)
    
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
        """Get recent odds changes with both sides of the market for no-vig calculation"""
        query = """
        WITH current_odds AS (
            SELECT DISTINCT ON (event_id, market_id, team_name, point_value)
                event_id, market_id, team_name, point_value, odds_value
            FROM odds
            ORDER BY event_id, market_id, team_name, point_value, scraped_at DESC
        )
        SELECT 
            oc.id,
            e.event_id,
            e.home_team,
            e.away_team,
            e.commence_time,
            s.sport_title,
            m.market_name,
            m.market_key,
            m.id as market_id,
            oc.team_name,
            oc.old_odds,
            oc.new_odds,
            oc.odds_change,
            oc.change_percentage,
            oc.point_value,
            oc.change_type,
            oc.detected_at,
            oc.is_flagged,
            -- Get the current odds for this specific team (not the old drop odds)
            (SELECT co.odds_value FROM current_odds co 
             WHERE co.event_id = oc.event_id 
             AND co.market_id = oc.market_id 
             AND co.team_name = oc.team_name
             AND co.point_value = oc.point_value
             LIMIT 1) as current_odds,
            -- Get the other sides' current odds for no-vig calculation
            CASE 
                WHEN m.market_key = 'h2h' AND s.sport_key IN ('soccer_epl', 'soccer_uefa_champs_league', 'soccer_spain_la_liga', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_france_ligue_one', 'soccer_efl_champ', 'soccer_uefa_europa_league', 'soccer_uefa_europa_conference_league') THEN
                    -- For soccer three-way moneyline, get all three sides as comma-separated string
                    (SELECT string_agg(co.odds_value::text, ',' ORDER BY 
                        CASE co.team_name 
                            WHEN 'Draw' THEN 1
                            ELSE 0 
                        END, co.team_name) 
                     FROM current_odds co 
                     WHERE co.event_id = oc.event_id 
                     AND co.market_id = oc.market_id)
                WHEN m.market_key = 'spreads' THEN
                    -- For spreads, get the opposite side (different team, negative point value)
                    -- Team A +1.5 is equivalent to Team B -1.5
                    (SELECT co.odds_value::text FROM current_odds co 
                     WHERE co.event_id = oc.event_id 
                     AND co.market_id = oc.market_id 
                     AND co.team_name != oc.team_name
                     AND co.point_value = -oc.point_value
                     LIMIT 1)
                WHEN m.market_key = 'totals' THEN
                    -- For totals, get the opposite side (Over vs Under)
                    (SELECT co.odds_value::text FROM current_odds co 
                     WHERE co.event_id = oc.event_id 
                     AND co.market_id = oc.market_id 
                     AND co.team_name != oc.team_name
                     AND co.point_value = oc.point_value
                     LIMIT 1)
                WHEN m.market_key = 'h2h' THEN
                    -- For non-soccer two-way moneyline, get the other side
                    (SELECT co.odds_value::text FROM current_odds co 
                     WHERE co.event_id = oc.event_id 
                     AND co.market_id = oc.market_id 
                     AND co.team_name != oc.team_name
                     LIMIT 1)
                ELSE NULL
            END as other_side_odds
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

    async def insert_bet(self, event_id: uuid.UUID, market_id: uuid.UUID, team_name: str, 
                        odds_value: float, stake: float, no_vig_odds: float, 
                        expected_value: float, point_value: Optional[float] = None,
                        bet_type: str = 'moneyline', notes: Optional[str] = None) -> uuid.UUID:
        """Insert a new bet into the database"""
        query = """
        INSERT INTO bets (event_id, market_id, team_name, odds_value, stake, 
                         no_vig_odds, expected_value, point_value, bet_type, notes)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """
        result = await self.fetch_one(query, event_id, market_id, team_name, 
                                    odds_value, stake, no_vig_odds, expected_value, 
                                    point_value, bet_type, notes)
        return result['id']

    async def get_bets(self, limit: int = 100, offset: int = 0, 
                      status_filter: Optional[str] = None,
                      search_term: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all logged bets with optional filtering"""
        base_query = """
        SELECT 
            b.id,
            b.odds_value,
            b.stake,
            b.no_vig_odds,
            b.expected_value,
            b.point_value,
            b.bet_type,
            b.status,
            b.notes,
            b.logged_at,
            e.event_id,
            e.home_team,
            e.away_team,
            e.commence_time,
            s.sport_title,
            m.market_name,
            b.team_name
        FROM bets b
        JOIN events e ON b.event_id = e.id
        JOIN sports s ON e.sport_id = s.id
        JOIN markets m ON b.market_id = m.id
        WHERE 1=1
        """
        
        params = []
        param_count = 0
        
        if status_filter and status_filter != 'all':
            param_count += 1
            base_query += f" AND b.status = ${param_count}"
            params.append(status_filter)
        
        if search_term:
            param_count += 1
            base_query += f" AND (e.home_team ILIKE ${param_count} OR e.away_team ILIKE ${param_count} OR b.team_name ILIKE ${param_count})"
            params.append(f"%{search_term}%")
        
        base_query += " ORDER BY b.logged_at DESC"
        
        param_count += 1
        base_query += f" LIMIT ${param_count}"
        params.append(limit)
        
        param_count += 1
        base_query += f" OFFSET ${param_count}"
        params.append(offset)
        
        return await self.execute_query(base_query, *params)

    async def update_bet_status(self, bet_id: uuid.UUID, status: str, notes: Optional[str] = None) -> bool:
        """Update the status of a bet"""
        query = """
        UPDATE bets 
        SET status = $2, notes = COALESCE($3, notes), updated_at = CURRENT_TIMESTAMP
        WHERE id = $1
        RETURNING id
        """
        result = await self.fetch_one(query, bet_id, status, notes)
        return result is not None

    async def get_bet_by_id(self, bet_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get a specific bet by ID"""
        query = """
        SELECT 
            b.id,
            b.odds_value,
            b.stake,
            b.no_vig_odds,
            b.expected_value,
            b.point_value,
            b.bet_type,
            b.status,
            b.notes,
            b.logged_at,
            e.event_id,
            e.home_team,
            e.away_team,
            e.commence_time,
            s.sport_title,
            m.market_name,
            b.team_name
        FROM bets b
        JOIN events e ON b.event_id = e.id
        JOIN sports s ON e.sport_id = s.id
        JOIN markets m ON b.market_id = m.id
        WHERE b.id = $1
        """
        return await self.fetch_one(query, bet_id)

    async def delete_bet(self, bet_id: uuid.UUID) -> bool:
        """Delete a bet by ID"""
        query = """
        DELETE FROM bets 
        WHERE id = $1
        RETURNING id
        """
        result = await self.fetch_one(query, bet_id)
        return result is not None

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

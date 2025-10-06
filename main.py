"""
Pinnacle Odds Drop Tracker (POD)
Scrapes Pinnacle odds from The Odds API to track line movements and drops.
Based on the existing arbitrage finder but focused specifically on Pinnacle data.
"""

import pandas as pd
from datetime import datetime, timezone
import json
import os
import hashlib
import aiohttp
import asyncio
from typing import List, Dict, Optional
import uuid
import logging
from dataclasses import dataclass
from database.connection import get_db_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pinnacle_odds.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('pinnacle_scraper')


@dataclass
class OddsData:
    """Data class for storing odds information"""
    event_id: str
    sport_key: str
    sport_title: str
    commence_time: str
    home_team: str
    away_team: str
    market_type: str
    team_name: str
    odds: float
    point: Optional[float]
    timestamp: datetime
    bookmaker: str = "pinnacle"


class RateLimiter:
    """Rate limiter for API requests"""
    def __init__(self, max_requests=10, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    async def acquire(self):
        """Acquire permission to make a request"""
        now = datetime.now()
        # Remove requests older than time window
        self.requests = [req_time for req_time in self.requests 
                        if (now - req_time).total_seconds() < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0]).total_seconds()
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
        
        self.requests.append(now)


class PinnacleOddsScraper:
    """Main class for scraping Pinnacle odds from The Odds API"""
    
    def __init__(self, api_key: str, state: str = "us"):
        self.api_key = api_key
        self.state = state.lower()
        self.base_url = "https://api.the-odds-api.com/v4/sports"
        self.output_dir = "pinnacle_data"
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize session and rate limiter
        self.session = None
        self.rate_limiter = RateLimiter(max_requests=25, time_window=1)  # 25 requests per second (under 30 limit)
        
        # Store scraped data
        self.all_odds_data = []
        self.odds_changes = []
        
        # Soccer sports 
        self.soccer_sports = [
            "soccer_epl",                                    # English Premier League
            "soccer_efl_champ",                             # English Championship
        ]
        
        # Other sports (secondary)
        self.other_sports = [
            "americanfootball_nfl",
            "basketball_nba", 
            "icehockey_nhl",
            "baseball_mlb",
            "americanfootball_ncaaf",
            "basketball_ncaab"
        ]
        
        # All sports combined
        self.all_sports = self.soccer_sports + self.other_sports
        
        # Market types - core markets (only supported markets)
        self.featured_markets = [
            "h2h",          # Moneyline/Head-to-Head
            "spreads",      # Point Spreads
            "totals"        # Over/Under Totals
        ]
        
        # Alternate markets
        self.alternate_markets = [
            "alternate_spreads",    # Alternative point spreads
            "alternate_totals",     # Alternative totals
            "spreads_h1",          # First half spreads
            "spreads_h2",          # Second half spreads
            "totals_h1",           # First half totals
            "totals_h2",           # Second half totals
        ]
        
        # All markets combined
        self.all_markets = self.featured_markets + self.alternate_markets
        
        # Only track Pinnacle
        self.bookmakers = ["pinnacle"]
        
        # Cache of allowed bookmaker keys for fast membership checks
        self.allowed_bookmaker_keys = set(b.lower() for b in self.bookmakers)
        
        # Store raw data
        self.raw_data = pd.DataFrame()
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def decimal_to_american(self, decimal_odds: float) -> int:
        """Convert decimal odds to American odds"""
        if decimal_odds >= 2.0:
            return int((decimal_odds - 1) * 100)
        else:
            return int(-100 / (decimal_odds - 1))
    
    async def make_request(self, url: str, params: dict) -> Optional[dict]:
        """Make API request with rate limiting and error handling"""
        try:
            await self.rate_limiter.acquire()
            
            async with self.session.get(url, params=params) as response:
                if response.status == 429:  # Rate limit exceeded
                    logger.warning("Rate limit exceeded, waiting 2 seconds")
                    await asyncio.sleep(2)
                    return await self.make_request(url, params)  # Retry
                
                response.raise_for_status()
                data = await response.json()
                
                logger.debug(f"Successfully fetched data from {url}")
                return data
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error making request to {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error making request to {url}: {e}")
            return None
    
    async def get_featured_odds(self, sport: str) -> List[dict]:
        """Fetch odds for featured markets from Pinnacle only"""
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{self.base_url}/{sport}/odds"
        
        params = {
            "apiKey": self.api_key,
            "bookmakers": ",".join(self.bookmakers),  # Only Pinnacle
            "markets": ",".join(self.featured_markets),
            "oddsFormat": "decimal",
            "commenceTimeFrom": current_time,
            "includeLinks": "true",
            "includeBetLimits": "true",  # Include bet limits in response
        }
        
        logger.info(f"Fetching featured odds for {sport}")
        data = await self.make_request(url, params)
        
        if data:
            logger.info(f"Retrieved {len(data)} events for {sport}")
            return data
        else:
            logger.warning(f"No data retrieved for {sport}")
            return []
    
    async def get_alternate_odds(self, sport: str, event_id: str) -> List[dict]:
        """Fetch alternate market odds for a specific event"""
        url = f"{self.base_url}/{sport}/events/{event_id}/odds"
        
        params = {
            "apiKey": self.api_key,
            "bookmakers": ",".join(self.bookmakers),  # Only Pinnacle
            "markets": ",".join(self.alternate_markets),
            "oddsFormat": "decimal",
            "includeLinks": "true",
        }
        
        logger.debug(f"Fetching alternate odds for event {event_id} in {sport}")
        data = await self.make_request(url, params)
        
        if data:
            return data
        else:
            return []
    
    async def process_odds_data(self, raw_data: List[dict]) -> List[Dict]:
        """Process raw API response and store in database"""
        processed_data = []
        odds_records = []
        
        for event in raw_data:
            event_id = event.get("id")
            sport_key = event.get("sport_key")
            sport_title = event.get("sport_title")
            commence_time = event.get("commence_time")
            home_team = event.get("home_team")
            away_team = event.get("away_team")
            
            # Get sport ID
            sport_id = await get_db_manager().get_sport_id(sport_key)
            if not sport_id:
                logger.warning(f"Sport {sport_key} not found in database")
                continue
            
            # Convert commence_time string to datetime object
            commence_datetime = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
            
            # Upsert event
            event_db_id = await get_db_manager().upsert_event({
                'event_id': event_id,
                'sport_id': sport_id,
                'home_team': home_team,
                'away_team': away_team,
                'commence_time': commence_datetime,
                'status': 'upcoming'
            })
            
            for bookmaker in event.get("bookmakers", []):
                if bookmaker.get("key") == "pinnacle":
                    for market in bookmaker.get("markets", []):
                        market_type = market.get("key")
                        
                        # Get market ID
                        market_id = await get_db_manager().get_market_id(market_type)
                        if not market_id:
                            logger.warning(f"Market {market_type} not found in database")
                            continue
                        
                        for outcome in market.get("outcomes", []):
                            team_name = outcome.get("name")
                            price = outcome.get("price", 0)
                            point = outcome.get("point")
                            bet_limit = outcome.get("bet_limit")  # Extract bet limit from API response
                            
                            # Convert to American odds
                            american_odds = self.decimal_to_american(price)
                            
                            # Create odds record for database
                            odds_record = {
                                'event_id': event_db_id,
                                'market_id': market_id,
                                'team_name': team_name,
                                'odds_value': american_odds,
                                'point_value': point,
                                'bet_limit': bet_limit,
                                'bookmaker': 'pinnacle',
                                'scraped_at': datetime.now(timezone.utc)
                            }
                            odds_records.append(odds_record)
                            
                            # Also create OddsData object for compatibility
                            odds_data = OddsData(
                                event_id=event_id,
                                sport_key=sport_key,
                                sport_title=sport_title,
                                commence_time=commence_time,
                                home_team=home_team,
                                away_team=away_team,
                                market_type=market_type,
                                team_name=team_name,
                                odds=american_odds,
                                point=point,
                                timestamp=datetime.now(timezone.utc),
                                bookmaker="pinnacle"
                            )
                            processed_data.append(odds_data)
        
        # Insert all odds records into database
        if odds_records:
            await get_db_manager().insert_odds(odds_records)
            logger.info(f"Inserted {len(odds_records)} odds records into database")
            
            # Also store in price history for graphing
            for record in odds_records:
                await get_db_manager().insert_price_history(
                    event_id=record['event_id'],
                    market_id=record['market_id'],
                    team_name=record['team_name'],
                    odds_value=record['odds_value'],
                    point_value=record.get('point_value'),
                    bet_limit=record.get('bet_limit')
                )
            logger.info(f"Inserted {len(odds_records)} price history records")
        
        return processed_data
    
    async def scrape_all_sports(self) -> List[OddsData]:
        """Scrape odds for all configured sports"""
        logger.info("Starting to scrape Pinnacle odds for all sports")
        all_odds = []
        
        # Process sports sequentially to avoid rate limiting issues
        for sport in self.all_sports:
            try:
                logger.info(f"Processing sport: {sport}")
                result = await self.get_featured_odds(sport)
                
                if result:
                    processed = await self.process_odds_data(result)
                    all_odds.extend(processed)
                    logger.info(f"Processed {len(processed)} odds entries for {sport}")
                    
                    # Skip alternate markets to reduce API costs
                    # Only scrape featured markets (h2h, spreads, totals)
                else:
                    logger.warning(f"No data retrieved for {sport}")
                
                # Small delay between sports to be safe
                await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error fetching odds for {sport}: {e}")
                continue
        
        logger.info(f"Total odds entries scraped: {len(all_odds)}")
        return all_odds
    
    def save_to_csv(self, odds_data: List[OddsData], filename: str = None):
        """Save odds data to CSV file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pinnacle_odds_{timestamp}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Convert to DataFrame
        data_dicts = []
        for odds in odds_data:
            data_dicts.append({
                'event_id': odds.event_id,
                'sport_key': odds.sport_key,
                'sport_title': odds.sport_title,
                'commence_time': odds.commence_time,
                'home_team': odds.home_team,
                'away_team': odds.away_team,
                'market_type': odds.market_type,
                'team_name': odds.team_name,
                'odds': odds.odds,
                'point': odds.point,
                'timestamp': odds.timestamp.isoformat(),
                'bookmaker': odds.bookmaker
            })
        
        df = pd.DataFrame(data_dicts)
        df.to_csv(filepath, index=False)
        logger.info(f"Saved {len(odds_data)} odds entries to {filepath}")
        
        return filepath
    
    def load_previous_data(self, filepath: str) -> List[OddsData]:
        """Load previous odds data for comparison"""
        try:
            df = pd.read_csv(filepath)
            previous_data = []
            
            for _, row in df.iterrows():
                odds_data = OddsData(
                    event_id=row['event_id'],
                    sport_key=row['sport_key'],
                    sport_title=row['sport_title'],
                    commence_time=row['commence_time'],
                    home_team=row['home_team'],
                    away_team=row['away_team'],
                    market_type=row['market_type'],
                    team_name=row['team_name'],
                    odds=row['odds'],
                    point=row['point'] if pd.notna(row['point']) else None,
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    bookmaker=row['bookmaker']
                )
                previous_data.append(odds_data)
            
            logger.info(f"Loaded {len(previous_data)} previous odds entries")
            return previous_data
            
        except Exception as e:
            logger.error(f"Error loading previous data: {e}")
            return []
    
    def american_to_decimal(self, american_odds: float) -> float:
        """Convert American odds to decimal odds"""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    
    def calculate_implied_probability_drop(self, old_odds: float, new_odds: float) -> float:
        """Calculate percentage drop using implied probability method"""
        # Convert American odds to decimal odds
        old_decimal = self.american_to_decimal(old_odds)
        new_decimal = self.american_to_decimal(new_odds)
        
        # Calculate implied probabilities
        old_probability = 1 / old_decimal
        new_probability = 1 / new_decimal
        
        # Calculate the difference in probabilities
        probability_difference = new_probability - old_probability
        
        # Calculate percentage drop: (difference / initial probability) * 100
        if old_probability != 0:
            percentage_drop = (probability_difference / old_probability) * 100
        else:
            percentage_drop = 0
            
        return percentage_drop

    def detect_odds_changes(self, current_odds: List[OddsData], 
                          previous_odds: List[OddsData], 
                          threshold: float = 0.05) -> List[Dict]:
        """Detect significant odds drops (better prices) between current and previous data"""
        changes = []
        
        # Create lookup dictionary for previous odds
        previous_lookup = {}
        for prev in previous_odds:
            key = (prev.event_id, prev.market_type, prev.team_name)
            previous_lookup[key] = prev
        
        # Check for changes in current odds
        for current in current_odds:
            key = (current.event_id, current.market_type, current.team_name)
            
            if key in previous_lookup:
                previous = previous_lookup[key]
                # Convert Decimal to float for comparison
                previous_odds_float = float(previous.odds) if hasattr(previous.odds, '__float__') else previous.odds
                odds_change = current.odds - previous_odds_float
                
                # Only flag as a drop if odds got BETTER (lower value)
                # For positive odds: 200 -> 180 is better (odds_change < 0)
                # For negative odds: -110 -> -120 is better (odds_change < 0)
                is_better_odds = odds_change < 0
                
                if is_better_odds:
                    # Calculate drop using implied probability method
                    drop_percentage = self.calculate_implied_probability_drop(previous_odds_float, current.odds)
                    
                    # Log all potential drops for debugging
                    logger.info(f"🔍 POTENTIAL DROP: {current.sport_title} - {current.home_team} vs {current.away_team} | {current.market_type} - {current.team_name} | {previous_odds_float} → {current.odds} | Drop: {drop_percentage:.2f}%")
                    
                    # Check if change exceeds threshold
                    if drop_percentage >= (threshold * 100):  # Convert threshold to percentage
                        change_info = {
                            'event_id': current.event_id,
                            'sport': current.sport_title,
                            'game': f"{current.home_team} vs {current.away_team}",
                            'market_type': current.market_type,
                            'team_name': current.team_name,
                            'old_odds': previous_odds_float,
                            'new_odds': current.odds,
                            'odds_change': odds_change,
                            'change_percentage': drop_percentage,
                            'point': current.point,
                            'commence_time': current.commence_time,
                            'detected_at': datetime.now(timezone.utc).isoformat()
                        }
                        changes.append(change_info)
                        
                        # Log confirmed drops
                        logger.info(f"✅ CONFIRMED DROP: {change_info['game']} | {change_info['team_name']} | {change_info['old_odds']} → {change_info['new_odds']} | Drop: {drop_percentage:.2f}%")
        
        logger.info(f"Detected {len(changes)} significant odds drops (better prices)")
        return changes
    
    async def get_previous_odds_from_database(self) -> List[OddsData]:
        """Get the most recent odds from database for comparison"""
        from database.connection import get_db_manager
        
        try:
            # Get the most recent odds for each event/market/team combination
            query = """
            WITH latest_odds AS (
                SELECT DISTINCT ON (event_id, market_id, team_name) 
                    id, event_id, market_id, team_name, odds_value, point_value, scraped_at
                FROM odds 
                WHERE scraped_at < NOW() - INTERVAL '1 minute'
                ORDER BY event_id, market_id, team_name, scraped_at DESC
            )
            SELECT 
                e.event_id as event_id,
                e.home_team,
                e.away_team,
                s.sport_key,
                s.sport_title,
                m.market_key as market_type,
                lo.team_name,
                lo.odds_value as odds,
                lo.point_value,
                lo.scraped_at,
                e.commence_time
            FROM latest_odds lo
            JOIN events e ON lo.event_id = e.id
            JOIN sports s ON e.sport_id = s.id
            JOIN markets m ON lo.market_id = m.id
            ORDER BY lo.scraped_at DESC
            LIMIT 1000
            """
            
            results = await get_db_manager().execute_query(query)
            
            previous_odds = []
            for row in results:
                odds_data = OddsData(
                    event_id=row['event_id'],
                    sport_key=row['sport_key'],
                    sport_title=row['sport_title'],
                    commence_time=row['commence_time'].isoformat(),
                    home_team=row['home_team'],
                    away_team=row['away_team'],
                    market_type=row['market_type'],
                    team_name=row['team_name'],
                    odds=row['odds'],
                    point=row['point_value'],
                    timestamp=row['scraped_at']
                )
                previous_odds.append(odds_data)
            
            logger.info(f"Retrieved {len(previous_odds)} previous odds from database")
            return previous_odds
            
        except Exception as e:
            logger.error(f"Error retrieving previous odds from database: {e}")
            return []

    async def store_changes_in_database(self, changes: List[Dict]) -> int:
        """Store odds changes in the database"""
        if not changes:
            return 0
        
        from database.connection import get_db_manager
        
        stored_count = 0
        for change in changes:
            try:
                # Get database event ID from API event ID
                db_event_id = await get_db_manager().get_event_id_by_api_id(change['event_id'])
                market_id = await get_db_manager().get_market_id(change['market_type'])
                
                if db_event_id and market_id:
                    # Calculate implied probabilities
                    old_decimal = self.american_to_decimal(change['old_odds'])
                    new_decimal = self.american_to_decimal(change['new_odds'])
                    old_implied_prob = 1 / old_decimal
                    new_implied_prob = 1 / new_decimal
                    
                    change_data = {
                        'event_id': db_event_id,
                        'market_id': market_id,
                        'team_name': change['team_name'],
                        'old_odds': change['old_odds'],
                        'new_odds': change['new_odds'],
                        'odds_change': change['odds_change'],
                        'change_percentage': change['change_percentage'],
                        'point_value': change.get('point'),
                        'change_type': 'drop',
                        'old_implied_prob': old_implied_prob,
                        'new_implied_prob': new_implied_prob
                    }
                    
                    change_id = await get_db_manager().insert_odds_change(change_data)
                    if change_id:
                        stored_count += 1
                        logger.info(f"✅ Stored drop in database: {change['game']} | {change['team_name']} | {change['change_percentage']:.2f}%")
                    else:
                        logger.error(f"❌ Failed to store drop in database: {change['game']}")
                else:
                    logger.error(f"❌ Could not find db_event_id or market_id for: {change['game']}")
                    
            except Exception as e:
                logger.error(f"Error storing change in database: {e}")
        
        logger.info(f"Stored {stored_count}/{len(changes)} odds changes in database")
        return stored_count
    
    def save_changes_to_json(self, changes: List[Dict], filename: str = None):
        """Save odds changes to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"odds_changes_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(changes, f, indent=2, default=str)
        
        logger.info(f"Saved {len(changes)} odds changes to {filepath}")
        return filepath
    
    async def run_scraping_session(self, compare_with_previous: bool = True) -> Dict:
        """Run a complete scraping session"""
        logger.info("Starting Pinnacle odds scraping session")
        
        # Scrape current odds
        current_odds = await self.scrape_all_sports()
        
        result = {
            'current_odds_count': len(current_odds),
            'changes_detected': 0,
            'changes_file': None
        }
        
        # Compare with previous data if requested
        if compare_with_previous:
            # Get previous odds from database
            previous_odds = await self.get_previous_odds_from_database()
            
            if previous_odds:
                # Detect changes
                changes = self.detect_odds_changes(current_odds, previous_odds)
                
                if changes:
                    # Store changes in database
                    stored_count = await self.store_changes_in_database(changes)
                    logger.info(f"Stored {stored_count} odds changes in database")
                    
                    result['changes_detected'] = len(changes)
                    
                    # Log significant changes
                    for change in changes:
                        logger.info(
                            f"ODDS CHANGE: {change['sport']} - {change['game']} | "
                            f"{change['market_type']} - {change['team_name']} | "
                            f"{change['old_odds']} → {change['new_odds']} "
                            f"({change['change_percentage']:.2f}%)"
                        )
                else:
                    logger.info("No significant odds changes detected")
            else:
                logger.info("No previous odds data found in database")
        
        logger.info("Scraping session completed")
        return result


async def main():
    """Main function to run the Pinnacle odds scraper"""
    # Get API key from environment variable
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        logger.error("ODDS_API_KEY environment variable not set")
        return
    
    # Initialize database
    try:
        await get_db_manager().initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return
    
    try:
        async with PinnacleOddsScraper(api_key) as scraper:
            result = await scraper.run_scraping_session()
            
            print(f"\n=== Scraping Results ===")
            print(f"Odds entries scraped: {result['current_odds_count']}")
            
            if result['changes_detected'] > 0:
                print(f"Significant changes detected: {result['changes_detected']}")
            else:
                print("No significant odds changes detected")
    finally:
        await get_db_manager().close()


if __name__ == "__main__":
    # Set up environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run the scraper
    asyncio.run(main())

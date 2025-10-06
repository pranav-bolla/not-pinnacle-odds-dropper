# Pinnacle Odds Scraping Technical Guide

## Overview
This guide explains how to scrape Pinnacle odds from The Odds API for tracking odds movements and drops. The implementation is based on the existing arbitrage finder but focused specifically on Pinnacle bookmaker data.

## API Setup

### 1. The Odds API Configuration
- **Base URL**: `https://api.the-odds-api.com/v4/sports`
- **Authentication**: API key required
- **Rate Limiting**: 500 requests per month (free tier), 10,000+ (paid tiers)
- **Regions**: `us`, `us2` (US markets)

### 2. Key Endpoints
```
GET /sports/{sport}/odds
GET /sports/{sport}/events/{event_id}/odds
```

## Sports Configuration

### Soccer Leagues (Primary Focus)
```python
soccer_sports = [
    "soccer_epl",           # English Premier League
    "soccer_efl_champ",     # English Championship
    "soccer_bundesliga",    # German Bundesliga
    "soccer_serie_a",       # Italian Serie A
    "soccer_ligue_one",     # French Ligue 1
    "soccer_la_liga",       # Spanish La Liga
    "soccer_uefa_champs_league",  # Champions League
    "soccer_uefa_europa_league",  # Europa League
    "soccer_uefa_europa_conference_league",  # Conference League
    "soccer_mls",           # Major League Soccer
    "soccer_brazil_campeonato",   # Brazilian Serie A
    "soccer_argentina_primera_division",     # Argentine Primera
]
```

### Other Sports (Secondary)
```python
other_sports = [
    "americanfootball_nfl",
    "basketball_nba", 
    "icehockey_nhl",
    "baseball_mlb",
    "americanfootball_ncaaf",
    "basketball_ncaab"
]
```

## Market Types

### Core Markets
```python
featured_markets = [
    "h2h",          # Moneyline/Head-to-Head
    "spreads",      # Point Spreads
    "totals"        # Over/Under Totals
]
```

### Alternate Markets
```python
alternate_markets = [
    "alternate_spreads",    # Alternative point spreads
    "alternate_totals",     # Alternative totals
    "spreads_h1",          # First half spreads
    "spreads_h2",          # Second half spreads
    "totals_h1",           # First half totals
    "totals_h2",           # Second half totals
]
```

## API Request Structure

### Basic Request Parameters
```python
params = {
    "apiKey": "your_api_key",
    "bookmakers": "pinnacle",           # Only Pinnacle
    "markets": "h2h,spreads,totals",   # Comma-separated markets
    "oddsFormat": "decimal",            # Decimal odds format
    "commenceTimeFrom": "2024-01-01T00:00:00Z",  # Start time filter
    "includeLinks": "true",             # Include betting links
}
```

### Response Structure
```json
[
  {
    "id": "event_id",
    "sport_key": "soccer_epl",
    "sport_title": "EPL",
    "commence_time": "2024-01-15T15:00:00Z",
    "home_team": "Manchester United",
    "away_team": "Liverpool",
    "bookmakers": [
      {
        "key": "pinnacle",
        "title": "Pinnacle",
        "last_update": "2024-01-15T10:30:00Z",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              {
                "name": "Manchester United",
                "price": 2.10,
                "point": null
              },
              {
                "name": "Liverpool", 
                "price": 3.40,
                "point": null
              }
            ]
          }
        ]
      }
    ]
  }
]
```

## Implementation Architecture

### 1. Async HTTP Client
```python
import aiohttp
import asyncio
from datetime import datetime, timezone

class PinnacleOddsScraper:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4/sports"
        self.session = None
```

### 2. Rate Limiting
```python
class RateLimiter:
    def __init__(self, max_requests=10, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    async def acquire(self):
        # Implement rate limiting logic
        pass
```

### 3. Data Processing
```python
def process_odds_data(self, raw_data):
    """Process raw API response into structured format"""
    processed_data = []
    
    for event in raw_data:
        for bookmaker in event.get("bookmakers", []):
            if bookmaker.get("key") == "pinnacle":
                # Process Pinnacle odds only
                pass
    
    return processed_data
```

## Error Handling

### 1. HTTP Status Codes
- **200**: Success
- **401**: Invalid API key
- **403**: Forbidden (quota exceeded)
- **429**: Rate limit exceeded
- **500**: Server error

### 2. Retry Logic
```python
async def make_request_with_retry(self, url, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = await self.session.get(url, params=params)
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

## Data Storage

### 1. Database Schema
```sql
CREATE TABLE pinnacle_odds (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255),
    sport_key VARCHAR(100),
    sport_title VARCHAR(100),
    commence_time TIMESTAMP,
    home_team VARCHAR(255),
    away_team VARCHAR(255),
    market_type VARCHAR(100),
    team_name VARCHAR(255),
    odds DECIMAL(10,3),
    point DECIMAL(10,2),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bookmaker VARCHAR(100) DEFAULT 'pinnacle'
);
```

### 2. Change Detection
```python
def detect_odds_changes(self, current_odds, previous_odds):
    """Detect when Pinnacle odds drop or change significantly"""
    changes = []
    
    for current in current_odds:
        for previous in previous_odds:
            if (current['event_id'] == previous['event_id'] and 
                current['market_type'] == previous['market_type'] and
                current['team_name'] == previous['team_name']):
                
                odds_change = current['odds'] - previous['odds']
                if abs(odds_change) > 0.05:  # 5% threshold
                    changes.append({
                        'event': current['event_id'],
                        'market': current['market_type'],
                        'team': current['team_name'],
                        'old_odds': previous['odds'],
                        'new_odds': current['odds'],
                        'change': odds_change,
                        'timestamp': datetime.now()
                    })
    
    return changes
```

## Monitoring & Alerts

### 1. Odds Movement Tracking
- Track odds changes over time
- Set thresholds for significant movements
- Alert on sharp line movements (indicates sharp money)

### 2. Key Metrics
- **Line Movement Speed**: How quickly odds change
- **Movement Direction**: Favoring which side
- **Volume Indicators**: Based on movement patterns
- **Sharp vs Public**: Identify professional vs recreational betting

## Best Practices

### 1. API Usage
- Use appropriate rate limiting
- Cache responses when possible
- Monitor API quota usage
- Handle errors gracefully

### 2. Data Quality
- Validate odds data before processing
- Handle missing or malformed data
- Implement data consistency checks
- Regular data quality audits

### 3. Performance
- Use async/await for concurrent requests
- Implement connection pooling
- Cache frequently accessed data
- Optimize database queries

## Security Considerations

### 1. API Key Protection
- Store API keys securely (environment variables)
- Rotate keys regularly
- Monitor API usage for anomalies
- Use HTTPS for all requests

### 2. Data Privacy
- Comply with data protection regulations
- Implement access controls
- Log access and usage
- Regular security audits

## Deployment

### 1. Environment Setup
```bash
# Install dependencies
pip install aiohttp asyncio pandas python-dotenv

# Set environment variables
export ODDS_API_KEY="1e926844efc2bdb47a3552415b65b3cd"
export DATABASE_URL="your_database_url"
```

### 2. Scheduling
```python
# Run every 5 minutes
import schedule
import time

def run_scraper():
    asyncio.run(main())

schedule.every(5).minutes.do(run_scraper)

while True:
    schedule.run_pending()
    time.sleep(1)
```

## Troubleshooting

### Common Issues
1. **Rate Limiting**: Implement proper backoff strategies
2. **Data Inconsistency**: Validate data before processing
3. **Network Issues**: Implement retry logic with exponential backoff
4. **API Changes**: Monitor API documentation for updates

### Debugging
- Enable detailed logging
- Monitor API response times
- Track error rates
- Implement health checks

This guide provides a comprehensive foundation for building a Pinnacle odds tracking system that can detect line movements and provide valuable insights for betting analysis.

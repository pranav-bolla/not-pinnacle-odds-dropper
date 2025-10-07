# Database State Check Commands

This document provides SQL queries to check the state of all database tables in the Not POD system.

## Prerequisites

Make sure Docker is running and the database container is active:
```bash
docker ps | grep pinnacle-postgres
```

## General Database Connection

Connect to the database:
```bash
cd /home/pranav/pod
docker exec pinnacle-postgres psql -U postgres -d pinnacle_odds
```

## Table Overview Queries

### 1. Check All Tables and Row Counts
```sql
SELECT 
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes,
    n_live_tup as live_rows
FROM pg_stat_user_tables 
ORDER BY tablename;
```

### 2. Check Table Sizes
```sql
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
```

## Sports Table

### Check All Sports
```sql
SELECT id, sport_key, sport_title, active, created_at 
FROM sports 
ORDER BY created_at DESC;
```

### Count Sports by Status
```sql
SELECT 
    active,
    COUNT(*) as count
FROM sports 
GROUP BY active;
```

## Events Table

### Recent Events
```sql
SELECT 
    e.event_id,
    e.home_team,
    e.away_team,
    s.sport_title,
    e.commence_time,
    e.status,
    e.created_at
FROM events e
JOIN sports s ON e.sport_id = s.id
ORDER BY e.created_at DESC
LIMIT 20;
```

### Events by Sport
```sql
SELECT 
    s.sport_title,
    COUNT(*) as event_count
FROM events e
JOIN sports s ON e.sport_id = s.id
GROUP BY s.sport_title
ORDER BY event_count DESC;
```

### Upcoming Events
```sql
SELECT 
    e.home_team,
    e.away_team,
    s.sport_title,
    e.commence_time
FROM events e
JOIN sports s ON e.sport_id = s.id
WHERE e.commence_time > NOW()
ORDER BY e.commence_time ASC
LIMIT 10;
```

## Markets Table

### All Markets
```sql
SELECT id, market_key, market_name, active, created_at 
FROM markets 
ORDER BY market_key;
```

### Market Usage Count
```sql
SELECT 
    m.market_name,
    COUNT(o.id) as usage_count
FROM markets m
LEFT JOIN odds o ON m.id = o.market_id
GROUP BY m.market_name
ORDER BY usage_count DESC;
```

## Odds Table

### Recent Odds (Last 10 Minutes)
```sql
SELECT 
    e.home_team,
    e.away_team,
    s.sport_title,
    m.market_name,
    o.team_name,
    o.odds_value,
    o.scraped_at
FROM odds o
JOIN events e ON o.event_id = e.id
JOIN sports s ON e.sport_id = s.id
JOIN markets m ON o.market_id = m.id
WHERE o.scraped_at >= NOW() - INTERVAL '10 minutes'
ORDER BY o.scraped_at DESC
LIMIT 20;
```

### Odds Count by Sport (Last Hour)
```sql
SELECT 
    s.sport_title,
    COUNT(*) as odds_count
FROM odds o
JOIN events e ON o.event_id = e.id
JOIN sports s ON e.sport_id = s.id
WHERE o.scraped_at >= NOW() - INTERVAL '1 hour'
GROUP BY s.sport_title
ORDER BY odds_count DESC;
```

### Odds Count by Time Period
```sql
SELECT 
    DATE_TRUNC('hour', scraped_at) as hour,
    COUNT(*) as odds_count
FROM odds
WHERE scraped_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', scraped_at)
ORDER BY hour DESC;
```

## Odds Changes Table (Drops)

### Recent Drops (Last 24 Hours)
```sql
SELECT 
    e.home_team,
    e.away_team,
    s.sport_title,
    m.market_name,
    oc.team_name,
    oc.old_odds,
    oc.new_odds,
    oc.change_percentage,
    oc.detected_at
FROM odds_changes oc
JOIN events e ON oc.event_id = e.id
JOIN sports s ON e.sport_id = s.id
JOIN markets m ON oc.market_id = m.id
WHERE oc.detected_at >= NOW() - INTERVAL '24 hours'
ORDER BY oc.detected_at DESC;
```

### Drop Statistics
```sql
SELECT 
    COUNT(*) as total_drops,
    AVG(change_percentage) as avg_change_percentage,
    MIN(change_percentage) as min_change,
    MAX(change_percentage) as max_change
FROM odds_changes
WHERE detected_at >= NOW() - INTERVAL '24 hours';
```

### Drops by Sport
```sql
SELECT 
    s.sport_title,
    COUNT(*) as drop_count
FROM odds_changes oc
JOIN events e ON oc.event_id = e.id
JOIN sports s ON e.sport_id = s.id
WHERE oc.detected_at >= NOW() - INTERVAL '24 hours'
GROUP BY s.sport_title
ORDER BY drop_count DESC;
```

## Price History Table

### Recent Price History
```sql
SELECT 
    e.home_team,
    e.away_team,
    s.sport_title,
    m.market_name,
    ph.team_name,
    ph.odds_value,
    ph.bet_limit,
    ph.scraped_at
FROM price_history ph
JOIN events e ON ph.event_id = e.id
JOIN sports s ON e.sport_id = s.id
JOIN markets m ON ph.market_id = m.id
WHERE ph.scraped_at >= NOW() - INTERVAL '1 hour'
ORDER BY ph.scraped_at DESC
LIMIT 20;
```

### Price History Count by Time
```sql
SELECT 
    DATE_TRUNC('hour', scraped_at) as hour,
    COUNT(*) as history_count
FROM price_history
WHERE scraped_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', scraped_at)
ORDER BY hour DESC;
```

## System Health Checks

### Check for Recent Scraping Activity
```sql
SELECT 
    'odds' as table_name,
    COUNT(*) as recent_count,
    MAX(scraped_at) as latest_scrape
FROM odds
WHERE scraped_at >= NOW() - INTERVAL '10 minutes'

UNION ALL

SELECT 
    'price_history' as table_name,
    COUNT(*) as recent_count,
    MAX(scraped_at) as latest_scrape
FROM price_history
WHERE scraped_at >= NOW() - INTERVAL '10 minutes';
```

### Check Database Performance
```sql
SELECT 
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch
FROM pg_stat_user_tables
ORDER BY seq_tup_read DESC;
```

### Check Index Usage
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

## Quick Health Check Commands

### One-liner Commands (Run from terminal)

```bash
# Check if scraper is working (should show recent odds)
docker exec pinnacle-postgres psql -U postgres -d pinnacle_odds -c "SELECT COUNT(*) FROM odds WHERE scraped_at >= NOW() - INTERVAL '10 minutes';"

# Check for recent drops
docker exec pinnacle-postgres psql -U postgres -d pinnacle_odds -c "SELECT COUNT(*) FROM odds_changes WHERE detected_at >= NOW() - INTERVAL '1 hour';"

# Check all sports are active
docker exec pinnacle-postgres psql -U postgres -d pinnacle_odds -c "SELECT sport_title, active FROM sports ORDER BY sport_title;"

# Check recent scraping activity
docker exec pinnacle-postgres psql -U postgres -d pinnacle_odds -c "SELECT s.sport_title, COUNT(*) as odds_count FROM odds o JOIN events e ON o.event_id = e.id JOIN sports s ON e.sport_id = s.id WHERE o.scraped_at >= NOW() - INTERVAL '10 minutes' GROUP BY s.sport_title ORDER BY odds_count DESC;"
```

## Troubleshooting Queries

### Find Events Without Odds
```sql
SELECT 
    e.event_id,
    e.home_team,
    e.away_team,
    s.sport_title
FROM events e
JOIN sports s ON e.sport_id = s.id
LEFT JOIN odds o ON e.id = o.event_id
WHERE o.id IS NULL
AND e.commence_time > NOW() - INTERVAL '1 day';
```

### Find Duplicate Odds
```sql
SELECT 
    event_id,
    market_id,
    team_name,
    COUNT(*) as duplicate_count
FROM odds
WHERE scraped_at >= NOW() - INTERVAL '1 hour'
GROUP BY event_id, market_id, team_name
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
```

### Check for Missing Price History
```sql
SELECT 
    COUNT(*) as odds_without_history
FROM odds o
LEFT JOIN price_history ph ON o.event_id = ph.event_id 
    AND o.market_id = ph.market_id 
    AND o.team_name = ph.team_name
WHERE o.scraped_at >= NOW() - INTERVAL '1 hour'
AND ph.id IS NULL;
```

## Notes

- Replace `INTERVAL '10 minutes'` with your desired time window
- Use `LIMIT` clauses for large result sets
- The `pinnacle-postgres` container name may vary
- All timestamps are in UTC
- Use `\q` to exit the PostgreSQL prompt

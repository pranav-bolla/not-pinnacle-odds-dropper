-- Pinnacle Odds Database Schema
-- Optimized for real-time odds tracking and change detection

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sports table
CREATE TABLE sports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sport_key VARCHAR(50) UNIQUE NOT NULL,
    sport_title VARCHAR(100) NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Events table
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id VARCHAR(255) UNIQUE NOT NULL, -- The Odds API event ID
    sport_id UUID REFERENCES sports(id) ON DELETE CASCADE,
    home_team VARCHAR(255) NOT NULL,
    away_team VARCHAR(255) NOT NULL,
    commence_time TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'upcoming', -- upcoming, live, completed, cancelled
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Markets table
CREATE TABLE markets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    market_key VARCHAR(50) UNIQUE NOT NULL,
    market_name VARCHAR(100) NOT NULL,
    market_category VARCHAR(50) NOT NULL, -- featured, alternate, live
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Odds table - main table for storing all odds data
CREATE TABLE odds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    market_id UUID REFERENCES markets(id) ON DELETE CASCADE,
    team_name VARCHAR(255) NOT NULL,
    odds_value DECIMAL(10,3) NOT NULL, -- American odds format
    point_value DECIMAL(10,2), -- For spreads and totals
    bookmaker VARCHAR(50) DEFAULT 'pinnacle',
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_live BOOLEAN DEFAULT false,
    
    -- Indexes for performance
    UNIQUE(event_id, market_id, team_name, scraped_at)
);

-- Odds changes table - for tracking significant movements
CREATE TABLE odds_changes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    market_id UUID REFERENCES markets(id) ON DELETE CASCADE,
    team_name VARCHAR(255) NOT NULL,
    old_odds DECIMAL(10,3) NOT NULL,
    new_odds DECIMAL(10,3) NOT NULL,
    odds_change DECIMAL(10,3) NOT NULL,
    change_percentage DECIMAL(8,4) NOT NULL,
    point_value DECIMAL(10,2),
    change_type VARCHAR(20) NOT NULL, -- 'increase', 'decrease', 'significant_drop'
    old_implied_prob DECIMAL(8,6),
    new_implied_prob DECIMAL(8,6),
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_flagged BOOLEAN DEFAULT false,
    flag_reason TEXT
);

-- Alerts table - for user notifications
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    odds_change_id UUID REFERENCES odds_changes(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL, -- 'odds_drop', 'line_movement', 'sharp_money'
    severity VARCHAR(20) DEFAULT 'medium', -- low, medium, high, critical
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User preferences table (for future user management)
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255), -- For future user system
    sport_ids UUID[] DEFAULT '{}',
    market_ids UUID[] DEFAULT '{}',
    change_threshold DECIMAL(8,4) DEFAULT 0.05, -- 5% default threshold
    notification_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Price history table for tracking odds over time
CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    market_id UUID REFERENCES markets(id) ON DELETE CASCADE,
    team_name VARCHAR(255) NOT NULL,
    odds_value DECIMAL(10,3) NOT NULL,
    point_value DECIMAL(10,2),
    bet_limit DECIMAL(10,2),
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes
CREATE INDEX idx_odds_event_market ON odds(event_id, market_id);
CREATE INDEX idx_odds_scraped_at ON odds(scraped_at DESC);
CREATE INDEX idx_odds_team_name ON odds(team_name);
CREATE INDEX idx_odds_value ON odds(odds_value);

CREATE INDEX idx_price_history_event_market_team ON price_history(event_id, market_id, team_name);
CREATE INDEX idx_price_history_scraped_at ON price_history(scraped_at DESC);

CREATE INDEX idx_odds_changes_event ON odds_changes(event_id);
CREATE INDEX idx_odds_changes_detected_at ON odds_changes(detected_at DESC);
CREATE INDEX idx_odds_changes_flagged ON odds_changes(is_flagged) WHERE is_flagged = true;
CREATE INDEX idx_odds_changes_percentage ON odds_changes(change_percentage DESC);

CREATE INDEX idx_events_commence_time ON events(commence_time);
CREATE INDEX idx_events_sport ON events(sport_id);
CREATE INDEX idx_events_status ON events(status);

-- Views for common queries
CREATE VIEW current_odds AS
SELECT 
    e.event_id,
    e.home_team,
    e.away_team,
    e.commence_time,
    s.sport_title,
    m.market_name,
    o.team_name,
    o.odds_value,
    o.point_value,
    o.scraped_at
FROM odds o
JOIN events e ON o.event_id = e.id
JOIN sports s ON e.sport_id = s.id
JOIN markets m ON o.market_id = m.id
WHERE o.scraped_at = (
    SELECT MAX(scraped_at) 
    FROM odds o2 
    WHERE o2.event_id = o.event_id 
    AND o2.market_id = o.market_id 
    AND o2.team_name = o.team_name
);

CREATE VIEW recent_odds_changes AS
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
WHERE oc.detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY oc.detected_at DESC;

-- Functions for data management
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic timestamp updates
CREATE TRIGGER update_sports_updated_at BEFORE UPDATE ON sports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to detect odds changes
CREATE OR REPLACE FUNCTION detect_odds_changes(
    p_event_id UUID,
    p_market_id UUID,
    p_team_name VARCHAR,
    p_new_odds DECIMAL,
    p_point_value DECIMAL DEFAULT NULL,
    p_threshold DECIMAL DEFAULT 0.05
)
RETURNS BOOLEAN AS $$
DECLARE
    v_previous_odds DECIMAL;
    v_change_percentage DECIMAL;
    v_change_type VARCHAR;
BEGIN
    -- Get the most recent odds for this event/market/team
    SELECT odds_value INTO v_previous_odds
    FROM odds
    WHERE event_id = p_event_id 
    AND market_id = p_market_id 
    AND team_name = p_team_name
    ORDER BY scraped_at DESC
    LIMIT 1;
    
    -- If no previous odds, no change to detect
    IF v_previous_odds IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Calculate change percentage
    v_change_percentage := ABS(p_new_odds - v_previous_odds) / ABS(v_previous_odds);
    
    -- Check if change exceeds threshold
    IF v_change_percentage >= p_threshold THEN
        -- Determine change type
        IF p_new_odds < v_previous_odds THEN
            v_change_type := 'decrease';
        ELSE
            v_change_type := 'increase';
        END IF;
        
        -- Insert change record
        INSERT INTO odds_changes (
            event_id, market_id, team_name, old_odds, new_odds,
            odds_change, change_percentage, point_value, change_type
        ) VALUES (
            p_event_id, p_market_id, p_team_name, v_previous_odds, p_new_odds,
            p_new_odds - v_previous_odds, v_change_percentage, p_point_value, v_change_type
        );
        
        RETURN TRUE;
    END IF;
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Insert initial data
INSERT INTO sports (sport_key, sport_title) VALUES
('soccer_epl', 'English Premier League'),
('soccer_efl_champ', 'English Championship'),
('soccer_bundesliga', 'German Bundesliga'),
('soccer_serie_a', 'Italian Serie A'),
('soccer_ligue_one', 'French Ligue 1'),
('soccer_la_liga', 'Spanish La Liga'),
('soccer_uefa_champs_league', 'Champions League'),
('soccer_uefa_europa_league', 'Europa League'),
('soccer_uefa_europa_conference_league', 'Conference League'),
('soccer_mls', 'Major League Soccer'),
('soccer_brazil_campeonato', 'Brazilian Serie A'),
('soccer_argentina_primera_division', 'Argentine Primera'),
('americanfootball_nfl', 'NFL'),
('basketball_nba', 'NBA'),
('icehockey_nhl', 'NHL'),
('baseball_mlb', 'MLB'),
('americanfootball_ncaaf', 'NCAA Football'),
('basketball_ncaab', 'NCAA Basketball');

INSERT INTO markets (market_key, market_name, market_category) VALUES
-- Featured markets
('h2h', 'Moneyline', 'featured'),
('spreads', 'Point Spread', 'featured'),
('totals', 'Over/Under', 'featured'),
-- Alternate markets
('alternate_spreads', 'Alternate Spreads', 'alternate'),
('alternate_totals', 'Alternate Totals', 'alternate'),
('spreads_h1', '1st Half Spread', 'alternate'),
('spreads_h2', '2nd Half Spread', 'alternate'),
('totals_h1', '1st Half Total', 'alternate'),
('totals_h2', '2nd Half Total', 'alternate');

-- Bets table - for logging user bets
CREATE TABLE bets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    market_id UUID REFERENCES markets(id) ON DELETE CASCADE,
    team_name VARCHAR(255) NOT NULL,
    odds_value DECIMAL(10,3) NOT NULL,
    stake DECIMAL(10,2) NOT NULL,
    no_vig_odds DECIMAL(10,3) NOT NULL,
    expected_value DECIMAL(10,4) NOT NULL,
    point_value DECIMAL(10,2),
    bet_type VARCHAR(50) NOT NULL, -- 'moneyline', 'spread', 'total'
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'won', 'lost', 'push'
    notes TEXT,
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for bets table
CREATE INDEX idx_bets_event_id ON bets(event_id);
CREATE INDEX idx_bets_logged_at ON bets(logged_at DESC);
CREATE INDEX idx_bets_status ON bets(status);

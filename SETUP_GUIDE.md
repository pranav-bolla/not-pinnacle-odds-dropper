# Pinnacle Odds Tracker - Setup Guide

## 🎯 What We've Built

A comprehensive real-time odds tracking system with:

### 🏗️ Architecture
- **Backend**: FastAPI with WebSocket support
- **Database**: PostgreSQL with optimized schema
- **Frontend**: Beautiful stock market-inspired dark theme
- **Scraper**: Async Python scraper with change detection

### 🎨 Frontend Features
- **Dark Theme**: Stock market aesthetics with blacks, greens, and reds
- **Real-time Updates**: WebSocket connections for live data
- **Responsive Design**: Works on desktop and mobile
- **Multiple Views**: Live odds, drops, history, and settings
- **Smart Notifications**: Browser and sound alerts

### 📊 Database Schema
- **Normalized Design**: Efficient storage with proper relationships
- **Change Tracking**: Comprehensive odds change history
- **Performance Optimized**: Indexed queries and views
- **Data Retention**: Configurable cleanup policies

## 🚀 Quick Setup

### 1. Prerequisites
```bash
# Install Python 3.8+
# Install PostgreSQL 12+
# Get The Odds API key from https://the-odds-api.com/
```

### 2. Installation
```bash
# Clone and setup
git clone <repository-url>
cd pod
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your API key and database URL
```

### 3. Database Setup
```bash
# Option 1: Using setup script
python setup_db.py

# Option 2: Manual setup
createdb pinnacle_odds
python database/migrate.py
```

### 4. Start the Application
```bash
# Option 1: All-in-one startup
python start.py

# Option 2: Manual startup
# Terminal 1: Backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Scraper
python main.py

# Terminal 3: Scheduler (optional)
python scheduler.py
```

### 5. Access the Application
- **Web Interface**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## 🐳 Docker Setup

### Using Docker Compose
```bash
# Set your API key
export ODDS_API_KEY=your_api_key_here

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Manual Docker
```bash
# Build image
docker build -t pinnacle-odds .

# Run with environment
docker run -p 8000:8000 \
  -e ODDS_API_KEY=your_key \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  pinnacle-odds
```

## 📁 Project Structure

```
pod/
├── backend/              # FastAPI backend
│   └── main.py          # API server with WebSocket
├── database/            # Database management
│   ├── schema.sql       # Complete database schema
│   ├── connection.py    # Database connection manager
│   └── migrate.py       # Migration script
├── frontend/            # Frontend assets
│   └── dist/           # Built frontend files
│       ├── index.html  # Main HTML page
│       ├── styles.css  # Beautiful dark theme CSS
│       └── app.js      # Frontend JavaScript app
├── main.py             # Main odds scraper
├── start.py            # All-in-one startup script
├── setup_db.py         # Database setup script
├── scheduler.py        # Scheduled scraper
├── requirements.txt    # Python dependencies
├── docker-compose.yml  # Docker setup
├── Dockerfile         # Docker image
└── README.md          # Comprehensive documentation
```

## 🔧 Configuration

### Environment Variables
```bash
# Required
ODDS_API_KEY=your_odds_api_key_here
DATABASE_URL=postgresql://user:pass@host:5432/db

# Optional
DEBUG=true
LOG_LEVEL=INFO
SCRAPING_INTERVAL_MINUTES=5
DEFAULT_CHANGE_THRESHOLD=0.05
```

### Sports & Markets
The system tracks:
- **Soccer**: EPL, Championship, Bundesliga, Serie A, Ligue 1, La Liga, Champions League, Europa League, MLS, Brazilian Serie A, Argentine Primera
- **American Sports**: NFL, NBA, NHL, MLB, NCAA Football, NCAA Basketball
- **Markets**: Moneyline, Point Spreads, Over/Under, Alternate markets, Half-time markets

## 🎯 Key Features

### Real-time Odds Tracking
- Monitors Pinnacle odds across multiple sports
- Detects significant changes and drops
- WebSocket updates for live data
- Historical tracking and analysis

### Beautiful Interface
- Stock market-inspired dark theme
- Responsive design for all devices
- Intuitive navigation and controls
- Real-time animations and updates

### Smart Alerts
- Configurable change thresholds
- Sound and browser notifications
- Flagged changes for review
- Historical change tracking

### Performance Optimized
- Async/await throughout
- Database indexing and optimization
- Connection pooling
- Efficient data structures

## 🔍 Usage

### Web Interface
1. **Live Odds**: View current odds across all sports
2. **Drops**: See significant odds changes and drops
3. **History**: Browse historical odds changes
4. **Settings**: Configure thresholds and notifications

### API Endpoints
- `GET /api/odds` - Current odds data
- `GET /api/odds/changes` - Recent changes
- `GET /api/odds/history/{event_id}` - Event history
- `POST /api/odds/changes/{change_id}/flag` - Flag changes
- `WebSocket /ws` - Real-time updates

### Scraper
- Runs every 5 minutes (configurable)
- Compares with previous data
- Detects significant changes
- Stores in database
- Broadcasts via WebSocket

## 🚨 Troubleshooting

### Common Issues
1. **Database Connection**: Check PostgreSQL is running and DATABASE_URL is correct
2. **API Rate Limiting**: Reduce scraping frequency or check API quota
3. **WebSocket Issues**: Check firewall and WebSocket support
4. **No Data**: Verify API key and network connectivity

### Debug Mode
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### Logs
- Application: `pinnacle_odds.log`
- Scheduler: `scheduler.log`
- Console output for real-time monitoring

## 📈 Monitoring

### Key Metrics
- Total events tracked
- Recent changes (24h)
- Flagged changes
- API usage and rate limits

### Health Checks
- Database connectivity
- API endpoint responses
- WebSocket connections
- Scraper status

## 🎉 Success!

You now have a fully functional Pinnacle odds tracking system with:

✅ **Beautiful dark-themed interface**  
✅ **Real-time odds monitoring**  
✅ **Change detection and alerts**  
✅ **Historical data tracking**  
✅ **WebSocket live updates**  
✅ **Responsive design**  
✅ **Docker support**  
✅ **Comprehensive documentation**  

The system is ready to track odds drops and provide valuable insights for betting analysis!

# Pinnacle Odds Drop Tracker (POD)

A real-time odds tracking system that monitors Pinnacle odds movements and alerts users to significant drops and changes. Built with a beautiful stock market-inspired dark theme interface.

## Features

### Core Functionality
- **Real-time Odds Tracking**: Monitors Pinnacle odds across multiple sports and markets
- **Change Detection**: Automatically detects significant odds movements and drops
- **WebSocket Updates**: Live updates via WebSocket connections
- **Historical Data**: Track odds changes over time with detailed history

### Beautiful Interface
- **Stock Market Theme**: Dark theme with blacks, greens, and reds
- **Responsive Design**: Works perfectly on desktop and mobile
- **Real-time Updates**: Live odds updates with smooth animations
- **Intuitive Navigation**: Easy-to-use tabs for different views

### Sports & Markets
- **Soccer**: English Premier League, English Championship
- **American Sports**: NFL, NBA, NHL, MLB, NCAA Football, NCAA Basketball
- **Markets**: Moneyline, Point Spreads, Over/Under, Alternate markets (for non-soccer sports)

### Smart Alerts
- **Configurable Thresholds**: Set custom change detection thresholds
- **Sound Notifications**: Audio alerts for significant changes
- **Browser Notifications**: Desktop notifications for important updates
- **Flagged Changes**: Mark important changes for review

### Automatic Monitoring
- **Rescraping Frequency**: Every 5 minutes from 9 AM to 9 PM EST
- **Change Detection**: Automatically flags odds drops of 5% or more
- **Real-time Updates**: WebSocket connections provide instant updates
- **Historical Tracking**: All odds changes are stored for analysis
- **Business Hours Only**: Runs during active betting hours to optimize API usage

## Architecture

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **PostgreSQL**: Robust database for storing odds and change data
- **WebSockets**: Real-time communication with frontend
- **Async/Await**: High-performance async operations

### Frontend
- **Vanilla JavaScript**: No framework dependencies for maximum performance
- **CSS Grid/Flexbox**: Modern responsive layout
- **WebSocket Client**: Real-time data updates
- **Local Storage**: User preferences and settings

### Database Schema
- **Normalized Design**: Efficient storage with proper relationships
- **Indexed Queries**: Fast lookups and filtering
- **Change Tracking**: Comprehensive odds change history
- **Data Retention**: Configurable cleanup policies

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- The Odds API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pod
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

4. **Set up the database**
   ```bash
   # Create PostgreSQL database
   createdb pinnacle_odds
   
   # Run migrations
   python database/migrate.py
   ```

5. **Start the application**
   ```bash
   # Start the backend
   python backend/main.py
   
   # In another terminal, start the scraper
   python main.py
   ```

6. **Access the application**
   Open your browser to `http://localhost:8000`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ODDS_API_KEY` | The Odds API key | Required |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `API_RATE_LIMIT` | API requests per minute | `10` |
| `DEFAULT_CHANGE_THRESHOLD` | Default change detection threshold | `0.05` |

### API Configuration

The scraper is configured to track:
- **Primary Sports**: Soccer leagues (EPL, Championship, etc.)
- **Secondary Sports**: NFL, NBA, NHL, MLB, NCAA
- **Markets**: Moneyline, spreads, totals, alternate markets
- **Bookmaker**: Pinnacle only

## Usage

### Web Interface

1. **Live Odds Tab**: View current odds across all sports and markets
2. **Drops Tab**: See significant odds changes and drops
3. **History Tab**: Browse historical odds changes
4. **Settings Tab**: Configure thresholds, notifications, and display options

### API Endpoints

- `GET /api/odds` - Get current odds data
- `GET /api/odds/changes` - Get recent odds changes
- `GET /api/odds/history/{event_id}` - Get odds history for an event
- `POST /api/odds/changes/{change_id}/flag` - Flag an odds change
- `GET /api/stats` - Get system statistics
- `WebSocket /ws` - Real-time updates

### Scraper

The scraper runs continuously and:
1. Fetches odds from The Odds API every X minutes
2. Compares with previous data to detect changes
3. Stores new data in the database
4. Broadcasts changes via WebSocket
5. Logs significant movements

## Development

### Project Structure
```
pod/
├── backend/           # FastAPI backend
│   └── main.py       # API server
├── database/         # Database management
│   ├── schema.sql    # Database schema
│   ├── connection.py # Database connection
│   └── migrate.py    # Migration script
├── frontend/         # Frontend assets
│   └── dist/        # Built frontend files
├── main.py          # Main scraper
├── requirements.txt # Python dependencies
└── README.md       # This file
```

### Running in Development

1. **Start PostgreSQL**
   ```bash
   # Using Docker
   docker run -d --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15
   ```

2. **Run migrations**
   ```bash
   python database/migrate.py
   ```

3. **Start the backend**
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Start the scraper**
   ```bash
   # Run once manually
   python main.py
   
   # Or run continuously every 5 minutes
   python start_scheduler.py
   ```

### Database Management

```bash
# Run migrations
python database/migrate.py

# Connect to database
psql $DATABASE_URL

# View recent changes
SELECT * FROM recent_odds_changes LIMIT 10;

# Clean up old data
SELECT cleanup_old_data(30); -- Keep 30 days
```

## Monitoring

### Key Metrics
- **Total Events**: Number of tracked events
- **Recent Changes**: Changes in last 24 hours
- **Flagged Changes**: Important changes requiring attention
- **API Usage**: Rate limit monitoring

### Logs
- Application logs: `pinnacle_odds.log`
- Error tracking: Console and file output
- Performance metrics: Response times and throughput

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL is running
   - Verify DATABASE_URL format
   - Ensure database exists

2. **API Rate Limiting**
   - Reduce scraping frequency
   - Check API quota usage
   - Implement proper backoff

3. **WebSocket Connection Issues**
   - Check firewall settings
   - Verify WebSocket support
   - Monitor connection logs

4. **No Odds Data**
   - Verify API key is valid
   - Check network connectivity
   - Review API response logs

### Debug Mode

Enable debug mode for detailed logging:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the API documentation

## Roadmap

### Planned Features
- [ ] User authentication and preferences
- [ ] Email/SMS notifications
- [ ] Advanced filtering and search
- [ ] Mobile app
- [ ] API rate limit optimization
- [ ] Historical data analysis
- [ ] Export functionality
- [ ] Multi-bookmaker support

### Performance Improvements
- [ ] Database query optimization
- [ ] Caching layer
- [ ] CDN for static assets
- [ ] Horizontal scaling support

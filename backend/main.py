"""
FastAPI backend for Pinnacle Odds Tracker
Provides REST API and WebSocket endpoints for real-time odds data
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List, Dict, Optional, Any
import asyncio
import json
import logging
from datetime import datetime, timezone
import uuid
from contextlib import asynccontextmanager

from database.connection import get_db_manager, init_database, close_database
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_database()
    logger.info("FastAPI application started")
    yield
    # Shutdown
    await close_database()
    logger.info("FastAPI application shutdown")

app = FastAPI(
    title="Pinnacle Odds Tracker API",
    description="Real-time odds tracking and change detection",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend/dist"), name="static")

@app.get("/")
async def read_root():
    """Serve the main HTML page"""
    try:
        with open("frontend/dist/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return {"message": "Frontend not built. Run 'npm run build' in the frontend directory."}

@app.get("/favicon.svg")
async def favicon():
    """Serve the favicon"""
    try:
        with open("frontend/dist/favicon.svg", "r") as f:
            return HTMLResponse(content=f.read(), media_type="image/svg+xml")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Favicon not found")

# API Endpoints

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/sports")
async def get_sports():
    """Get all available sports"""
    try:
        sports = await get_db_manager().execute_query("SELECT * FROM sports WHERE active = true ORDER BY sport_title")
        return {"sports": sports}
    except Exception as e:
        logger.error(f"Error fetching sports: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sports")

@app.get("/api/markets")
async def get_markets():
    """Get all available markets"""
    try:
        markets = await get_db_manager().execute_query("SELECT * FROM markets WHERE active = true ORDER BY market_name")
        return {"markets": markets}
    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch markets")

@app.get("/api/odds")
async def get_odds(
    sport_key: Optional[str] = Query(None, description="Filter by sport key"),
    market_key: Optional[str] = Query(None, description="Filter by market key"),
    limit: int = Query(1000, description="Maximum number of results")
):
    """Get current odds data"""
    try:
        odds = await get_db_manager().get_current_odds(sport_key, market_key, limit)
        return {"odds": odds, "count": len(odds)}
    except Exception as e:
        logger.error(f"Error fetching odds: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch odds")

@app.get("/api/odds/changes")
async def get_odds_changes(
    hours: int = Query(24, description="Hours to look back"),
    min_change_percentage: float = Query(0.05, description="Minimum change percentage"),
    flagged_only: bool = Query(False, description="Only return flagged changes")
):
    """Get recent odds changes"""
    try:
        if flagged_only:
            changes = await get_db_manager().get_flagged_changes()
        else:
            changes = await get_db_manager().get_recent_changes(hours, min_change_percentage)
        return {"changes": changes, "count": len(changes)}
    except Exception as e:
        logger.error(f"Error fetching odds changes: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch odds changes")

@app.get("/api/odds/history/{event_id}")
async def get_odds_history(
    event_id: str,
    market_key: str = Query(..., description="Market key"),
    team_name: str = Query(..., description="Team name"),
    hours: int = Query(24, description="Hours to look back")
):
    """Get odds history for a specific event/market/team"""
    try:
        history = await get_db_manager().get_odds_history(event_id, market_key, team_name, hours)
        return {"history": history, "count": len(history)}
    except Exception as e:
        logger.error(f"Error fetching odds history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch odds history")

@app.get("/api/price-history/{event_id}")
async def get_price_history(
    event_id: str,
    market_id: str = Query(..., description="Market ID"),
    team_name: str = Query(..., description="Team name"),
    hours: int = Query(24, description="Hours to look back")
):
    """Get price history for a specific event/market/team for graphing"""
    try:
        import uuid
        market_uuid = uuid.UUID(market_id)
        
        history = await get_db_manager().get_price_history(event_id, market_uuid, team_name, hours)
        return {"history": history, "count": len(history)}
    except Exception as e:
        logger.error(f"Error fetching price history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch price history")

@app.post("/api/odds/changes/{change_id}/flag")
async def flag_odds_change(
    change_id: str,
    reason: str = Query(..., description="Reason for flagging")
):
    """Flag an odds change for attention"""
    try:
        change_uuid = uuid.UUID(change_id)
        success = await get_db_manager().flag_odds_change(change_uuid, reason)
        if success:
            return {"message": "Odds change flagged successfully"}
        else:
            raise HTTPException(status_code=404, detail="Odds change not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid change ID format")
    except Exception as e:
        logger.error(f"Error flagging odds change: {e}")
        raise HTTPException(status_code=500, detail="Failed to flag odds change")

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    try:
        # Get total events
        total_events = await get_db_manager().fetch_one("SELECT COUNT(*) as count FROM events")
        
        # Get total odds records
        total_odds = await get_db_manager().fetch_one("SELECT COUNT(*) as count FROM odds")
        
        # Get recent changes count
        recent_changes = await get_db_manager().fetch_one(
            "SELECT COUNT(*) as count FROM odds_changes WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'"
        )
        
        # Get flagged changes count
        flagged_changes = await get_db_manager().fetch_one(
            "SELECT COUNT(*) as count FROM odds_changes WHERE is_flagged = true"
        )
        
        # Get last scrape time
        last_scrape = await get_db_manager().fetch_one(
            "SELECT MAX(scraped_at) as last_scrape FROM odds"
        )
        
        return {
            "total_events": total_events["count"] if total_events else 0,
            "total_odds": total_odds["count"] if total_odds else 0,
            "recent_changes_24h": recent_changes["count"] if recent_changes else 0,
            "flagged_changes": flagged_changes["count"] if flagged_changes else 0,
            "last_scrape_time": last_scrape["last_scrape"].isoformat() if last_scrape and last_scrape["last_scrape"] else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            # Echo back for now - could be used for client commands
            await manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Function to broadcast odds changes (called by scraper)
async def broadcast_odds_change(change_data: Dict[str, Any]):
    """Broadcast odds change to all connected WebSocket clients"""
    message = json.dumps({
        "type": "odds_change",
        "data": change_data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    await manager.broadcast(message)

# Function to broadcast new odds data (called by scraper)
async def broadcast_odds_update(odds_data: List[Dict[str, Any]]):
    """Broadcast odds update to all connected WebSocket clients"""
    message = json.dumps({
        "type": "odds_update",
        "data": odds_data,
        "count": len(odds_data),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    await manager.broadcast(message)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

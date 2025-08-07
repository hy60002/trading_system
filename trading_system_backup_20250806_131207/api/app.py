"""
FastAPI Web Dashboard
Web-based dashboard for monitoring and controlling the trading system
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Security, WebSocket, WebSocketDisconnect, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..database.db_manager import EnhancedDatabaseManager
    from ..engine.advanced_trading_engine import AdvancedTradingEngine
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from engine.advanced_trading_engine import AdvancedTradingEngine


# FastAPI Application Setup
app = FastAPI(title="Bitget Trading System v3.0")

# Dashboard files mounting
dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")
if os.path.exists(dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=dashboard_dir), name="dashboard")
else:
    print(f"Warning: Dashboard directory not found at {dashboard_dir}")

# Static files mounting
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    print(f"Warning: Static directory not found at {static_dir}")

# Templates setup
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_dir)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Global trading engine instance
trading_engine: Optional[AdvancedTradingEngine] = None


# API Models
class TradeRequest(BaseModel):
    symbol: str
    side: str
    amount: float
    price: Optional[float] = None


class ConfigUpdate(BaseModel):
    config_data: Dict[str, Any]


# Authentication
async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify API token"""
    import secrets
    expected_token = os.getenv('API_TOKEN')
    if not expected_token:
        expected_token = secrets.token_urlsafe(32)
        logging.warning("No API_TOKEN set in environment. Generated secure token for this session.")
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Bitget Trading System v3.0", "status": "running"}

@app.get("/dashboard/")
async def dashboard_root():
    """Dashboard root redirect"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard/index.html")

@app.get("/dashboard")
async def dashboard_redirect():
    """Dashboard redirect"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard/index.html")

# Capital Tracking API Endpoints
@app.get("/api/capital/status")
async def get_capital_status():
    """Get capital tracking status"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        if hasattr(trading_engine, 'capital_tracker'):
            status = trading_engine.capital_tracker.get_current_status()
            return status
        else:
            # Fallback calculation
            balance = trading_engine.db.get_latest_balance()
            positions = trading_engine.db.get_open_positions()
            
            used_capital = sum(pos.get('quantity', 0) * pos.get('entry_price', 0) for pos in positions)
            total_balance = balance.get('total_balance', 10000)
            allocation_percentage = used_capital / total_balance if total_balance > 0 else 0
            
            return {
                'total_balance': total_balance,
                'used_capital': used_capital,
                'allocation_percentage': allocation_percentage,
                'within_limit': allocation_percentage <= 0.33,
                'available_capital': total_balance * 0.33 - used_capital,
                'position_count': len(positions),
                'tracking_enabled': False
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/capital/positions")
async def get_detailed_positions():
    """Get detailed position information"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        if hasattr(trading_engine, 'capital_tracker'):
            return trading_engine.capital_tracker.get_detailed_positions()
        else:
            # Fallback
            positions = trading_engine.db.get_open_positions()
            return [
                {
                    'symbol': pos.get('symbol', ''),
                    'quantity': pos.get('quantity', 0),
                    'entry_price': pos.get('entry_price', 0),
                    'market_value': abs(pos.get('quantity', 0) * pos.get('entry_price', 0)),
                    'side': pos.get('side', 'long'),
                    'leverage': pos.get('leverage', 1),
                    'unrealized_pnl': 0,
                    'allocation_percentage': 0
                }
                for pos in positions
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/capital/update")
async def force_capital_update():
    """Force capital tracking update"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        if hasattr(trading_engine, 'capital_tracker'):
            snapshot = await trading_engine.capital_tracker.force_update()
            return {'success': True, 'snapshot': snapshot}
        else:
            return {'success': False, 'message': 'Capital tracker not available'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notifications/test")
async def test_notifications():
    """Test notification system"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        if hasattr(trading_engine, 'notification_manager'):
            success = await trading_engine.notification_manager.test_notification_system()
            return {'success': success}
        else:
            return {'success': False, 'message': 'Notification manager not available'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Dashboard Routes
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the main dashboard page"""
    dashboard_path = os.path.join(dashboard_dir, "index.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Dashboard Not Found</title></head>
        <body>
            <h1>Dashboard files not found</h1>
            <p>Please ensure the dashboard directory exists at: {}</p>
        </body>
        </html>
        """.format(dashboard_dir))

@app.get("/api/dashboard")
async def get_dashboard_data():
    """Get comprehensive dashboard data"""
    if trading_engine is None:
        return {"status": "not_initialized"}
    
    try:
        # Get system status first
        system_status = trading_engine.get_system_status()
        
        # Mock data for demonstration (replace with real data when methods are available)
        balance_info = {
            "total": {"USDT": 6170.85},
            "free": {"USDT": 4864.38},
            "used": {"USDT": 1306.47},
            "info": [{"unrealizedPL": "-11.78"}]
        }
        
        positions = []  # Empty positions for now
        
        performance = {
            "total_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "total_fees": 0,
            "btc_pnl": 0,
            "eth_pnl": 0,
            "xrp_pnl": 0
        }
        
        recent_trades = []  # Empty trades for now
        
        return {
            "balance": balance_info,
            "positions": positions,
            "performance": performance,
            "recent_trades": recent_trades,
            "system_status": system_status
        }
    except Exception as e:
        logging.error(f"Dashboard data error: {e}")
        return {"error": str(e)}

@app.get("/status")
async def get_system_status():
    """Get comprehensive system status"""
    if trading_engine is None:
        return {"status": "not_initialized"}
    
    # Get comprehensive system status from AdvancedTradingEngine
    return trading_engine.get_system_status()


@app.get("/positions")
async def get_positions():
    """Get current positions"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    positions = trading_engine.db.get_open_positions()
    return {"positions": positions}


@app.get("/performance")
async def get_performance(days: int = 7):
    """Get comprehensive performance metrics"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        # Get performance data
        daily_perf = trading_engine.db.get_daily_performance()
        
        # Get historical performance if available
        history = []
        today_pnl = daily_perf.get('total_pnl_percent', 0.0)
        
        # Calculate portfolio allocation
        positions = trading_engine.db.get_open_positions()
        portfolio_allocation = {}
        
        for pos in positions:
            symbol = pos['symbol']
            base_symbol = symbol.replace('USDT', '')
            if base_symbol not in portfolio_allocation:
                portfolio_allocation[base_symbol] = 0
            portfolio_allocation[base_symbol] += abs(pos.get('quantity', 0) * pos.get('entry_price', 0))
        
        return {
            "daily_pnl_percent": daily_perf.get('total_pnl_percent', 0.0),
            "win_rate": daily_perf.get('win_rate', 0.0),
            "total_trades": daily_perf.get('total_trades', 0),
            "kelly_fraction": daily_perf.get('kelly_fraction', 0.0),
            "today_pnl": today_pnl,
            "history": history,  # Could be expanded with historical data
            "portfolio_allocation": portfolio_allocation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Position Management API Endpoints
@app.post("/api/positions/{position_id}/close")
async def close_position(position_id: str):
    """Close a specific position"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        # Close position through trading engine
        result = await trading_engine.position_manager.close_position(position_id)
        return {"success": True, "result": result}
    except Exception as e:
        logging.error(f"Position close error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/positions/{position_id}/stop-loss")
async def update_stop_loss(position_id: str, data: dict):
    """Update stop loss for a position"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        stop_loss = data.get('stop_loss')
        result = await trading_engine.position_manager.update_stop_loss(position_id, stop_loss)
        return {"success": True, "result": result}
    except Exception as e:
        logging.error(f"Stop loss update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/positions/{position_id}/partial-close")
async def partial_close_position(position_id: str, data: dict):
    """Partially close a position"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        percentage = data.get('percentage', 50)
        result = await trading_engine.position_manager.partial_close(position_id, percentage)
        return {"success": True, "result": result}
    except Exception as e:
        logging.error(f"Partial close error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/positions/{position_id}/update")
async def update_position(position_id: str, data: dict):
    """Update position parameters"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        result = await trading_engine.position_manager.update_position(position_id, data)
        return {"success": True, "result": result}
    except Exception as e:
        logging.error(f"Position update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trades")
async def get_recent_trades(limit: int = 50):
    """Get recent trades"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    # Get recent trades from database
    with trading_engine.db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        trades = [dict(row) for row in cursor.fetchall()]
    
    return {"trades": trades}


@app.post("/trade")
async def manual_trade(trade_request: TradeRequest, credentials: HTTPAuthorizationCredentials = Security(verify_token)):
    """Execute manual trade"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        # Execute manual trade
        result = await trading_engine.exchange.place_order(
            symbol=trade_request.symbol,
            side=trade_request.side,
            amount=trade_request.amount,
            price=trade_request.price
        )
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/start")
async def start_trading(credentials: HTTPAuthorizationCredentials = Security(verify_token)):
    """Start trading system"""
    global trading_engine
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    if not trading_engine.is_running:
        trading_engine.is_running = True
        return {"message": "Trading system started"}
    else:
        return {"message": "Trading system already running"}


@app.post("/stop")
async def stop_trading(credentials: HTTPAuthorizationCredentials = Security(verify_token)):
    """Stop trading system"""
    global trading_engine
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    if trading_engine.is_running:
        trading_engine.is_running = False
        return {"message": "Trading system stopped"}
    else:
        return {"message": "Trading system already stopped"}


# 텔레그램 알림 관련 엔드포인트
@app.get("/api/telegram/notifications")
async def get_telegram_notifications():
    """텔레그램 알림 목록 조회"""
    try:
        if trading_engine is None:
            raise HTTPException(status_code=503, detail="Trading engine not initialized")
        
        # 알림 통계 가져오기
        notification_stats = trading_engine.notifier.verification_stats
        
        # 최근 알림 생성 (실제로는 데이터베이스에서 조회)
        notifications = [
            {
                "id": "1",
                "type": "trade",
                "message": "🟢 BTCUSDT 롱 포지션 진입 - $50,000에 0.1 BTC",
                "details": {
                    "symbol": "BTCUSDT",
                    "action": "open_long",
                    "price": 50000,
                    "quantity": 0.1
                },
                "priority": "high",
                "timestamp": "2025-01-01T12:30:00Z",
                "delivery_status": "success"
            },
            {
                "id": "2", 
                "type": "daily_report",
                "message": "📊 일일 거래 성과 보고서\n오늘 수익률: +2.5%",
                "details": {
                    "daily_pnl": 2.5,
                    "trades_count": 5,
                    "win_rate": 80
                },
                "priority": "normal",
                "timestamp": "2025-01-01T09:00:00Z",
                "delivery_status": "success"
            }
        ]
        
        return {
            "success": True,
            "notifications": notifications,
            "stats": {
                "total_sent": notification_stats['total_notifications_sent'],
                "success_rate": (
                    notification_stats['successful_deliveries'] / 
                    max(notification_stats['total_notifications_sent'], 1) * 100
                ),
                "last_delivery": notification_stats['last_successful_delivery']
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch notifications: {str(e)}")


@app.websocket("/ws/telegram-notifications")
async def telegram_notifications_websocket(websocket: WebSocket):
    """텔레그램 알림 실시간 WebSocket"""
    await websocket.accept()
    
    try:
        if trading_engine is None:
            await websocket.send_json({"error": "Trading engine not initialized"})
            return
            
        # 알림 시스템 상태 전송
        await websocket.send_json({
            "type": "connection_status",
            "status": "connected",
            "message": "텔레그램 알림 스트림 연결됨"
        })
        
        # 실제 구현에서는 NotificationManager의 이벤트를 구독하여
        # 새로운 알림이 발생할 때마다 클라이언트에게 전송
        while True:
            await asyncio.sleep(30)  # 30초마다 연결 상태 확인
            
            # 연결 상태 체크 메시지
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": asyncio.get_event_loop().time()
            })
            
    except WebSocketDisconnect:
        print("텔레그램 알림 WebSocket 연결 종료")
    except Exception as e:
        print(f"텔레그램 알림 WebSocket 오류: {e}")
        await websocket.close()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    
    if trading_engine is None:
        await websocket.send_json({"error": "Trading engine not initialized"})
        await websocket.close()
        return
    
    try:
        while True:
            # Send system status every 5 seconds
            status = {
                "status": "running" if trading_engine.is_running else "stopped",
                "positions": len(trading_engine.db.get_open_positions()),
                "balance": 0,  # Would need to fetch from exchange
                "websocket_connected": trading_engine.exchange.ws_connected
            }
            await websocket.send_json(status)
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")


@app.get("/balance")
async def get_balance():
    """Get account balance and allocation"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        balance = await trading_engine.exchange.get_balance()
        positions = trading_engine.db.get_open_positions()
        
        # Calculate used balance
        used_balance = sum(
            pos.get('quantity', 0) * pos.get('entry_price', 0)
            for pos in positions
        )
        
        total_balance = balance.get('USDT', {}).get('free', 0) + used_balance
        
        return {
            "free_balance": balance.get('USDT', {}).get('free', 0),
            "used_balance": used_balance,
            "total_balance": total_balance,
            "open_positions": len(positions),
            "allocation_percent": (used_balance / total_balance * 100) if total_balance > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard")
async def get_dashboard():
    """Get dashboard data"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    try:
        # Get comprehensive dashboard data
        balance = await trading_engine.exchange.get_balance()
        positions = trading_engine.db.get_open_positions()
        performance = trading_engine.db.get_daily_performance()
        
        # Get recent trades
        with trading_engine.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10"
            )
            recent_trades = [dict(row) for row in cursor.fetchall()]
        
        return {
            "balance": balance,
            "positions": positions,
            "performance": performance,
            "recent_trades": recent_trades,
            "system_status": {
                "running": trading_engine.is_running,
                "websocket_connected": trading_engine.exchange.ws_connected,
                "symbols": trading_engine.config.SYMBOLS
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ml-status")
async def get_ml_status():
    """Get ML model status and performance"""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    
    if not trading_engine.config.ENABLE_ML_MODELS:
        return {"ml_enabled": False, "message": "ML models disabled"}
    
    try:
        model_performances = {}
        for model_name in ['random_forest', 'gradient_boost', 'neural_network', 'xgboost']:
            perf = trading_engine.db.get_ml_model_performance(model_name)
            if perf:
                model_performances[model_name] = perf
        
        return {
            "ml_enabled": True,
            "models": model_performances,
            "overall_health": trading_engine._calculate_ml_health()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notifications")
async def get_notifications():
    """Get recent notifications/reports"""
    if not trading_engine:
        raise HTTPException(status_code=503, detail="Trading engine not available")
    
    try:
        import time
        import json
        from datetime import datetime
        
        # Get recent notifications from notification manager
        notifications = []
        if hasattr(trading_engine, 'notifier') and trading_engine.notifier:
            # Get recent messages from queue
            recent_messages = list(trading_engine.notifier.message_queue)
            for msg in recent_messages[-20:]:  # Last 20 messages
                notifications.append({
                    'timestamp': msg.get('timestamp', time.time()),
                    'content': msg.get('content', ''),
                    'channel': msg.get('channel', 'telegram'),
                    'metadata': msg.get('metadata', {}),
                    'formatted_time': datetime.fromtimestamp(msg.get('timestamp', time.time())).strftime('%H:%M:%S')
                })
        
        # Get system logs from database
        system_logs = []
        if hasattr(trading_engine, 'db') and trading_engine.db:
            try:
                with trading_engine.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT timestamp, component, message, level, metadata 
                        FROM system_logs 
                        ORDER BY timestamp DESC 
                        LIMIT 50
                    """)
                    for row in cursor.fetchall():
                        system_logs.append({
                            'timestamp': row['timestamp'],
                            'component': row['component'],
                            'message': row['message'],
                            'level': row['level'],
                            'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                            'formatted_time': row['timestamp'][:19] if row['timestamp'] else ''
                        })
            except Exception as e:
                logging.error(f"System logs retrieval error: {e}")
        
        return {
            "notifications": notifications,
            "system_logs": system_logs,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Get notifications error: {e}")
        return {"notifications": [], "system_logs": [], "error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def dashboard_page():
    """Serve dashboard HTML page"""
    html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    else:
        return HTMLResponse("""
        <html>
            <head><title>Trading System v3.0</title></head>
            <body>
                <h1>Trading System v3.0 - Dashboard</h1>
                <p>Dashboard HTML not found. API endpoints are available.</p>
                <ul>
                    <li><a href="/status">System Status</a></li>
                    <li><a href="/positions">Positions</a></li>
                    <li><a href="/performance">Performance</a></li>
                    <li><a href="/balance">Balance</a></li>
                    <li><a href="/ml-status">ML Status</a></li>
                    <li><a href="/dashboard">Dashboard Data</a></li>
                </ul>
            </body>
        </html>
        """)


def set_trading_engine(engine: AdvancedTradingEngine):
    """Set the trading engine instance"""
    global trading_engine
    trading_engine = engine


def get_app():
    """Get the FastAPI app instance"""
    return app
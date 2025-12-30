"""
Real-Time API Server for Convergence Strategy
==============================================
FastAPI + WebSocket server that streams live signals from the coordinator.

Endpoints:
- GET /health - Health check
- GET /analyze/{asset} - One-time analysis
- WS /ws/signals - Real-time signal streaming
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import our existing coordinator
from agents.coordinator import AgentCoordinator


class ConnectionManager:
    """Manages WebSocket connections for broadcasting signals"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, assets: List[str] = None):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set(assets) if assets else {"BTC"}
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict, asset: str = None):
        """Send message to all connected clients (or those subscribed to asset)"""
        disconnected = set()

        for connection in self.active_connections:
            try:
                # Check if client is subscribed to this asset
                if asset and asset not in self.subscriptions.get(connection, set()):
                    continue
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global instances
manager = ConnectionManager()
coordinator = AgentCoordinator()

# Background task reference
signal_task = None


async def signal_streaming_loop():
    """Background task that continuously analyzes and broadcasts signals"""
    assets = ["BTC", "ETH"]  # Assets to monitor
    current_asset_idx = 0

    # Store historical data for charts
    history = {
        "entropy": [],
        "k_factor": [],
        "cvd": [],
        "timestamps": []
    }
    max_history = 60  # Keep 60 data points

    while True:
        try:
            # Rotate through assets
            asset = assets[current_asset_idx]
            current_asset_idx = (current_asset_idx + 1) % len(assets)

            # Run analysis (this calls all agents)
            print(f"\n[Signal Loop] Analyzing {asset}...")
            analysis = coordinator.analyze(asset)

            # Extract convergence signals
            convergence = analysis.convergence

            # Build signal payload
            timestamp = datetime.now().isoformat()

            signal_data = {
                "type": "signal_update",
                "timestamp": timestamp,
                "asset": asset,

                # Convergence status
                "convergence": {
                    "entry_signal": convergence.entry_signal if convergence else False,
                    "exit_signal": convergence.exit_signal if convergence else False,
                    "signal_strength": convergence.signal_strength if convergence else 0,
                },

                # Bio-Check (Viral K-Factor)
                "bio": {
                    "k_factor": analysis.agent_opinions.get('social', {}).indicators.get('viral_k_factor', 1.0) if hasattr(analysis.agent_opinions.get('social', {}), 'indicators') else 1.0,
                    "acceleration": analysis.agent_opinions.get('social', {}).indicators.get('viral_acceleration', 0) if hasattr(analysis.agent_opinions.get('social', {}), 'indicators') else 0,
                    "signal": analysis.agent_opinions.get('social', {}).indicators.get('viral_signal', 'STABLE') if hasattr(analysis.agent_opinions.get('social', {}), 'indicators') else 'STABLE',
                    "passed": convergence.bio_check_passed if convergence else False,
                },

                # Physics-Check (Entropy + Hurst)
                "physics": {
                    "entropy": analysis.agent_opinions.get('technical', {}).indicators.get('shannon_entropy', 0.5) if hasattr(analysis.agent_opinions.get('technical', {}), 'indicators') else 0.5,
                    "entropy_signal": analysis.agent_opinions.get('technical', {}).indicators.get('entropy_signal', 'TRANSITIONAL') if hasattr(analysis.agent_opinions.get('technical', {}), 'indicators') else 'TRANSITIONAL',
                    "hurst": analysis.agent_opinions.get('technical', {}).indicators.get('hurst_exponent', 0.5) if hasattr(analysis.agent_opinions.get('technical', {}), 'indicators') else 0.5,
                    "hurst_signal": analysis.agent_opinions.get('technical', {}).indicators.get('hurst_signal', 'RANDOM') if hasattr(analysis.agent_opinions.get('technical', {}), 'indicators') else 'RANDOM',
                    "market_regime": analysis.agent_opinions.get('technical', {}).indicators.get('market_regime', 'CAUTION') if hasattr(analysis.agent_opinions.get('technical', {}), 'indicators') else 'CAUTION',
                    "passed": convergence.physics_check_passed if convergence else False,
                },

                # Micro-Check (CVD Divergence)
                "micro": {
                    "cvd_value": analysis.agent_opinions.get('risk', {}).indicators.get('cvd_value', 0) if hasattr(analysis.agent_opinions.get('risk', {}), 'indicators') else 0,
                    "cvd_trend": analysis.agent_opinions.get('risk', {}).indicators.get('cvd_trend', 'NEUTRAL') if hasattr(analysis.agent_opinions.get('risk', {}), 'indicators') else 'NEUTRAL',
                    "whale_trap": analysis.agent_opinions.get('risk', {}).indicators.get('whale_trap_detected', False) if hasattr(analysis.agent_opinions.get('risk', {}), 'indicators') else False,
                    "distribution": analysis.agent_opinions.get('risk', {}).indicators.get('distribution_detected', False) if hasattr(analysis.agent_opinions.get('risk', {}), 'indicators') else False,
                    "passed": convergence.micro_check_passed if convergence else False,
                },

                # Overall recommendation
                "recommendation": {
                    "action": analysis.action.value,
                    "confidence": analysis.confidence.name,
                    "consensus": analysis.consensus_level,
                },

                # Exit conditions
                "circuit_breakers": {
                    "entropy_breaker": convergence.entropy_circuit_breaker if convergence else False,
                    "viral_death": convergence.viral_death if convergence else False,
                    "distribution_exit": convergence.distribution_exit if convergence else False,
                },

                # Reasons
                "entry_reasons": convergence.entry_reasons if convergence else [],
                "exit_reasons": convergence.exit_reasons if convergence else [],
            }

            # Update history for charts
            history["timestamps"].append(timestamp)
            history["entropy"].append(signal_data["physics"]["entropy"])
            history["k_factor"].append(signal_data["bio"]["k_factor"])
            history["cvd"].append(signal_data["micro"]["cvd_value"])

            # Trim history
            if len(history["timestamps"]) > max_history:
                for key in history:
                    history[key] = history[key][-max_history:]

            # Add history to payload
            signal_data["history"] = history

            # Broadcast to all connected clients
            await manager.broadcast(signal_data, asset)

            # Also broadcast to clients subscribed to "ALL"
            await manager.broadcast(signal_data, "ALL")

        except Exception as e:
            print(f"[Signal Loop] Error: {e}")
            error_msg = {
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            await manager.broadcast(error_msg)

        # Wait before next update (adjustable frequency)
        await asyncio.sleep(5)  # 5 seconds between updates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global signal_task

    # Start background signal streaming
    print("[API] Starting signal streaming loop...")
    signal_task = asyncio.create_task(signal_streaming_loop())

    yield

    # Shutdown
    print("[API] Shutting down signal streaming...")
    if signal_task:
        signal_task.cancel()
        try:
            await signal_task
        except asyncio.CancelledError:
            pass


# Create FastAPI app
app = FastAPI(
    title="ShopGuard Convergence API",
    description="Real-time trading signals using Bio/Physics/Micro convergence strategy",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === REST Endpoints ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "connections": len(manager.active_connections)
    }


@app.get("/analyze/{asset}")
async def analyze_asset(asset: str):
    """
    One-time analysis for a specific asset

    Args:
        asset: Asset symbol (BTC, ETH, SPY, etc.)
    """
    asset = asset.upper()

    if asset not in ["BTC", "ETH", "SPY", "QQQ", "NVDA"]:
        raise HTTPException(status_code=400, detail=f"Unsupported asset: {asset}")

    try:
        analysis = coordinator.analyze(asset)
        return analysis.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/convergence/{asset}")
async def get_convergence(asset: str):
    """
    Get just the convergence signal for an asset
    """
    asset = asset.upper()

    try:
        analysis = coordinator.analyze(asset)
        convergence = analysis.convergence

        if not convergence:
            return {"error": "No convergence data available"}

        return {
            "asset": asset,
            "timestamp": datetime.now().isoformat(),
            "entry_signal": convergence.entry_signal,
            "exit_signal": convergence.exit_signal,
            "signal_strength": convergence.signal_strength,
            "checks": {
                "bio": convergence.bio_check_passed,
                "physics": convergence.physics_check_passed,
                "micro": convergence.micro_check_passed,
            },
            "circuit_breakers": {
                "entropy": convergence.entropy_circuit_breaker,
                "viral_death": convergence.viral_death,
                "distribution": convergence.distribution_exit,
            },
            "entry_reasons": convergence.entry_reasons,
            "exit_reasons": convergence.exit_reasons,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === WebSocket Endpoint ===

@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """
    WebSocket endpoint for real-time signal streaming

    Query params:
        assets: Comma-separated list of assets to subscribe to (default: BTC)

    Example: ws://localhost:8001/ws/signals?assets=BTC,ETH
    """
    # Parse query params
    query_params = dict(websocket.query_params)
    assets_param = query_params.get("assets", "BTC")
    assets = [a.strip().upper() for a in assets_param.split(",")]

    await manager.connect(websocket, assets)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "message": f"Subscribed to signals for: {', '.join(assets)}",
            "timestamp": datetime.now().isoformat()
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any client messages (ping/pong, subscription changes)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)

                # Handle subscription updates
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "subscribe":
                        new_assets = msg.get("assets", [])
                        manager.subscriptions[websocket] = set(new_assets)
                        await websocket.send_json({
                            "type": "subscribed",
                            "assets": new_assets
                        })
                    elif msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS] Error: {e}")
        manager.disconnect(websocket)


# === Run Server ===

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("ShopGuard Convergence API Server")
    print("=" * 60)
    print("Endpoints:")
    print("  - GET  /health           - Health check")
    print("  - GET  /analyze/{asset}  - Full analysis")
    print("  - GET  /convergence/{asset} - Convergence signal only")
    print("  - WS   /ws/signals       - Real-time streaming")
    print("=" * 60)

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )

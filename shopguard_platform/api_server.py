"""
Real-Time API Server for Convergence Strategy
==============================================
FastAPI + WebSocket server that streams live signals from the coordinator.

Endpoints:
- GET /health - Health check
- GET /analyze/{asset} - One-time analysis
- GET /convergence/{asset} - Convergence signal only
- GET /status - System status including circuit breakers
- WS /ws/signals - Real-time signal streaming

Production Features:
- Pydantic models for type safety
- Professional logging
- Circuit breaker status exposure
- Matrix simulation mode (no API keys required)
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import os

# Import our existing coordinator
from agents.coordinator import AgentCoordinator

# Import Matrix simulation engine
try:
    from src.simulation.matrix import Matrix
    MATRIX_AVAILABLE = True
except ImportError:
    MATRIX_AVAILABLE = False

# Import logging
try:
    from utils.logging_config import api_logger, get_logger
    logger = get_logger("shopguard.api")
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    api_logger = None


# ============================================================================
# SIMULATION MODE - Set to True to use Matrix synthetic data
# ============================================================================
SIMULATION_MODE = True  # Set to False to use real API data


# ============================================================================
# PYDANTIC MODELS - Type-safe API responses
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service health status")
    timestamp: str = Field(..., description="ISO timestamp")
    connections: int = Field(..., description="Active WebSocket connections")


class BioCheck(BaseModel):
    """Bio-Check (Viral K-Factor) data"""
    k_factor: float = Field(1.0, description="Viral K-Factor (growth rate)")
    acceleration: float = Field(0.0, description="K-Factor acceleration")
    signal: str = Field("STABLE", description="Viral signal: EXPLOSIVE, GROWING, STABLE, DECLINING")
    passed: bool = Field(False, description="Whether bio check passed")


class PhysicsCheck(BaseModel):
    """Physics-Check (Entropy + Hurst) data"""
    entropy: float = Field(0.5, description="Shannon entropy (0-1)")
    entropy_signal: str = Field("TRANSITIONAL", description="Entropy signal")
    hurst: float = Field(0.5, description="Hurst exponent (0-1)")
    hurst_signal: str = Field("RANDOM", description="Hurst signal")
    market_regime: str = Field("CAUTION", description="Market regime classification")
    passed: bool = Field(False, description="Whether physics check passed")


class MicroCheck(BaseModel):
    """Micro-Check (CVD Divergence) data"""
    cvd_value: float = Field(0.0, description="Cumulative Volume Delta")
    cvd_trend: str = Field("NEUTRAL", description="CVD trend direction")
    whale_trap: bool = Field(False, description="Whale trap detected")
    distribution: bool = Field(False, description="Distribution detected")
    passed: bool = Field(False, description="Whether micro check passed")


class ConvergenceStatus(BaseModel):
    """Convergence signal status"""
    entry_signal: bool = Field(False, description="Entry signal active")
    exit_signal: bool = Field(False, description="Exit signal active")
    signal_strength: float = Field(0.0, description="Signal strength (0-3)")


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status"""
    entropy_breaker: bool = Field(False, description="Entropy circuit breaker triggered")
    viral_death: bool = Field(False, description="Viral death detected")
    distribution_exit: bool = Field(False, description="Distribution exit triggered")


class RecommendationResponse(BaseModel):
    """Trading recommendation"""
    action: str = Field(..., description="Recommended action: STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL")
    confidence: str = Field(..., description="Confidence level: HIGH, MEDIUM, LOW")
    consensus: float = Field(..., description="Agent consensus level (0-1)")


class ConvergenceResponse(BaseModel):
    """Full convergence analysis response"""
    asset: str = Field(..., description="Asset symbol")
    timestamp: str = Field(..., description="ISO timestamp")
    entry_signal: bool = Field(False)
    exit_signal: bool = Field(False)
    signal_strength: float = Field(0.0)
    checks: Dict[str, bool] = Field(default_factory=dict)
    circuit_breakers: Dict[str, bool] = Field(default_factory=dict)
    entry_reasons: List[str] = Field(default_factory=list)
    exit_reasons: List[str] = Field(default_factory=list)


class SignalUpdate(BaseModel):
    """Real-time signal update (WebSocket payload)"""
    type: str = Field("signal_update")
    timestamp: str
    asset: str
    convergence: ConvergenceStatus
    bio: BioCheck
    physics: PhysicsCheck
    micro: MicroCheck
    recommendation: RecommendationResponse
    circuit_breakers: CircuitBreakerStatus
    entry_reasons: List[str] = Field(default_factory=list)
    exit_reasons: List[str] = Field(default_factory=list)
    history: Optional[Dict[str, List]] = None


class SystemStatus(BaseModel):
    """Overall system status"""
    status: str = Field("healthy")
    timestamp: str
    websocket_connections: int = Field(0)
    reddit_circuit: Dict[str, Any] = Field(default_factory=dict)
    last_analysis: Optional[str] = None
    simulation_mode: bool = Field(False, description="Whether Matrix simulation is active")
    market_phase: Optional[str] = Field(None, description="Current simulated market phase")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: str


# ============================================================================
# SUPPORTED ASSETS
# ============================================================================

SUPPORTED_ASSETS = {"BTC", "ETH", "SPY", "QQQ", "NVDA"}


class ConnectionManager:
    """Manages WebSocket connections for broadcasting signals"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, assets: List[str] = None):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set(assets) if assets else {"BTC"}
        if api_logger:
            api_logger.websocket_connect(len(self.active_connections), assets)
        else:
            logger.info(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        if api_logger:
            api_logger.websocket_disconnect(len(self.active_connections))
        else:
            logger.info(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

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

# Matrix simulation engine
matrix: Optional[Matrix] = None
if SIMULATION_MODE and MATRIX_AVAILABLE:
    matrix = Matrix(
        crash_interval=60,  # Perfect Storm every 60 seconds
        tick_interval=2.0   # 2 seconds between ticks
    )
    logger.info("🔮 Matrix simulation engine initialized")

# Background task reference
signal_task = None

# Track last analysis time for status endpoint
last_analysis_time: Optional[str] = None

# Track current market phase for status
current_market_phase: str = "stable"


def _build_signal_from_matrix(tick: Dict[str, Any], history: Dict[str, List]) -> Dict[str, Any]:
    """Transform Matrix tick data into signal format for WebSocket."""
    conv = tick.get("convergence", {})

    # Determine action based on convergence
    if conv.get("entry_signal"):
        action = "STRONG_BUY"
        confidence = "VERY_HIGH"
    elif conv.get("exit_signal"):
        action = "SELL"
        confidence = "HIGH"
    elif conv.get("signal_strength", 0) >= 0.66:
        action = "BUY"
        confidence = "MEDIUM"
    else:
        action = "HOLD"
        confidence = "LOW"

    # Build entry/exit reasons
    entry_reasons = []
    exit_reasons = []

    if conv.get("bio_passed"):
        entry_reasons.append(f"✅ Bio-Check PASSED: Viral K={tick.get('viral_k_factor', 1.0):.2f}")
    else:
        entry_reasons.append(f"❌ Bio-Check FAILED: Viral K={tick.get('viral_k_factor', 1.0):.2f} (need >1.2)")

    if conv.get("physics_passed"):
        entry_reasons.append(f"✅ Physics-Check PASSED: Entropy={tick.get('entropy', 0.5):.2f}, Hurst={tick.get('hurst', 0.5):.2f}")
    else:
        entry_reasons.append(f"❌ Physics-Check FAILED: Entropy={tick.get('entropy', 0.5):.2f} (need <0.6)")

    if conv.get("micro_passed"):
        entry_reasons.append("✅ Micro-Check PASSED: Whale absorption detected")
    else:
        entry_reasons.append(f"❌ Micro-Check FAILED: CVD {tick.get('cvd_trend', 'NEUTRAL')}")

    # Exit reasons
    if tick.get("entropy", 0.5) > 0.9:
        exit_reasons.append(f"🔴 CIRCUIT BREAKER: Entropy at {tick.get('entropy', 0.5):.2f}")
    if tick.get("viral_k_factor", 1.0) < 0.8:
        exit_reasons.append(f"🔴 VIRAL DEATH: K-Factor at {tick.get('viral_k_factor', 1.0):.2f}")
    if tick.get("distribution_detected"):
        exit_reasons.append("🔴 DISTRIBUTION: Smart money selling")

    return {
        "type": "signal_update",
        "timestamp": tick.get("timestamp", datetime.now().isoformat()),
        "asset": tick.get("asset", "BTC"),
        "source": "matrix",
        "market_phase": tick.get("market_phase", "stable"),

        # Convergence status
        "convergence": {
            "entry_signal": conv.get("entry_signal", False),
            "exit_signal": conv.get("exit_signal", False),
            "signal_strength": conv.get("signal_strength", 0) * 3,  # Scale to 0-3
        },

        # Bio-Check (Viral K-Factor)
        "bio": {
            "k_factor": tick.get("viral_k_factor", 1.0),
            "acceleration": tick.get("viral_acceleration", 0),
            "signal": tick.get("viral_signal", "STABLE"),
            "passed": conv.get("bio_passed", False),
        },

        # Physics-Check (Entropy + Hurst)
        "physics": {
            "entropy": tick.get("entropy", 0.5),
            "entropy_signal": tick.get("entropy_signal", "TRANSITIONAL"),
            "hurst": tick.get("hurst", 0.5),
            "hurst_signal": tick.get("hurst_signal", "NEUTRAL"),
            "market_regime": tick.get("market_regime", "CAUTION"),
            "passed": conv.get("physics_passed", False),
        },

        # Micro-Check (CVD Divergence)
        "micro": {
            "cvd_value": tick.get("cvd", 0),
            "cvd_trend": tick.get("cvd_trend", "NEUTRAL"),
            "whale_trap": tick.get("whale_trap_detected", False),
            "distribution": tick.get("distribution_detected", False),
            "passed": conv.get("micro_passed", False),
        },

        # Overall recommendation
        "recommendation": {
            "action": action,
            "confidence": confidence,
            "consensus": conv.get("signal_strength", 0.5),
        },

        # Exit conditions
        "circuit_breakers": {
            "entropy_breaker": tick.get("entropy", 0.5) > 0.9,
            "viral_death": tick.get("viral_k_factor", 1.0) < 0.8,
            "distribution_exit": tick.get("distribution_detected", False),
        },

        # Reasons
        "entry_reasons": entry_reasons,
        "exit_reasons": exit_reasons,

        # Price data
        "price": tick.get("price", 0),
        "change_24h": tick.get("change_24h", 0),

        # Historical data for charts
        "history": history,
    }


async def signal_streaming_loop():
    """
    Background task that continuously streams signals.

    In SIMULATION_MODE, uses Matrix to generate synthetic data.
    Otherwise, uses real coordinator analysis.
    """
    global last_analysis_time, current_market_phase

    assets = ["BTC", "ETH"]  # Assets to monitor
    current_asset_idx = 0

    # Store historical data for charts
    history: Dict[str, Dict[str, List]] = {
        "BTC": {"entropy": [], "k_factor": [], "cvd": [], "timestamps": [], "price": []},
        "ETH": {"entropy": [], "k_factor": [], "cvd": [], "timestamps": [], "price": []},
    }
    max_history = 60  # Keep 60 data points

    if SIMULATION_MODE and matrix:
        logger.info("🔮 Starting Matrix simulation loop...")

        while True:
            try:
                # Rotate through assets
                asset = assets[current_asset_idx]
                current_asset_idx = (current_asset_idx + 1) % len(assets)

                # Get tick from Matrix
                tick = matrix.tick(asset)

                # Update market phase
                current_market_phase = tick.get("market_phase", "stable")

                # Update history
                if asset not in history:
                    history[asset] = {"entropy": [], "k_factor": [], "cvd": [], "timestamps": [], "price": []}

                asset_history = history[asset]
                asset_history["timestamps"].append(tick.get("timestamp"))
                asset_history["entropy"].append(tick.get("entropy", 0.5))
                asset_history["k_factor"].append(tick.get("viral_k_factor", 1.0))
                asset_history["cvd"].append(tick.get("cvd", 0))
                asset_history["price"].append(tick.get("price", 0))

                # Trim history
                for key in asset_history:
                    if len(asset_history[key]) > max_history:
                        asset_history[key] = asset_history[key][-max_history:]

                # Build signal data
                signal_data = _build_signal_from_matrix(tick, asset_history)

                # Broadcast to all connected clients
                await manager.broadcast(signal_data, asset)
                await manager.broadcast(signal_data, "ALL")

                # Log signal update
                conv = tick.get("convergence", {})
                if conv.get("entry_signal"):
                    logger.info(f"🔥 [{asset}] ENTRY SIGNAL! Phase: {current_market_phase}")
                elif conv.get("exit_signal"):
                    logger.warning(f"🔴 [{asset}] EXIT SIGNAL! Phase: {current_market_phase}")

                if api_logger:
                    checks = sum([conv.get("bio_passed", False), conv.get("physics_passed", False), conv.get("micro_passed", False)])
                    api_logger.signal_update(asset, signal_data["recommendation"]["action"], checks)

                # Update last analysis time
                last_analysis_time = tick.get("timestamp")

            except Exception as e:
                logger.error(f"Matrix loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

            # Wait for next tick
            await asyncio.sleep(2)  # 2 seconds between updates

    else:
        # Original coordinator-based analysis
        logger.info("📊 Starting coordinator analysis loop (live mode)...")

        while True:
            try:
                # Rotate through assets
                asset = assets[current_asset_idx]
                current_asset_idx = (current_asset_idx + 1) % len(assets)

                # Run analysis (this calls all agents)
                logger.debug(f"Analyzing {asset}...")
                analysis = coordinator.analyze(asset)

                # Extract convergence signals
                convergence = analysis.convergence

                # Build signal payload
                timestamp = datetime.now().isoformat()

                signal_data = {
                    "type": "signal_update",
                    "timestamp": timestamp,
                    "asset": asset,
                    "source": "live",

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
                if asset not in history:
                    history[asset] = {"entropy": [], "k_factor": [], "cvd": [], "timestamps": [], "price": []}

                asset_history = history[asset]
                asset_history["timestamps"].append(timestamp)
                asset_history["entropy"].append(signal_data["physics"]["entropy"])
                asset_history["k_factor"].append(signal_data["bio"]["k_factor"])
                asset_history["cvd"].append(signal_data["micro"]["cvd_value"])

                # Trim history
                for key in asset_history:
                    if len(asset_history[key]) > max_history:
                        asset_history[key] = asset_history[key][-max_history:]

                # Add history to payload
                signal_data["history"] = asset_history

                # Broadcast to all connected clients
                await manager.broadcast(signal_data, asset)
                await manager.broadcast(signal_data, "ALL")

                # Log signal update
                if api_logger:
                    checks = sum([
                        signal_data["bio"]["passed"],
                        signal_data["physics"]["passed"],
                        signal_data["micro"]["passed"]
                    ])
                    api_logger.signal_update(asset, signal_data["recommendation"]["action"], checks)

                # Update last analysis time
                last_analysis_time = timestamp

            except Exception as e:
                logger.error(f"Signal loop error: {e}", exc_info=True)
                if api_logger:
                    api_logger.error("signal_loop", e, f"asset={asset}")
                error_msg = {
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                await manager.broadcast(error_msg)

            # Wait before next update
            await asyncio.sleep(5)  # 5 seconds between updates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global signal_task

    # Start background signal streaming
    mode = "MATRIX SIMULATION" if (SIMULATION_MODE and matrix) else "LIVE API"
    logger.info(f"Starting signal streaming loop ({mode})...")
    signal_task = asyncio.create_task(signal_streaming_loop())

    yield

    # Shutdown
    logger.info("Shutting down signal streaming...")
    if signal_task:
        signal_task.cancel()
        try:
            await signal_task
        except asyncio.CancelledError:
            pass
    logger.info("API server shutdown complete")


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

# Serve static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# === REST Endpoints ===

@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the standalone HTML dashboard"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Dashboard not found. Visit /docs for API documentation."}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        connections=len(manager.active_connections)
    )


@app.get("/status", response_model=SystemStatus)
async def system_status():
    """
    System status including circuit breaker states and simulation info.

    Useful for monitoring and debugging external API dependencies.
    """
    # Get Reddit circuit breaker status from social agent
    reddit_status = {}
    if not SIMULATION_MODE:
        try:
            from agents.social_agent import SocialAgent
            social = SocialAgent()
            reddit_status = social.get_circuit_status()
        except Exception as e:
            logger.warning(f"Could not get Reddit circuit status: {e}")
            reddit_status = {"state": "unknown", "error": str(e)}
    else:
        reddit_status = {"state": "bypassed", "reason": "simulation_mode"}

    return SystemStatus(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        websocket_connections=len(manager.active_connections),
        reddit_circuit=reddit_status,
        last_analysis=last_analysis_time if 'last_analysis_time' in globals() else None,
        simulation_mode=SIMULATION_MODE and matrix is not None,
        market_phase=current_market_phase if SIMULATION_MODE else None
    )


@app.get("/analyze/{asset}")
async def analyze_asset(asset: str):
    """
    One-time analysis for a specific asset

    Args:
        asset: Asset symbol (BTC, ETH, SPY, etc.)
    """
    asset = asset.upper()

    if asset not in SUPPORTED_ASSETS:
        logger.warning(f"Unsupported asset requested: {asset}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported asset: {asset}. Supported: {', '.join(SUPPORTED_ASSETS)}"
        )

    try:
        logger.info(f"Analyzing asset: {asset}")
        analysis = coordinator.analyze(asset)
        return analysis.to_dict()
    except Exception as e:
        logger.error(f"Analysis failed for {asset}: {e}", exc_info=True)
        if api_logger:
            api_logger.error("analyze_asset", e, f"asset={asset}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/convergence/{asset}", response_model=ConvergenceResponse)
async def get_convergence(asset: str):
    """
    Get just the convergence signal for an asset.

    Returns the three-pillar convergence analysis:
    - Bio: Viral K-Factor
    - Physics: Entropy + Hurst
    - Micro: CVD Divergence
    """
    asset = asset.upper()

    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported asset: {asset}. Supported: {', '.join(SUPPORTED_ASSETS)}"
        )

    try:
        logger.debug(f"Getting convergence for: {asset}")
        analysis = coordinator.analyze(asset)
        convergence = analysis.convergence

        if not convergence:
            logger.warning(f"No convergence data for {asset}")
            raise HTTPException(status_code=404, detail="No convergence data available")

        return ConvergenceResponse(
            asset=asset,
            timestamp=datetime.now().isoformat(),
            entry_signal=convergence.entry_signal,
            exit_signal=convergence.exit_signal,
            signal_strength=convergence.signal_strength,
            checks={
                "bio": convergence.bio_check_passed,
                "physics": convergence.physics_check_passed,
                "micro": convergence.micro_check_passed,
            },
            circuit_breakers={
                "entropy": convergence.entropy_circuit_breaker,
                "viral_death": convergence.viral_death,
                "distribution": convergence.distribution_exit,
            },
            entry_reasons=convergence.entry_reasons,
            exit_reasons=convergence.exit_reasons,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Convergence analysis failed for {asset}: {e}", exc_info=True)
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
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


# === Run Server ===

if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("ShopGuard Convergence API Server")
    logger.info("=" * 60)

    if SIMULATION_MODE and MATRIX_AVAILABLE:
        logger.info("🔮 MODE: MATRIX SIMULATION (No API keys required)")
        logger.info("   - Perfect Storm events every 60 seconds")
        logger.info("   - Whale traps, viral spikes, entropy shifts")
    else:
        logger.info("📊 MODE: LIVE API (Requires external APIs)")

    logger.info("-" * 60)
    logger.info("Endpoints:")
    logger.info("  - GET  /                    - Dashboard UI")
    logger.info("  - GET  /health              - Health check")
    logger.info("  - GET  /status              - System status + simulation info")
    logger.info("  - GET  /analyze/{asset}     - Full analysis")
    logger.info("  - GET  /convergence/{asset} - Convergence signal only")
    logger.info("  - WS   /ws/signals          - Real-time streaming")
    logger.info("  - GET  /docs                - API documentation")
    logger.info("=" * 60)
    logger.info(f"Supported assets: {', '.join(SUPPORTED_ASSETS)}")
    logger.info("Dashboard: http://localhost:8001/")
    logger.info("=" * 60)

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )

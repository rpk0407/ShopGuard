/**
 * Convergence Dashboard Component
 * ================================
 * Real-time visualization of the three-pillar trading strategy:
 * - Bio-Check: Viral K-Factor gauge
 * - Physics-Check: Shannon Entropy chart
 * - Micro-Check: CVD trend indicator
 *
 * Connects to WebSocket at ws://localhost:8001/ws/signals
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';

// ============================================================================
// CONFIGURATION
// ============================================================================

const WS_URL = 'ws://localhost:8001/ws/signals?assets=BTC,ETH';
const RECONNECT_DELAY = 3000;

// ============================================================================
// UTILITY COMPONENTS
// ============================================================================

/**
 * Circular Gauge Component - Used for K-Factor visualization
 */
const CircularGauge = ({ value, min = 0, max = 2, label, thresholds }) => {
  const percentage = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  const rotation = (percentage / 100) * 270 - 135; // -135 to 135 degrees

  // Determine color based on thresholds
  let color = '#fbbf24'; // yellow (default)
  if (thresholds) {
    if (value >= thresholds.high) color = '#22c55e'; // green
    else if (value <= thresholds.low) color = '#ef4444'; // red
  }

  const circumference = 2 * Math.PI * 45;
  const strokeDasharray = circumference;
  const strokeDashoffset = circumference - (percentage / 100) * circumference * 0.75;

  return (
    <div className="gauge-container">
      <svg viewBox="0 0 100 100" className="gauge-svg">
        {/* Background arc */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="#1f2937"
          strokeWidth="8"
          strokeDasharray={`${circumference * 0.75} ${circumference * 0.25}`}
          strokeLinecap="round"
          transform="rotate(135 50 50)"
        />
        {/* Value arc */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={strokeDasharray}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          transform="rotate(135 50 50)"
          style={{
            transition: 'stroke-dashoffset 0.5s ease, stroke 0.3s ease',
            filter: value >= (thresholds?.high || 999) ? 'drop-shadow(0 0 8px #22c55e)' : 'none'
          }}
        />
        {/* Center text */}
        <text x="50" y="45" textAnchor="middle" className="gauge-value" fill={color}>
          {value.toFixed(2)}
        </text>
        <text x="50" y="62" textAnchor="middle" className="gauge-label" fill="#9ca3af">
          {label}
        </text>
      </svg>
    </div>
  );
};

/**
 * Real-time Line Chart Component - Used for Entropy visualization
 */
const EntropyChart = ({ data, timestamps, threshold = 0.6 }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data.length) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = 30;

    // Clear canvas
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, width, height);

    // Draw grid
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;

    // Horizontal grid lines
    for (let i = 0; i <= 4; i++) {
      const y = padding + (i / 4) * (height - 2 * padding);
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
    }

    // Draw threshold line
    const thresholdY = padding + (1 - threshold) * (height - 2 * padding);
    ctx.strokeStyle = '#22c55e';
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(padding, thresholdY);
    ctx.lineTo(width - padding, thresholdY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw danger zone threshold (0.9)
    const dangerY = padding + (1 - 0.9) * (height - 2 * padding);
    ctx.strokeStyle = '#ef4444';
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(padding, dangerY);
    ctx.lineTo(width - padding, dangerY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw data line
    if (data.length > 1) {
      const xStep = (width - 2 * padding) / (data.length - 1);

      ctx.beginPath();
      ctx.lineWidth = 2;

      data.forEach((value, index) => {
        const x = padding + index * xStep;
        const y = padding + (1 - value) * (height - 2 * padding);

        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      // Gradient stroke based on current value
      const currentValue = data[data.length - 1];
      if (currentValue > 0.9) {
        ctx.strokeStyle = '#ef4444'; // Red - chaotic
      } else if (currentValue < 0.6) {
        ctx.strokeStyle = '#22c55e'; // Green - structured
      } else {
        ctx.strokeStyle = '#fbbf24'; // Yellow - transitional
      }

      ctx.stroke();

      // Draw current value dot
      const lastX = padding + (data.length - 1) * xStep;
      const lastY = padding + (1 - currentValue) * (height - 2 * padding);

      ctx.beginPath();
      ctx.arc(lastX, lastY, 5, 0, 2 * Math.PI);
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fill();

      // Glow effect
      ctx.shadowColor = ctx.strokeStyle;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(lastX, lastY, 3, 0, 2 * Math.PI);
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // Draw Y-axis labels
    ctx.fillStyle = '#6b7280';
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    ctx.fillText('1.0', padding - 5, padding + 4);
    ctx.fillText('0.5', padding - 5, height / 2 + 4);
    ctx.fillText('0.0', padding - 5, height - padding + 4);

    // Draw label
    ctx.fillStyle = '#9ca3af';
    ctx.font = '12px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('Shannon Entropy', width / 2, height - 5);

  }, [data, threshold]);

  return (
    <div className="chart-container">
      <canvas
        ref={canvasRef}
        width={400}
        height={200}
        style={{ width: '100%', height: 'auto', borderRadius: '8px' }}
      />
    </div>
  );
};

/**
 * Signal Status Badge Component
 */
const SignalStatus = ({ entrySignal, exitSignal, signalStrength }) => {
  let status, color, animation;

  if (exitSignal) {
    status = 'EXIT SIGNAL';
    color = '#ef4444';
    animation = 'pulse-red';
  } else if (entrySignal) {
    status = 'SNIPE ENTRY';
    color = '#22c55e';
    animation = 'pulse-green';
  } else if (signalStrength >= 0.66) {
    status = 'PREPARING';
    color = '#fbbf24';
    animation = '';
  } else {
    status = 'WAITING';
    color = '#6b7280';
    animation = '';
  }

  return (
    <div className={`signal-status ${animation}`} style={{ borderColor: color }}>
      <div className="signal-indicator" style={{ backgroundColor: color }} />
      <span style={{ color }}>{status}</span>
      <div className="signal-strength">
        <div
          className="signal-strength-bar"
          style={{
            width: `${signalStrength * 100}%`,
            backgroundColor: color
          }}
        />
      </div>
    </div>
  );
};

/**
 * Check Status Component - Shows pass/fail for each pillar
 */
const CheckStatus = ({ name, passed, details }) => {
  return (
    <div className={`check-status ${passed ? 'passed' : 'failed'}`}>
      <div className="check-icon">
        {passed ? '✓' : '✗'}
      </div>
      <div className="check-info">
        <div className="check-name">{name}</div>
        <div className="check-details">{details}</div>
      </div>
    </div>
  );
};

// ============================================================================
// MAIN DASHBOARD COMPONENT
// ============================================================================

const ConvergenceDashboard = () => {
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [asset, setAsset] = useState('BTC');

  // Signal data
  const [signalData, setSignalData] = useState({
    bio: { k_factor: 1.0, acceleration: 0, signal: 'STABLE', passed: false },
    physics: { entropy: 0.5, hurst: 0.5, market_regime: 'CAUTION', passed: false },
    micro: { cvd_value: 0, cvd_trend: 'NEUTRAL', whale_trap: false, passed: false },
    convergence: { entry_signal: false, exit_signal: false, signal_strength: 0 },
    recommendation: { action: 'HOLD', confidence: 'LOW', consensus: 0.5 },
    circuit_breakers: { entropy_breaker: false, viral_death: false, distribution_exit: false },
    entry_reasons: [],
    exit_reasons: [],
  });

  // History for charts
  const [entropyHistory, setEntropyHistory] = useState([]);
  const [kFactorHistory, setKFactorHistory] = useState([]);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // WebSocket connection handler
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    console.log('[WS] Connecting to', WS_URL);
    wsRef.current = new WebSocket(WS_URL);

    wsRef.current.onopen = () => {
      console.log('[WS] Connected');
      setConnected(true);
    };

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'signal_update') {
          setAsset(data.asset);
          setLastUpdate(new Date().toLocaleTimeString());

          setSignalData({
            bio: data.bio,
            physics: data.physics,
            micro: data.micro,
            convergence: data.convergence,
            recommendation: data.recommendation,
            circuit_breakers: data.circuit_breakers,
            entry_reasons: data.entry_reasons || [],
            exit_reasons: data.exit_reasons || [],
          });

          // Update history from server
          if (data.history) {
            setEntropyHistory(data.history.entropy || []);
            setKFactorHistory(data.history.k_factor || []);
          }
        }
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };

    wsRef.current.onclose = () => {
      console.log('[WS] Disconnected');
      setConnected(false);

      // Attempt reconnect
      reconnectTimeoutRef.current = setTimeout(connectWebSocket, RECONNECT_DELAY);
    };

    wsRef.current.onerror = (error) => {
      console.error('[WS] Error:', error);
    };
  }, []);

  // Connect on mount
  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connectWebSocket]);

  return (
    <div className="convergence-dashboard">
      {/* Styles */}
      <style>{`
        .convergence-dashboard {
          font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
          background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
          min-height: 100vh;
          padding: 20px;
          color: #e2e8f0;
        }

        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
          padding-bottom: 16px;
          border-bottom: 1px solid #334155;
        }

        .dashboard-title {
          font-size: 24px;
          font-weight: 700;
          background: linear-gradient(90deg, #22c55e, #3b82f6);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .connection-status {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          animation: pulse 2s infinite;
        }

        .status-dot.connected { background: #22c55e; }
        .status-dot.disconnected { background: #ef4444; }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        .dashboard-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 20px;
        }

        .panel {
          background: rgba(30, 41, 59, 0.8);
          border: 1px solid #334155;
          border-radius: 12px;
          padding: 20px;
          backdrop-filter: blur(10px);
        }

        .panel-title {
          font-size: 14px;
          font-weight: 600;
          color: #94a3b8;
          margin-bottom: 16px;
          text-transform: uppercase;
          letter-spacing: 1px;
        }

        /* Gauge styles */
        .gauge-container {
          display: flex;
          justify-content: center;
          align-items: center;
        }

        .gauge-svg {
          width: 180px;
          height: 180px;
        }

        .gauge-value {
          font-size: 24px;
          font-weight: 700;
        }

        .gauge-label {
          font-size: 10px;
          text-transform: uppercase;
        }

        /* Signal status styles */
        .signal-status {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px;
          border: 2px solid;
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.3);
        }

        .signal-indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }

        .signal-status span {
          font-size: 18px;
          font-weight: 700;
          flex: 1;
        }

        .signal-strength {
          width: 60px;
          height: 6px;
          background: #1f2937;
          border-radius: 3px;
          overflow: hidden;
        }

        .signal-strength-bar {
          height: 100%;
          transition: width 0.3s ease;
        }

        .pulse-green {
          animation: glow-green 1s infinite alternate;
        }

        .pulse-red {
          animation: glow-red 0.5s infinite alternate;
        }

        @keyframes glow-green {
          from { box-shadow: 0 0 5px #22c55e; }
          to { box-shadow: 0 0 20px #22c55e; }
        }

        @keyframes glow-red {
          from { box-shadow: 0 0 5px #ef4444; }
          to { box-shadow: 0 0 20px #ef4444; }
        }

        /* Check status styles */
        .checks-grid {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .check-status {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px;
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.2);
        }

        .check-status.passed {
          border-left: 3px solid #22c55e;
        }

        .check-status.failed {
          border-left: 3px solid #6b7280;
        }

        .check-icon {
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          font-size: 14px;
          font-weight: 700;
        }

        .check-status.passed .check-icon {
          background: #22c55e;
          color: #0f172a;
        }

        .check-status.failed .check-icon {
          background: #374151;
          color: #6b7280;
        }

        .check-name {
          font-weight: 600;
          font-size: 14px;
        }

        .check-details {
          font-size: 11px;
          color: #6b7280;
        }

        /* Reasons panel */
        .reasons-list {
          font-size: 12px;
          line-height: 1.6;
        }

        .reason-item {
          padding: 8px 0;
          border-bottom: 1px solid #1f2937;
        }

        .reason-item:last-child {
          border-bottom: none;
        }

        /* Chart container */
        .chart-container {
          margin-top: 8px;
        }

        /* Asset badge */
        .asset-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 12px;
          background: rgba(59, 130, 246, 0.2);
          border: 1px solid #3b82f6;
          border-radius: 20px;
          font-size: 14px;
          font-weight: 600;
        }

        /* Circuit breaker warning */
        .circuit-breakers {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 12px;
        }

        .breaker-badge {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
        }

        .breaker-badge.active {
          background: rgba(239, 68, 68, 0.2);
          border: 1px solid #ef4444;
          color: #ef4444;
          animation: blink 0.5s infinite;
        }

        .breaker-badge.inactive {
          background: rgba(107, 114, 128, 0.2);
          border: 1px solid #374151;
          color: #6b7280;
        }

        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>

      {/* Header */}
      <div className="dashboard-header">
        <div>
          <div className="dashboard-title">Convergence Dashboard</div>
          <div className="asset-badge">
            <span>{asset}</span>
            {lastUpdate && <span style={{ color: '#6b7280' }}>@ {lastUpdate}</span>}
          </div>
        </div>
        <div className="connection-status">
          <div className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          <span>{connected ? 'Live' : 'Reconnecting...'}</span>
        </div>
      </div>

      {/* Main Grid */}
      <div className="dashboard-grid">

        {/* Signal Status Panel */}
        <div className="panel">
          <div className="panel-title">Signal Status</div>
          <SignalStatus
            entrySignal={signalData.convergence.entry_signal}
            exitSignal={signalData.convergence.exit_signal}
            signalStrength={signalData.convergence.signal_strength}
          />
          <div className="circuit-breakers">
            <span className={`breaker-badge ${signalData.circuit_breakers.entropy_breaker ? 'active' : 'inactive'}`}>
              Entropy Breaker
            </span>
            <span className={`breaker-badge ${signalData.circuit_breakers.viral_death ? 'active' : 'inactive'}`}>
              Viral Death
            </span>
            <span className={`breaker-badge ${signalData.circuit_breakers.distribution_exit ? 'active' : 'inactive'}`}>
              Distribution
            </span>
          </div>
        </div>

        {/* Viral K-Factor Gauge */}
        <div className="panel">
          <div className="panel-title">Bio-Check: Viral K-Factor</div>
          <CircularGauge
            value={signalData.bio.k_factor}
            min={0}
            max={2}
            label="K-Factor"
            thresholds={{ low: 0.8, high: 1.2 }}
          />
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <span style={{
              color: signalData.bio.signal === 'EXPLOSIVE' ? '#22c55e' :
                     signalData.bio.signal === 'DECLINING' ? '#ef4444' : '#fbbf24',
              fontWeight: 600
            }}>
              {signalData.bio.signal}
            </span>
            <span style={{ color: '#6b7280', marginLeft: 8 }}>
              Accel: {signalData.bio.acceleration?.toFixed(2) || '0.00'}
            </span>
          </div>
        </div>

        {/* Entropy Chart */}
        <div className="panel">
          <div className="panel-title">Physics-Check: Shannon Entropy</div>
          <EntropyChart
            data={entropyHistory.length > 0 ? entropyHistory : [signalData.physics.entropy]}
            threshold={0.6}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 12 }}>
            <span>
              Entropy: <strong style={{ color: signalData.physics.entropy < 0.6 ? '#22c55e' : '#fbbf24' }}>
                {signalData.physics.entropy?.toFixed(3)}
              </strong>
            </span>
            <span>
              Hurst: <strong style={{ color: signalData.physics.hurst > 0.65 ? '#22c55e' : '#fbbf24' }}>
                {signalData.physics.hurst?.toFixed(3)}
              </strong>
            </span>
            <span style={{
              color: signalData.physics.market_regime === 'TRADEABLE' ? '#22c55e' :
                     signalData.physics.market_regime === 'AVOID' ? '#ef4444' : '#fbbf24'
            }}>
              {signalData.physics.market_regime}
            </span>
          </div>
        </div>

        {/* Three Pillars Status */}
        <div className="panel">
          <div className="panel-title">Convergence Checks</div>
          <div className="checks-grid">
            <CheckStatus
              name="Bio-Check"
              passed={signalData.bio.passed}
              details={`K=${signalData.bio.k_factor?.toFixed(2)} (need >1.2)`}
            />
            <CheckStatus
              name="Physics-Check"
              passed={signalData.physics.passed}
              details={`H=${signalData.physics.entropy?.toFixed(2)}, Hurst=${signalData.physics.hurst?.toFixed(2)}`}
            />
            <CheckStatus
              name="Micro-Check"
              passed={signalData.micro.passed}
              details={`CVD: ${signalData.micro.cvd_trend} ${signalData.micro.whale_trap ? '(Whale Trap!)' : ''}`}
            />
          </div>
        </div>

        {/* Entry/Exit Reasons */}
        <div className="panel" style={{ gridColumn: 'span 2' }}>
          <div className="panel-title">Analysis Reasons</div>
          <div className="reasons-list">
            {[...signalData.entry_reasons, ...signalData.exit_reasons].map((reason, i) => (
              <div key={i} className="reason-item">{reason}</div>
            ))}
            {signalData.entry_reasons.length === 0 && signalData.exit_reasons.length === 0 && (
              <div style={{ color: '#6b7280', fontStyle: 'italic' }}>Waiting for signals...</div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default ConvergenceDashboard;

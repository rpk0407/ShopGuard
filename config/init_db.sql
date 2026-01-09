-- =============================================================================
-- Database Initialization Script for Quantitative Trading Platform
-- =============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- =============================================================================
-- MARKET DATA TABLES
-- =============================================================================

-- Historical price data
CREATE TABLE IF NOT EXISTS market_data_ohlcv (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    vwap DOUBLE PRECISION,
    PRIMARY KEY (time, symbol, exchange)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('market_data_ohlcv', 'time', if_not_exists => TRUE);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol ON market_data_ohlcv (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_exchange ON market_data_ohlcv (exchange, time DESC);

-- Order book snapshots
CREATE TABLE IF NOT EXISTS market_data_orderbook (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    bids JSONB,  -- [{price, size, num_orders}, ...]
    asks JSONB,
    PRIMARY KEY (time, symbol, exchange)
);

SELECT create_hypertable('market_data_orderbook', 'time', if_not_exists => TRUE);

-- =============================================================================
-- TRADING TABLES
-- =============================================================================

-- Orders
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    client_order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- buy/sell
    order_type TEXT NOT NULL,  -- market/limit/stop
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION,
    stop_price DOUBLE PRECISION,
    status TEXT NOT NULL,  -- pending/submitted/filled/cancelled
    filled_quantity DOUBLE PRECISION DEFAULT 0,
    filled_price DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    strategy_name TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_strategy ON orders (strategy_name, created_at DESC);

-- Trades (executions)
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    order_id TEXT REFERENCES orders(order_id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    commission DOUBLE PRECISION DEFAULT 0,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exchange TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_trades_order ON trades (order_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_time ON trades (executed_at DESC);

-- Positions
CREATE TABLE IF NOT EXISTS positions (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    current_price DOUBLE PRECISION NOT NULL,
    unrealized_pnl DOUBLE PRECISION NOT NULL,
    realized_pnl DOUBLE PRECISION DEFAULT 0,
    strategy_name TEXT,
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('positions', 'time', if_not_exists => TRUE);

-- =============================================================================
-- PORTFOLIO & RISK TABLES
-- =============================================================================

-- Portfolio snapshots
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    time TIMESTAMPTZ NOT NULL PRIMARY KEY,
    equity DOUBLE PRECISION NOT NULL,
    cash DOUBLE PRECISION NOT NULL,
    buying_power DOUBLE PRECISION,
    gross_exposure DOUBLE PRECISION,
    net_exposure DOUBLE PRECISION,
    leverage DOUBLE PRECISION,
    returns_daily DOUBLE PRECISION,
    returns_cumulative DOUBLE PRECISION,
    sharpe_ratio DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    num_positions INTEGER,
    metadata JSONB
);

SELECT create_hypertable('portfolio_snapshots', 'time', if_not_exists => TRUE);

-- Risk events
CREATE TABLE IF NOT EXISTS risk_events (
    event_id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,  -- limit_breach/drawdown/volatility_spike
    severity TEXT NOT NULL,  -- info/warning/critical
    description TEXT,
    metrics JSONB,
    action_taken TEXT
);

CREATE INDEX IF NOT EXISTS idx_risk_events_time ON risk_events (time DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_type ON risk_events (event_type, time DESC);

-- =============================================================================
-- STRATEGY & MODEL TABLES
-- =============================================================================

-- Strategy performance
CREATE TABLE IF NOT EXISTS strategy_performance (
    time TIMESTAMPTZ NOT NULL,
    strategy_name TEXT NOT NULL,
    pnl DOUBLE PRECISION,
    returns DOUBLE PRECISION,
    win_rate DOUBLE PRECISION,
    sharpe_ratio DOUBLE PRECISION,
    num_trades INTEGER,
    avg_trade_duration INTERVAL,
    PRIMARY KEY (time, strategy_name)
);

SELECT create_hypertable('strategy_performance', 'time', if_not_exists => TRUE);

-- Model predictions (for backtesting/analysis)
CREATE TABLE IF NOT EXISTS model_predictions (
    time TIMESTAMPTZ NOT NULL,
    model_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    prediction_type TEXT,  -- direction/price/volatility
    prediction DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    actual DOUBLE PRECISION,
    error DOUBLE PRECISION,
    PRIMARY KEY (time, model_name, symbol)
);

SELECT create_hypertable('model_predictions', 'time', if_not_exists => TRUE);

-- =============================================================================
-- SYSTEM TABLES
-- =============================================================================

-- System metrics
CREATE TABLE IF NOT EXISTS system_metrics (
    time TIMESTAMPTZ NOT NULL PRIMARY KEY,
    latency_ms DOUBLE PRECISION,
    cpu_usage DOUBLE PRECISION,
    memory_usage DOUBLE PRECISION,
    active_orders INTEGER,
    active_positions INTEGER,
    messages_per_second INTEGER,
    metadata JSONB
);

SELECT create_hypertable('system_metrics', 'time', if_not_exists => TRUE);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    log_id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    changes JSONB,
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_time ON audit_log (time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (user_id, time DESC);

-- =============================================================================
-- CONTINUOUS AGGREGATES (Pre-computed views for performance)
-- =============================================================================

-- 1-minute OHLCV aggregates
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    exchange,
    FIRST(open, time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, time) AS close,
    SUM(volume) AS volume
FROM market_data_ohlcv
GROUP BY bucket, symbol, exchange
WITH NO DATA;

-- 5-minute OHLCV aggregates
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    symbol,
    exchange,
    FIRST(open, time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, time) AS close,
    SUM(volume) AS volume
FROM market_data_ohlcv
GROUP BY bucket, symbol, exchange
WITH NO DATA;

-- Daily portfolio returns
CREATE MATERIALIZED VIEW IF NOT EXISTS portfolio_daily_returns
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    LAST(equity, time) AS ending_equity,
    LAST(returns_cumulative, time) AS cumulative_return,
    MAX(equity) AS day_high,
    MIN(equity) AS day_low
FROM portfolio_snapshots
GROUP BY day
WITH NO DATA;

-- =============================================================================
-- DATA RETENTION POLICIES
-- =============================================================================

-- Keep raw 1-second data for 30 days
SELECT add_retention_policy('market_data_ohlcv', INTERVAL '30 days', if_not_exists => TRUE);

-- Keep order book snapshots for 7 days
SELECT add_retention_policy('market_data_orderbook', INTERVAL '7 days', if_not_exists => TRUE);

-- Keep system metrics for 90 days
SELECT add_retention_policy('system_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Function to calculate Sharpe ratio
CREATE OR REPLACE FUNCTION calculate_sharpe_ratio(
    strategy TEXT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    risk_free_rate DOUBLE PRECISION DEFAULT 0.02
)
RETURNS DOUBLE PRECISION AS $$
DECLARE
    sharpe DOUBLE PRECISION;
BEGIN
    SELECT
        (AVG(returns) - risk_free_rate / 252) / NULLIF(STDDEV(returns), 0) * SQRT(252)
    INTO sharpe
    FROM strategy_performance
    WHERE strategy_name = strategy
      AND time BETWEEN start_time AND end_time;

    RETURN sharpe;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- GRANTS (Security)
-- =============================================================================

-- Grant permissions to trader user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trader;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trader;

-- =============================================================================
-- INITIALIZATION COMPLETE
-- =============================================================================

-- Insert initial system marker
INSERT INTO audit_log (action, entity_type, entity_id, changes)
VALUES ('system_init', 'database', 'quant_research', '{"version": "1.0", "initialized_at": "now()"}');

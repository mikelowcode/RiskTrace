CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_start TEXT NOT NULL,
    ts_end TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response_text TEXT NOT NULL,
    stop_reason TEXT NOT NULL,
    tool_calls_json TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    risk_level TEXT NOT NULL,
    matched_terms TEXT
);

CREATE INDEX IF NOT EXISTS idx_interactions_ts_start ON interactions (ts_start);
CREATE INDEX IF NOT EXISTS idx_interactions_risk_level ON interactions (risk_level);

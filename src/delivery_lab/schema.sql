PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    surname TEXT NOT NULL,
    first_name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pickup_points (
    pickup_point_id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    address TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    recipient_name TEXT NOT NULL,
    delivery_method TEXT NOT NULL CHECK (delivery_method IN ('courier', 'pickup_point')),
    pickup_point_id TEXT REFERENCES pickup_points(pickup_point_id),
    delivery_address TEXT,
    status TEXT NOT NULL CHECK (status IN ('created', 'accepted', 'in_transit', 'delivered', 'cancelled')),
    created_at TEXT NOT NULL,
    CHECK (
        (delivery_method = 'pickup_point' AND pickup_point_id IS NOT NULL AND delivery_address IS NULL)
        OR (delivery_method = 'courier' AND pickup_point_id IS NULL AND delivery_address IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS tracking_events (
    event_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
    status TEXT NOT NULL CHECK (status IN ('created', 'accepted', 'in_transit', 'delivered', 'cancelled')),
    description TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    task_code TEXT NOT NULL,
    target_shipment_id TEXT REFERENCES shipments(shipment_id),
    expected_pickup_point_id TEXT REFERENCES pickup_points(pickup_point_id),
    created_after TEXT NOT NULL,
    UNIQUE(session_id, task_code)
);

CREATE TABLE IF NOT EXISTS audit_log (
    request_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(session_id),
    method TEXT NOT NULL,
    route TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    resource_id TEXT,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shipments_session ON shipments(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tracking_shipment ON tracking_events(shipment_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id, occurred_at);

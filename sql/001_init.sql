-- Enterprise Tool Router - Initial Schema and Seed Data
-- Commit 09: Postgres local environment

-- sales_fact table: sample sales data for SQL tool queries
CREATE TABLE IF NOT EXISTS sales_fact (
    id SERIAL PRIMARY KEY,
    region VARCHAR(50) NOT NULL,
    quarter VARCHAR(10) NOT NULL,
    revenue DECIMAL(12, 2) NOT NULL,
    units_sold INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- job_runs table: track ETL/computation job runs
CREATE TABLE IF NOT EXISTS job_runs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failure', 'running')),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    records_processed INTEGER DEFAULT 0
);

-- audit_log table: append-only audit trail for query operations
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    correlation_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(128),
    tool VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    input_hash VARCHAR(64) NOT NULL,
    output_hash VARCHAR(64) NOT NULL,
    success BOOLEAN NOT NULL,
    duration_ms INTEGER NOT NULL
);

-- Create index on audit_log for efficient querying
CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_log_correlation_id ON audit_log(correlation_id);

-- Seed data for sales_fact (Q1-Q4 2024, multiple regions)
INSERT INTO sales_fact (region, quarter, revenue, units_sold) VALUES
    ('North America', 'Q1', 1250000.00, 5200),
    ('North America', 'Q2', 1380000.00, 5800),
    ('North America', 'Q3', 1420000.00, 6100),
    ('North America', 'Q4', 1650000.00, 7200),
    ('Europe', 'Q1', 980000.00, 4100),
    ('Europe', 'Q2', 1050000.00, 4400),
    ('Europe', 'Q3', 1120000.00, 4800),
    ('Europe', 'Q4', 1280000.00, 5500),
    ('Asia Pacific', 'Q1', 850000.00, 3800),
    ('Asia Pacific', 'Q2', 920000.00, 4100),
    ('Asia Pacific', 'Q3', 1100000.00, 4900),
    ('Asia Pacific', 'Q4', 1350000.00, 6200),
    ('Latin America', 'Q1', 420000.00, 2100),
    ('Latin America', 'Q2', 480000.00, 2400),
    ('Latin America', 'Q3', 510000.00, 2600),
    ('Latin America', 'Q4', 590000.00, 3000);

-- Seed data for job_runs (sample ETL job history)
INSERT INTO job_runs (job_name, status, started_at, completed_at, records_processed) VALUES
    ('daily_sales_etl', 'success', '2024-01-15 02:00:00', '2024-01-15 02:15:00', 15000),
    ('daily_sales_etl', 'success', '2024-01-16 02:00:00', '2024-01-16 02:12:00', 15200),
    ('daily_sales_etl', 'failure', '2024-01-17 02:00:00', '2024-01-17 02:05:00', 0),
    ('daily_sales_etl', 'success', '2024-01-18 02:00:00', '2024-01-18 02:14:00', 14800),
    ('weekly_report_gen', 'success', '2024-01-14 03:00:00', '2024-01-14 03:45:00', 5200),
    ('weekly_report_gen', 'success', '2024-01-21 03:00:00', '2024-01-21 03:38:00', 5400),
    ('customer_sync', 'success', '2024-01-15 01:00:00', '2024-01-15 01:30:00', 25000),
    ('customer_sync', 'success', '2024-01-16 01:00:00', '2024-01-16 01:28:00', 25100);

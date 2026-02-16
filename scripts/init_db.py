#!/usr/bin/env python3
"""
Initialize the database schema and seed data for Enterprise Tool Router.
This script is used by CI to set up the database before running tests.
"""
import sys
from pathlib import Path

# Add src to path so we can import from enterprise_tool_router
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from enterprise_tool_router.db import get_connection


def init_database():
    """Execute the SQL schema initialization script."""
    sql_file = Path(__file__).parent.parent / "sql" / "001_init.sql"
    
    if not sql_file.exists():
        print(f"Error: SQL file not found at {sql_file}")
        sys.exit(1)
    
    sql_content = sql_file.read_text(encoding="utf-8")
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Clear data tables before re-seeding (keep audit_log intact)
                # Use DELETE instead of TRUNCATE since we need IF EXISTS-like behavior
                cur.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sales_fact') THEN
                            DELETE FROM sales_fact;
                        END IF;
                        IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'job_runs') THEN
                            DELETE FROM job_runs;
                        END IF;
                    END $$;
                """)

                # Execute the schema initialization
                cur.execute(sql_content)
                conn.commit()
                print("[OK] Database schema initialized successfully")
                print(f"   - Executed: {sql_file}")
                
                # Verify tables were created
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """)
                tables = [row[0] for row in cur.fetchall()]
                print(f"   - Tables created: {', '.join(tables)}")
                
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_database()

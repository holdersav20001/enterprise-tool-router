import sys
sys.path.insert(0, 'src')

import psycopg
import os

# Set password in environment
os.environ['PGPASSWORD'] = 'etr_password'

try:
    print("Attempting connection...")
    # Use the key/value format which respects PGPASSWORD
    conn = psycopg.connect(
        host='localhost',
        port=5433,
        dbname='etr_db',
        user='etr_user',
        password='etr_password',
        sslmode='disable'
    )
    print("Connected successfully!")
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        result = cur.fetchone()
        print(f"Query result: {result}")
    conn.close()
    print("Connection closed")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()


import os
import sys
import psycopg2
from psycopg2 import sql

# Add parent directory to path to allow importing app modules if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get DB config from Env or direct
# Fallback to local default for quick check if env not set
DB_HOST = os.getenv("POSTGRES_SERVER", "localhost")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_DB = os.getenv("POSTGRES_DB", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "54322") # Default to Colima port if not set

def get_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_DB,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None

def verify_tables():
    conn = get_connection()
    if not conn:
        print("Could not connect to database.")
        sys.exit(1)

    cursor = conn.cursor()
    
    required_tables = [
        "organizations",
        "projects",
        "documents",
        "runs",
        "run_audits",
        "activities" # Phase 4.1 added this
    ]

    print(f"🔍 Verifying Database Schema on {DB_HOST}:{DB_PORT}/{DB_DB}...\n")
    
    missing = []
    
    print(f"{'TABLE':<20} | {'STATUS':<10}")
    print("-" * 35)
    
    for table in required_tables:
        cursor.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)",
            (table,)
        )
        exists = cursor.fetchone()[0]
        status = "✅ OK" if exists else "❌ MISSING"
        print(f"{table:<20} | {status}")
        
        if not exists:
            missing.append(table)
            
    print("-" * 35)

    if missing:
        print(f"\n⚠️  Missing Tables: {', '.join(missing)}")
        print("   Please apply the corresponding schema SQL files.")
        sys.exit(1)
    else:
        print("\n✅ All core tables are present.")
        sys.exit(0)

if __name__ == "__main__":
    verify_tables()

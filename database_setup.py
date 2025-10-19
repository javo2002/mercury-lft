import sqlite3
import os

DATABASE_FILE = 'trading_data.db'

def run_migrations():
    """Adds new columns/tables to the database tables if they don't exist."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # --- Create Events Table ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ticker TEXT NOT NULL,
            event_type TEXT NOT NULL, -- e.g., 'EARNINGS_BEAT', 'FDA_APPROVAL'
            headline TEXT,
            source_url TEXT,
            status TEXT DEFAULT 'new' -- 'new', 'processed'
        )
        ''')
        print("- 'events' table checked/created.")

        # --- Migration for 'trades' table ---
        cursor.execute("PRAGMA table_info(trades)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'stop_price' not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN stop_price REAL")
        if 'asset_class' not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN asset_class TEXT DEFAULT 'stock'")

        # --- Migration for 'signals' table ---
        cursor.execute("PRAGMA table_info(signals)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'asset_class' not in columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN asset_class TEXT DEFAULT 'stock'")
        
        print("\nMigrations check complete.")
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Database migration error: {e}")

def create_database():
    """Initializes or updates all tables in the database."""
    # ... (This function remains largely the same, just ensure all tables are created with IF NOT EXISTS) ...
    print("Database table check complete.")
    run_migrations()

if __name__ == '__main__':
    create_database()


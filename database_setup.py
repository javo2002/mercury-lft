import sqlite3
import os

DATABASE_FILE = 'trading_data.db'

def create_database():
    """Initializes or updates all tables in the database."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # --- Main Tables ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            ticker TEXT,
            asset_class TEXT DEFAULT 'stock',
            date TEXT,
            sma_signal TEXT,
            rsi_signal TEXT,
            volatility_signal TEXT,
            pattern_signal TEXT,
            live_signal TEXT,
            last_close REAL,
            PRIMARY KEY (ticker, date)
        )
        ''')
        print("- 'signals' table checked/created.")

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            ticker TEXT,
            asset_class TEXT DEFAULT 'stock',
            action TEXT,
            quantity REAL,
            price REAL,
            reason TEXT,
            trade_type TEXT,
            stop_price REAL
        )
        ''')
        print("- 'trades' table checked/created.")

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment (
            ticker TEXT,
            date TEXT,
            sentiment_score REAL,
            sentiment_label TEXT,
            keywords TEXT,
            top_headline TEXT,
            PRIMARY KEY (ticker, date)
        )
        ''')
        print("- 'sentiment' table checked/created.")

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ticker TEXT NOT NULL,
            event_type TEXT NOT NULL,
            headline TEXT,
            source_url TEXT,
            status TEXT DEFAULT 'new'
        )
        ''')
        print("- 'events' table checked/created.")

        # --- NEW: Mailbox Table ---
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mailbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'unread' -- 'unread' or 'read'
        )
        ''')
        print("- 'mailbox' table checked/created.")

        print("\nDatabase setup/update complete.")
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == '__main__':
    create_database()

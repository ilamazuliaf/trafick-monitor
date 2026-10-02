"""
Database Connection & Schema Manager (prd.md Section 24)
Handles SQLite connection pooling and schema initialization.
"""
import os
import sqlite3
from typing import Generator
from app.core.config import settings
from app.core.logging import logger


def get_db_connection() -> sqlite3.Connection:
    """
    Creates and returns a SQLite connection with row factory enabled.
    """
    db_path = settings.database_path
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Initializes database schema and indexes.
    """
    logger.info(f"Initializing SQLite database at: {settings.database_path}")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Table creation (prd.md Section 24)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS traffic_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                interface_name TEXT NOT NULL,
                rx_bytes INTEGER NOT NULL,
                tx_bytes INTEGER NOT NULL,
                rx_bps REAL NOT NULL,
                tx_bps REAL NOT NULL
            );
        """)

        # Index creation for optimal query performance (prd.md Section 24 & 50)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_traffic_interface_time 
            ON traffic_samples (interface_name, timestamp);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_traffic_timestamp 
            ON traffic_samples (timestamp);
        """)

        # Customers table creation (tambah_fitur.md Section 9 & 10)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT UNIQUE,
                username TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                package TEXT,
                monitoring_enabled BOOLEAN NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_customers_username 
            ON customers (username);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_customers_monitoring 
            ON customers (monitoring_enabled);
        """)

        conn.commit()
        logger.info("Database schema & indexes initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise e
    finally:
        conn.close()

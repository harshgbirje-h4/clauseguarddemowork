import sqlite3
import os
import sys

def init_db(db_path="data/db/portfolio.db"):
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # Connect to the database (creates it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    
    cursor = conn.cursor()
    
    # 1. Services table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT
        )
    """)
    
    # 2. Canonical Entities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS canonical_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    
    # 3. Clauses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clauses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            severity_score REAL,
            specificity_score REAL,
            risk_category TEXT,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        )
    """)
    
    # 4. Clause to Entity Mapping table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clause_entity_mapping (
            clause_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,
            PRIMARY KEY (clause_id, entity_id),
            FOREIGN KEY (clause_id) REFERENCES clauses(id) ON DELETE CASCADE,
            FOREIGN KEY (entity_id) REFERENCES canonical_entities(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"Database successfully initialized at {db_path}")

def reset_db(db_path="data/db/portfolio.db"):
    """Completely resets the portfolio database to an empty, clean state (0 services)."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF;")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clause_entity_mapping;")
    cursor.execute("DELETE FROM clauses;")
    cursor.execute("DELETE FROM canonical_entities;")
    cursor.execute("DELETE FROM services;")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.close()
    print(f"Portfolio database successfully reset to clean state at {db_path} (0 services)")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Initialize or reset ClauseGuard SQLite database.")
    parser.add_argument("--reset", "--clean", dest="reset", action="store_true", help="Reset portfolio database to empty state (0 services)")
    parser.add_argument("--db", default=None, help="Custom database path")
    args = parser.parse_args()

    # Determine absolute path to ensure we run from project root context
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    db_file_path = args.db or os.path.join(base_dir, 'data', 'db', 'portfolio.db')
    if args.reset:
        reset_db(db_file_path)
    else:
        init_db(db_file_path)

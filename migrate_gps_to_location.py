"""
One-shot migration: rename gps_accuracy columns → location (varchar) in the trips table.
Run from the project root: python migrate_gps_to_location.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

db_url = os.getenv("DATABASE_URL", "")
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(db_url, pool_pre_ping=True)

MIGRATIONS = [
    # 1. Rename start_gps_accuracy → start_location
    "ALTER TABLE trips RENAME COLUMN start_gps_accuracy TO start_location;",
    # 2. Change its type from float to varchar(255)
    "ALTER TABLE trips ALTER COLUMN start_location TYPE VARCHAR(255) USING start_location::VARCHAR;",
    # 3. Rename end_gps_accuracy → end_location
    "ALTER TABLE trips RENAME COLUMN end_gps_accuracy TO end_location;",
    # 4. Change its type from float to varchar(255)
    "ALTER TABLE trips ALTER COLUMN end_location TYPE VARCHAR(255) USING end_location::VARCHAR;",
]

with engine.begin() as conn:
    for sql in MIGRATIONS:
        print(f"Executing: {sql}")
        conn.execute(text(sql))

print("\n✅ Migration complete: gps_accuracy columns renamed to location (varchar).")

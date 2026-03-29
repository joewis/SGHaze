import sqlite3
import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
import os
from pathlib import Path

# --- Configuration ---
API_URL = "https://api-open.data.gov.sg/v2/real-time/api/pm25"
SG_TZ = pytz.timezone('Asia/Singapore')
BASE_DIR = Path(__file__).resolve().parent
DB_NAME = BASE_DIR / "sg_haze.db"

def get_latest_timestamp():
    """Finds the most recent entry in the DB to avoid redundant pulls."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(timestamp) FROM pm25_readings")
            row = cursor.fetchone()
            return pd.to_datetime(row[0]) if row and row[0] else None
    except sqlite3.OperationalError:
        return None

def fetch_day_data(date_str):
    """Fetches a full day's data and inserts into the pivot table."""
    try:
        response = requests.get(API_URL, params={"date": date_str}, timeout=15)
        response.raise_for_status()
        data = response.json()
        items = data.get('data', {}).get('items', [])
        
        if not items:
            return True

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            for item in items:
                ts = item.get('timestamp')
                # Extract readings - API usually returns keys: west, east, central, south, north
                r = item.get('readings', {}).get('pm25_one_hourly', {})
                
                # INSERT OR REPLACE handles partial day updates (e.g. today's hourly updates)
                cursor.execute("""
                    INSERT OR REPLACE INTO pm25_readings 
                    (timestamp, west, north, central, south, east)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    ts, 
                    r.get('west'), 
                    r.get('north'), 
                    r.get('central'), 
                    r.get('south'), 
                    r.get('east')
                ))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error fetching {date_str}: {e}")
        return False

def sync_haze_data():
    """Main loop to backfill from the last known date until today."""
    last_ts = get_latest_timestamp()
    
    # Start from Jan 1st 2025 if DB is empty, otherwise restart from the last known day
    if last_ts:
        current_date = last_ts.date()
    else:
        current_date = datetime(2025, 1, 1).date()
    
    today = datetime.now(SG_TZ).date()
    
    print(f"Starting sync from {current_date} to {today}...")
    
    while current_date <= today:
        date_str = current_date.strftime('%Y-%m-%d')
        print(f"Processing: {date_str}")
        
        if fetch_day_data(date_str):
            current_date += timedelta(days=1)
            # Rate limit: 6 requests / 10 seconds (staying safe with 2s delay)
            time.sleep(2) 
        else:
            print("Request failed. Waiting 10s before retry...")
            time.sleep(10)

if __name__ == "__main__":
    sync_haze_data()
    
    # Final database compression
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("VACUUM")
        print("Database optimized and vacuumed.")

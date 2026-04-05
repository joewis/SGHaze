"""
SG PM2.5 Haze Heatmap Generator (Database Edition)

This script pulls historical data from a local SQLite database, 
generates a vertical heatmap, and creates an HTML page for visualization.
It is designed to run via GitHub Actions.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd
import json



# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Determine the base directory safely
try:
    BASE_DIR = Path(__file__).parent
except NameError:
    BASE_DIR = Path.cwd()

@dataclass
class Config:
    """Configuration parameters for the haze script."""
    base_dir: Path = BASE_DIR
    db_path: Path = BASE_DIR / "sg_haze.db"
    days_to_plot: int = 7*16  # Number of days to show in the heatmap
    regions: list = None
    output_html_file: str = "index.html"

    def __post_init__(self):
        if self.regions is None:
            self.regions = ['west', 'north', 'central', 'south', 'east']

class DatabaseFetcher:
    """Handles fetching PM2.5 data from the local SQLite database."""
    def __init__(self, config: Config):
        self.config = config

    def fetch_freshness_from_db(self):
        with sqlite3.connect(self.config.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM sync_meta WHERE key = 'last_api_update'")
            res = cursor.fetchone()
            return res[0] if res else "Unknown"

    def fetch_data(self) -> pd.DataFrame:
        """
        Retrieves data relative to the LATEST timestamp in the database.
        This avoids issues with GitHub runners using UTC.
        """
        if not self.config.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.config.db_path}")

        with sqlite3.connect(self.config.db_path) as conn:
            # 1. Find the Anchor (The most recent data point we have)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(timestamp) FROM pm25_readings")
            res = cursor.fetchone()

            if not res or not res[0]:
                logger.error("Database table is empty.")
                return pd.DataFrame()

            latest_db_ts = pd.to_datetime(res[0])
            logger.info(f"Latest data point in DB: {latest_db_ts}")

            # 2. Calculate the start of our window
            cutoff_dt = latest_db_ts - timedelta(days=self.config.days_to_plot)
            cutoff_str = cutoff_dt.isoformat()
            logger.info(f"Cutoff date: {cutoff_str}")

            # 3. Pull the data into a DataFrame
            query = """
                SELECT * FROM pm25_readings 
                WHERE timestamp >= ? 
                ORDER BY timestamp DESC
            """

            df = pd.read_sql(query, conn, params=(cutoff_str,))
        

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            logger.info(f"Loaded {len(df)} rows for the heatmap.")

        return df


class HTMLGenerator:
    """Generates a clean index.html file to host on GitHub Pages."""

    @staticmethod
    def generate_html_table(df: pd.DataFrame, regions: list) -> str:
        """Generate an HTML table with color-coded cells matching the heatmap."""
        # Sort data newest to oldest to match heatmap
        df_table = df.sort_values('timestamp', ascending=False).copy()

        # Build table rows
        rows = []
        for _, row in df_table.iterrows():
            timestamp = row['timestamp']
            #time_label = timestamp.strftime('%a %d, %H:%M')
            time_label = timestamp.strftime('%d %b %Y %H:%M')

            cells = []
            for region in regions:
                value = row[region]
                cells.append(f'<td class="pm25-val" style="text-align: center; font-weight: bold; padding: 4px 2px; min-width: 40px;">{value:.0f}</td>')
            rows.append(f'<tr><td style="font-weight: normal; padding: 4px; white-space: nowrap; font-size: 0.75rem;">{time_label}</td>' + ''.join(cells) + '</tr>')

        # Build header row
        header_cells = [f'<th style="padding: 8px; background-color: #333; color: white; font-size: 0.75rem;">Time</th>']
        for region in regions:
            header_cells.append(f'<th style="padding: 8px; background-color: #333; color: white; font-size: 0.75rem;">{region.capitalize()}</th>')

        header_row = '<tr>' + ''.join(header_cells) + '</tr>'

        table_html = f'''
        <div class="table-container">
            <table class="data-table">
                <thead>{header_row}</thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        '''

        return table_html

    

    @staticmethod
    def generate(last_ts_str: str, output_path: str, df: pd.DataFrame = None, regions: list = None):
        # Generate the data table if dataframe is provided
        table_html = ""
        if df is not None and regions is not None and not df.empty:
            table_html = HTMLGenerator.generate_html_table(df, regions)

        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SG PM2.5 Haze Heatmap</title>
            <link rel="stylesheet" href="styles.css">
            <script src="app.js"></script>
        </head>

        <body>
            <div class="card">
                <h1>🇸🇬 SG Haze Heatmap</h1>
                <div class="legend">
                    <div class="item"><div class="dot" style="background:#228B22"></div>Good</div>
                    <div class="item"><div class="dot" style="background:#FFFF00"></div>Moderate</div>
                    <div class="item"><div class="dot" style="background:#FF8800"></div>Unhealthy</div>
                    <div class="item"><div class="dot" style="background:#800080"></div>Hazardous</div>
                </div>

                {table_html}

            </div>

            <div class="footer-fixed">
                <strong>Source:</strong> data.gov.sg API<br>
                <strong>Data Freshness:</strong> {last_ts_str} (SGT)<br>
                Generated via GitHub Actions
            </div>

        </body>
        </html>
        """

        with open(output_path, "w", encoding='utf-8') as f:
            f.write(html_template)


def main():
    config = Config()
    fetcher = DatabaseFetcher(config)

    try:
        # 1. Get Data
        df = fetcher.fetch_data()
        if df.empty:
            return 1
       

        # 3. Update HTML
        last_ts = fetcher.fetch_freshness_from_db()
        HTMLGenerator.generate(
            last_ts, 
            config.output_html_file,
            df=df,
            regions=config.regions,
        )

        logger.info("Successfully updated index.html")

            

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())

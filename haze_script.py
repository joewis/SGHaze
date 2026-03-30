"""
SG PM2.5 Haze Heatmap Generator (Database Edition)

This script pulls historical data from a local SQLite database, 
generates a vertical heatmap, and creates an HTML page for visualization.
It is designed to run locally on an X230 or via GitHub Actions.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Configuration parameters for the haze script."""
    # File Paths
    base_dir: Path = Path(__file__).parent
    db_path: Path = Path(__file__).parent / "sg_haze.db"
    
    # Data Window
    days_to_plot: int = 7*16  # Number of days to show in the heatmap
    
    # Visualization Settings
    regions: list = None
    vmax_pm25: int = 250  # Max scale for color (216 is the highest ever recorded in Singapore for PM2.5)
    row_height_inches: float = 0.25
    header_height_inches: float = 2.5
    figure_width_inches: float = 11.0
    dpi: int = 120
    
    # Output Settings
    output_image_name: str = "haze_latest.png"
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

# PM2.5 thresholds (µg/m³) and their specific colors
PM25_LEVELS = [
    (0, "#228B22"),   # Good
    (12, "#FFFF00"),  # Moderate (Low)
    (35, "#FFCC00"),  # Moderate (High)
    (55, "#FF8800"),  # Unhealthy (Low)
    (150, "#FF0000"), # Unhealthy (High)
    (250, "#800080")  # Hazardous
]


def create_colormap(vmax: int) -> LinearSegmentedColormap:
    """Create a colormap for PM2.5 values."""
    # 1. Filter levels that are below our VMAX
    valid_levels = [lvl for lvl in PM25_LEVELS if lvl[0] < vmax]
    
    # 2. Create the anchors for those levels
    anchors = [(val/vmax, col) for val, col in valid_levels]
    
    # 3. FORCE the final anchor to be exactly 1.0 using the next highest color
    # This fixes the "must end with x=1" error
    upper_colors = [lvl[1] for lvl in PM25_LEVELS if lvl[0] >= vmax]
    final_color = upper_colors[0] if upper_colors else PM25_LEVELS[-1][1]
    
    anchors.append((1.0, final_color))
    
    return LinearSegmentedColormap.from_list("SG_Haze", anchors)

class HTMLGenerator:
    """Generates a clean index.html file to host on GitHub Pages."""
    
    @staticmethod
    def _rgb_to_hex(rgb_tuple) -> str:
        """Convert RGB tuple (0-1 range) to hex color string."""
        r, g, b = rgb_tuple
        return '#{:02x}{:02x}{:02x}'.format(int(r * 255), int(g * 255), int(b * 255))
    
    @staticmethod
    def get_color_for_value(value: float, colormap: LinearSegmentedColormap, vmax: int = 250) -> str:
        """Return the color hex code for a given PM2.5 value using the actual heatmap colormap."""
        # Normalize value to 0-1 range based on vmax
        normalized = min(value / vmax, 1.0)
        # Get the interpolated color from the colormap
        rgb_color = colormap(normalized)
        # Convert to hex (ignore alpha channel)
        return HTMLGenerator._rgb_to_hex(rgb_color[:3])
    
    @staticmethod
    def generate_html_table(df: pd.DataFrame, regions: list, colormap: LinearSegmentedColormap, vmax: int = 250) -> str:
        """Generate an HTML table with color-coded cells."""
        df_table = df.sort_values('timestamp', ascending=False).copy()
        
        rows = []
        for _, row in df_table.iterrows():
            timestamp = row['timestamp']
            time_label = timestamp.strftime('%d %b %Y %H:%M')
            
            cells = []
            for region in regions:
                val = row[region]
                color = HTMLGenerator.get_color_for_value(val, colormap, vmax)
                
                # Dynamic text color (contrast check)
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                txt = "#ffffff" if lum < 0.5 else "#000000"
                
                cells.append(f'<td style="background-color: {color}; color: {txt}; font-weight: bold;">{val:.0f}</td>')
            
            rows.append(f'<tr><td>{time_label}</td>' + ''.join(cells) + '</tr>')
        
        header_cells = ['<th>Time</th>'] + [f'<th>{r.capitalize()}</th>' for r in regions]
        header_row = '<tr>' + ''.join(header_cells) + '</tr>'
        
        return f'''
        <div class="table-container">
            <table class="data-table">
                <thead>{header_row}</thead>
                <tbody>{"".join(rows)}</tbody>
            </table>
        </div>
        '''

    @staticmethod
    def generate(image_path: str, last_ts_str: str, output_path: str, df: pd.DataFrame = None, regions: list = None, colormap: LinearSegmentedColormap = None, vmax: int = 250):
        table_html = ""
        if df is not None and not df.empty:
            table_html = HTMLGenerator.generate_html_table(df, regions, colormap, vmax)
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SG PM2.5 Haze Heatmap</title>
            <link rel="stylesheet" href="style.css">
        </head>
        <body>
            <div class="card">
                <h1>🇸🇬 SG Haze Tracker</h1>
                <div class="legend">
                    <div class="item"><div class="dot" style="background:#228B22"></div>Good</div>
                    <div class="item"><div class="dot" style="background:#FFFF00"></div>Moderate</div>
                    <div class="item"><div class="dot" style="background:#FF8800"></div>Unhealthy</div>
                    <div class="item"><div class="dot" style="background:#800080"></div>Hazardous</div>
                </div>
                {table_html}
            </div>
            <div class="footer-fixed">
                <strong>Source:</strong> data.gov.sg API | 
                <strong>Data Freshness:</strong> {last_ts_str} (SGT)<br>
                Rendered on Lenovo X230 via GitHub Actions
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
            
        # 2. Create colormap for HTML table coloring
        colormap = create_colormap(config.vmax_pm25)
        
        # 3. Update HTML
        #last_ts = df['timestamp'].max().strftime('%Y-%m-%d %H:%M')
        last_ts = fetcher.fetch_freshness_from_db()
        HTMLGenerator.generate(
            config.output_image_name, 
            last_ts, 
            config.output_html_file,
            df=df,
            regions=config.regions,
            colormap=colormap,
            vmax=config.vmax_pm25
        )
        logger.info("Successfully updated index.html")
            
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())

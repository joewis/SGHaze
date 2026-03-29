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

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

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
    days_to_plot: int = 7  # Number of days to show in the heatmap
    
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

class HeatmapGenerator:
    """Handles the creation of the Seaborn heatmap image."""
    
    # PM2.5 thresholds (µg/m³) and their specific colors
    PM25_LEVELS = [
        (0, "#228B22"),   # Good
        (12, "#FFFF00"),  # Moderate (Low)
        (35, "#FFCC00"),  # Moderate (High)
        (55, "#FF8800"),  # Unhealthy (Low)
        (150, "#FF0000"), # Unhealthy (High)
        (250, "#800080")  # Hazardous
    ]

    def __init__(self, config: Config):
        self.config = config
        self.colormap = self._create_colormap()

    def _create_colormap(self) -> LinearSegmentedColormap:
        vmax = self.config.vmax_pm25
        
        # 1. Filter levels that are below our VMAX
        valid_levels = [lvl for lvl in self.PM25_LEVELS if lvl[0] < vmax]
        
        # 2. Create the anchors for those levels
        anchors = [(val/vmax, col) for val, col in valid_levels]
        
        # 3. FORCE the final anchor to be exactly 1.0 using the next highest color
        # This fixes the "must end with x=1" error
        upper_colors = [lvl[1] for lvl in self.PM25_LEVELS if lvl[0] >= vmax]
        final_color = upper_colors[0] if upper_colors else self.PM25_LEVELS[-1][1]
        
        anchors.append((1.0, final_color))
        
        return LinearSegmentedColormap.from_list("SG_Haze", anchors)

    def generate(self, df: pd.DataFrame) -> bool:
        """Renders the heatmap to a PNG file."""
        # Ensure we are sorted newest-to-oldest for vertical display
        df_plot = df.sort_values('timestamp', ascending=False)
        
        # Prepare the matrix
        heatmap_data = df_plot.set_index('timestamp')[self.config.regions]
        y_labels = [t.strftime('%a %d, %H:%M') for t in heatmap_data.index]
        x_labels = [r.capitalize() for r in self.config.regions]

        # Calculate height dynamically based on number of rows
        total_height = self.config.header_height_inches + (len(df_plot) * self.config.row_height_inches)
        
        fig = plt.figure(figsize=(self.config.figure_width_inches, total_height))
        gs = gridspec.GridSpec(2, 1, height_ratios=[0.4, len(df_plot) * self.config.row_height_inches], hspace=0.08)
        
        cax = fig.add_subplot(gs[0]) # Legend/Header
        ax = fig.add_subplot(gs[1])  # Heatmap
        
        sns.heatmap(
            heatmap_data, ax=ax, cbar_ax=cax, cmap=self.colormap,
            vmin=0, vmax=self.config.vmax_pm25,
            yticklabels=y_labels, xticklabels=x_labels,
            cbar_kws={'label': 'PM2.5 Concentration (µg/m³)', 'orientation': 'horizontal'},
            annot=True, fmt=".0f", annot_kws={"size": 9}, linewidths=0.2
        )
        
        # Formatting
        cax.set_title(f'Singapore PM2.5 Trends: Last {self.config.days_to_plot} Days', 
                      fontsize=18, pad=20, fontweight='bold')
        ax.xaxis.tick_top()
        ax.xaxis.set_label_position('top')
        plt.setp(ax.get_xticklabels(), fontsize=12, fontweight='bold')
        
        plt.savefig(self.config.output_image_name, dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        return True

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
        """Generate an HTML table with color-coded cells matching the heatmap."""
        # Sort data newest to oldest to match heatmap
        df_table = df.sort_values('timestamp', ascending=False).copy()
        
        # Build table rows
        rows = []
        for _, row in df_table.iterrows():
            timestamp = row['timestamp']
            time_label = timestamp.strftime('%a %d, %H:%M')
            
            cells = []
            for region in regions:
                value = row[region]
                color = HTMLGenerator.get_color_for_value(value, colormap, vmax)
                # Use white text for darker colors, black for lighter ones
                # Check luminance to determine text color
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                text_color = "#ffffff" if luminance < 0.5 else "#000000"
                cells.append(f'<td style="background-color: {color}; color: {text_color}; text-align: center; font-weight: bold; padding: 6px; min-width: 45px;">{value:.0f}</td>')
            
            rows.append(f'<tr><td style="font-weight: bold; padding: 6px; white-space: nowrap; font-size: 0.8rem;">{time_label}</td>' + ''.join(cells) + '</tr>')
        
        # Build header row
        header_cells = [f'<th style="padding: 8px; background-color: #333; color: white; font-size: 0.8rem;">Time</th>']
        for region in regions:
            header_cells.append(f'<th style="padding: 8px; background-color: #333; color: white; font-size: 0.8rem; min-width: 45px;">{region.capitalize()}</th>')
        header_row = '<tr>' + ''.join(header_cells) + '</tr>'
        
        table_html = f'''
        <div style="overflow-x: auto; margin-top: 20px; -webkit-overflow-scrolling: touch;">
            <table style="border-collapse: collapse; width: auto; max-width: 100%; font-family: -apple-system, sans-serif; font-size: 0.85rem;" role="table">
                {header_row}
                {''.join(rows)}
            </table>
        </div>
        '''
        return table_html
    
    @staticmethod
    def generate(image_path: str, last_ts_str: str, output_path: str, df: pd.DataFrame = None, regions: list = None, colormap: LinearSegmentedColormap = None, vmax: int = 250, include_image: bool = True):
        # Generate the data table if dataframe is provided
        table_html = ""
        if df is not None and regions is not None and colormap is not None and not df.empty:
            table_html = HTMLGenerator.generate_html_table(df, regions, colormap, vmax)
        
        # Image tag - only include if requested
        image_section = ""
        if include_image:
            image_section = f'<img src="{image_path}?t={int(datetime.now().timestamp())}" alt="PM2.5 Heatmap">'
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SG PM2.5 Tracker</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }}
                .card {{ background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); padding: 20px; max-width: 1000px; width: 100%; }}
                h1 {{ font-size: 1.5rem; margin-top: 0; color: #1c1e21; text-align: center; }}
                h2 {{ font-size: 1.2rem; margin-top: 20px; color: #1c1e21; text-align: center; }}
                img {{ width: 100%; height: auto; border-radius: 4px; }}
                .meta {{ margin-top: 15px; font-size: 0.85rem; color: #65676b; text-align: center; border-top: 1px solid #eee; padding-top: 15px; }}
                .legend {{ display: flex; justify-content: center; gap: 15px; margin-bottom: 20px; font-size: 0.8rem; font-weight: 600; flex-wrap: wrap; }}
                .item {{ display: flex; align-items: center; gap: 5px; }}
                .dot {{ height: 10px; width: 10px; border-radius: 50%; }}
                @media (max-width: 600px) {{
                    .card {{ padding: 10px; }}
                    h1 {{ font-size: 1.2rem; }}
                    h2 {{ font-size: 1rem; }}
                    .legend {{ gap: 10px; font-size: 0.7rem; }}
                }}
            </style>
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
                {image_section}
                <h2>📊 Data Table</h2>
                {table_html}
                <div class="meta">
                    <strong>Source:</strong> data.gov.sg API<br>
                    <strong>Data Freshness:</strong> {last_ts_str} (SGT)<br>
                    Generated via GitHub Actions
                </div>
            </div>
        </body>
        </html>
        """
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(html_template)

def main():
    config = Config()
    fetcher = DatabaseFetcher(config)
    generator = HeatmapGenerator(config)
    
    try:
        # 1. Get Data
        df = fetcher.fetch_data()
        if df.empty:
            return 1
            
        # 2. Render Heatmap
        success = generator.generate(df)
        
        # 3. Update HTML
        if success:
            #last_ts = df['timestamp'].max().strftime('%Y-%m-%d %H:%M')
            last_ts = fetcher.fetch_freshness_from_db()
            HTMLGenerator.generate(
                config.output_image_name, 
                last_ts, 
                config.output_html_file,
                df=df,
                regions=config.regions,
                colormap=generator.colormap,
                vmax=config.vmax_pm25,
                include_image=False
            )
            logger.info("Successfully updated heatmap and index.html")
            
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())

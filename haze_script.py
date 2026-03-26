"""
SG PM2.5 Haze Heatmap Generator

This script fetches PM2.5 data from data.gov.sg API, generates heatmaps,
and creates an HTML page for visualization.

Author: [Your Name]
License: MIT
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration parameters for the haze script."""
    # Number of days to fetch data for
    days_to_fetch: int = 14
    
    # API settings
    api_base_url: str = "https://api-open.data.gov.sg/v2/real-time/api/pm25"
    api_timeout: int = 10
    api_delay_between_requests: float = 3.0
    
    # Visualization settings
    regions: list = None
    vmax_pm25: int = 300
    row_height_inches: float = 0.28
    header_height_inches: float = 3.0
    figure_width_inches: float = 10.0
    dpi: int = 110
    
    # Output settings
    output_image_prefix: str = "haze"
    output_html_file: str = "index.html"
    
    def __post_init__(self):
        if self.regions is None:
            self.regions = ['west', 'north', 'central', 'south', 'east']


@dataclass
class APIResponse:
    """Container for API response data."""
    anchor_time: Optional[pd.Timestamp]
    last_updated_str: str
    historical_data: list


class PM25DataFetcher:
    """Handles fetching PM2.5 data from the API."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def fetch_latest_anchor(self) -> tuple[pd.Timestamp, str]:
        """
        Fetch the latest available data point from the API.
        
        Returns:
            Tuple of (anchor_time, last_updated_str)
            
        Raises:
            RuntimeError: If unable to fetch data from API
        """
        logger.info("Fetching latest available data point from API...")
        
        try:
            response = requests.get(
                self.config.api_base_url,
                timeout=self.config.api_timeout
            )
            response.raise_for_status()
            res = response.json()
            
            items = res.get('data', {}).get('items', [])
            if not items:
                raise ValueError("No items returned in API response")
            
            latest_item = items[0]
            anchor_time = pd.to_datetime(latest_item.get('timestamp'))
            last_updated_str = latest_item.get('updatedTimestamp', str(anchor_time))
            
            logger.info(f"Anchor time found: {anchor_time}")
            return anchor_time, last_updated_str
            
        except requests.RequestException as e:
            logger.error(f"Network error while fetching latest data: {e}")
            raise RuntimeError(f"Failed to fetch latest data: {e}")
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Invalid API response format: {e}")
            raise RuntimeError(f"Invalid API response: {e}")
    
    def fetch_historical_data(self, anchor_time: pd.Timestamp) -> list[dict]:
        """
        Fetch historical PM2.5 data for the specified number of days.
        
        Args:
            anchor_time: Starting point for fetching historical data
            
        Returns:
            List of data records with timestamp and regional readings
        """
        logger.info(f"Fetching historical data for {self.config.days_to_fetch} days...")
        
        # Generate unique dates to fetch
        dates_to_fetch = sorted(set(
            (anchor_time - timedelta(days=i)).strftime('%Y-%m-%d')
            for i in range(self.config.days_to_fetch)
        ))
        
        all_data = []
        for i, date_str in enumerate(dates_to_fetch, 1):
            url = f"{self.config.api_base_url}?date={date_str}"
            logger.info(f"[{i}/{len(dates_to_fetch)}] Fetching: {url}")
            
            try:
                time.sleep(self.config.api_delay_between_requests)
                response = requests.get(url, timeout=self.config.api_timeout)
                
                if response.status_code != 200:
                    logger.warning(f"HTTP {response.status_code} for {date_str}, skipping")
                    continue
                
                items = response.json().get('data', {}).get('items', [])
                
                for item in items:
                    row = {'timestamp': item.get('timestamp')}
                    readings = item.get('readings', {}).get('pm25_one_hourly', {})
                    row.update(readings)
                    all_data.append(row)
                    
            except requests.RequestException as e:
                logger.warning(f"Error fetching {date_str}: {e}")
            except (KeyError, TypeError) as e:
                logger.warning(f"Invalid data format for {date_str}: {e}")
        
        logger.info(f"Fetched {len(all_data)} data points")
        return all_data
    
    def fetch_all_data(self) -> APIResponse:
        """
        Fetch both latest anchor and historical data.
        
        Returns:
            APIResponse containing all fetched data
        """
        anchor_time, last_updated_str = self.fetch_latest_anchor()
        historical_data = self.fetch_historical_data(anchor_time)
        
        return APIResponse(
            anchor_time=anchor_time,
            last_updated_str=last_updated_str,
            historical_data=historical_data
        )


class DataProcessor:
    """Handles data processing and transformation."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def process_raw_data(self, raw_data: list[dict]) -> pd.DataFrame:
        """
        Process raw API data into a clean DataFrame.
        
        Args:
            raw_data: List of dictionaries from API
            
        Returns:
            Cleaned and processed DataFrame
        """
        if not raw_data:
            logger.warning("No data to process")
            return pd.DataFrame()
        
        df = pd.DataFrame(raw_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').drop_duplicates('timestamp')
        
        # Validate that all regions are present
        missing_regions = set(self.config.regions) - set(df.columns)
        if missing_regions:
            logger.warning(f"Missing region columns: {missing_regions}")
        
        logger.info(f"Processed {len(df)} unique timestamps")
        return df


class HeatmapGenerator:
    """Handles heatmap visualization generation."""
    
    def __init__(self, config: Config):
        self.config = config
        self.colormap = self._create_colormap()
    
    def _create_colormap(self) -> LinearSegmentedColormap:
        """Create custom colormap for PM2.5 levels."""
        vmax = self.config.vmax_pm25
        anchors = [
            (0/vmax,   "#228B22"),
            (12/vmax,  "#66DD00"),
            (35/vmax,  "#FFFF00"),
            (75/vmax,  "#FF8800"),
            (150/vmax, "#FF0000"),
            (250/vmax, "#800080"),
            (300/vmax, "#800000")
        ]
        return LinearSegmentedColormap.from_list("SG_Haze_Scale", anchors)
    
    def generate_vertical_heatmap(
        self,
        df: pd.DataFrame,
        anchor_time: pd.Timestamp,
        days: int,
        filename: str
    ) -> bool:
        """
        Generate a vertical heatmap visualization.
        
        Args:
            df: Processed DataFrame with PM2.5 data
            anchor_time: Reference timestamp
            days: Number of days to include
            filename: Output filename for the image
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Generating heatmap for last {days} day(s)...")
        
        # Filter data for the specified time range
        cutoff = anchor_time - pd.Timedelta(days=days)
        df_filtered = df[df['timestamp'] >= cutoff].copy()
        df_filtered = df_filtered.sort_values('timestamp', ascending=False)
        
        if df_filtered.empty or len(df_filtered) < 2:
            logger.warning("Insufficient data for heatmap generation")
            return False
        
        # Prepare heatmap data
        heatmap_data = df_filtered.set_index('timestamp')[self.config.regions]
        y_labels = [t.strftime('%a %H:%M') for t in heatmap_data.index]
        
        # Calculate figure dimensions
        total_height = (
            self.config.header_height_inches +
            len(df_filtered) * self.config.row_height_inches
        )
        
        # Create figure with GridSpec
        fig = plt.figure(figsize=(self.config.figure_width_inches, total_height))
        gs = gridspec.GridSpec(
            2, 1,
            height_ratios=[1.2, len(df_filtered) * self.config.row_height_inches],
            hspace=0.15
        )
        
        cax = fig.add_subplot(gs[0])  # Header axis
        ax = fig.add_subplot(gs[1])   # Heatmap axis
        
        # Generate heatmap
        sns.heatmap(
            heatmap_data,
            ax=ax,
            cbar_ax=cax,
            cmap=self.colormap,
            vmin=0,
            vmax=self.config.vmax_pm25,
            yticklabels=y_labels,
            xticklabels=[r.capitalize() for r in self.config.regions],
            cbar_kws={
                'label': 'PM2.5 Concentration',
                'orientation': 'horizontal'
            },
            annot=True,
            fmt=".0f",
            annot_kws={"size": 10},
            linewidths=0.5
        )
        
        # Configure title and labels
        cax.set_title(
            f'SG PM2.5: Latest {days} Day(s) (Newest on Top)',
            fontsize=18,
            pad=25,
            fontweight='bold'
        )
        
        ax.xaxis.tick_top()
        ax.xaxis.set_label_position('top')
        
        plt.setp(ax.get_xticklabels(), fontsize=13, fontweight='bold')
        plt.setp(ax.get_yticklabels(), fontsize=10, rotation=0)
        
        # Save figure
        plt.savefig(filename, dpi=self.config.dpi, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Heatmap saved to: {filename}")
        return True


class HTMLGenerator:
    """Handles HTML page generation."""
    
    @staticmethod
    def generate_html(
        image_filename: str,
        last_updated: str,
        output_path: str
    ) -> None:
        """
        Generate an HTML page displaying the heatmap.
        
        Args:
            image_filename: Name of the heatmap image file
            last_updated: Last update timestamp string
            output_path: Path to save the HTML file
        """
        logger.info(f"Generating HTML page: {output_path}")
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SG Haze Heatmap</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            text-align: center; 
            background: #f0f2f5; 
            margin: 0; 
            padding: 10px; 
            color: #1c1e21;
        }}
        .container {{ 
            max-width: 600px;
            margin: 10px auto; 
            background: white; 
            padding: 15px; 
            border-radius: 12px; 
            box-shadow: 0 2px 12px rgba(0,0,0,0.08); 
        }}
        h1 {{ font-size: 1.4rem; margin-bottom: 5px; }}
        .intro-text {{ color: #606770; font-size: 0.85rem; margin-bottom: 15px; }}
        
        .img-container {{
            width: 100%;
            margin-top: 10px;
        }}

        img {{ 
            width: 100%;
            height: auto; 
            border-radius: 8px;
            border: 1px solid #eee;
        }}
        
        select {{ 
            padding: 12px; 
            font-size: 16px; 
            border-radius: 8px; 
            border: 1px solid #ddd; 
            background: #fff;
            width: 100%;
            max-width: 280px;
        }}
        
        .controls {{ margin: 15px 0; }}
        .footer {{ color: #8d949e; font-size: 0.75rem; margin-top: 20px; line-height: 1.4; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>SG PM2.5 Haze Heatmap</h1>

        <div class="img-container">
            <img id="heatmap" src="{image_filename}" alt="PM2.5 Heatmap">
        </div>
        
        <div class="footer">
            Last updated: {last_updated}<br>
            Data provided by NEA via data.gov.sg
        </div>
    </div>

    <script>
        function updateImage() {{
            var select = document.getElementById('timeframe');
            var img = document.getElementById('heatmap');
            img.src = select.value + '?t=' + new Date().getTime();
        }}
    </script>
</body>
</html>
"""
        
        try:
            with open(output_path, "w", encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"HTML page saved to: {output_path}")
        except IOError as e:
            logger.error(f"Failed to write HTML file: {e}")
            raise


def main():
    """Main entry point for the haze script."""
    logger.info("=" * 60)
    logger.info("Starting SG PM2.5 Haze Heatmap Generator")
    logger.info("=" * 60)
    
    try:
        # Initialize components
        config = Config()
        fetcher = PM25DataFetcher(config)
        processor = DataProcessor(config)
        heatmap_gen = HeatmapGenerator(config)
        
        # Fetch data
        api_response = fetcher.fetch_all_data()
        
        # Process data
        df = processor.process_raw_data(api_response.historical_data)
        
        if df.empty:
            logger.error("No data available after processing. Exiting.")
            return 1
        
        # Generate heatmap
        image_filename = f"{config.output_image_prefix}_{config.days_to_fetch}d.png"
        success = heatmap_gen.generate_vertical_heatmap(
            df=df,
            anchor_time=api_response.anchor_time,
            days=config.days_to_fetch,
            filename=image_filename
        )
        
        if not success:
            logger.error("Failed to generate heatmap")
            return 1
        
        # Generate HTML page
        HTMLGenerator.generate_html(
            image_filename=image_filename,
            last_updated=api_response.last_updated_str,
            output_path=config.output_html_file
        )
        
        logger.info("=" * 60)
        logger.info("Successfully completed all tasks!")
        logger.info("=" * 60)
        return 0
        
    except Exception as e:
        logger.exception(f"Unexpected error occurred: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

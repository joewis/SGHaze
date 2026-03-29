# 🇸🇬 Singapore PM2.5 Haze Tracker

A lightweight, automated system for tracking and visualizing Singapore's air quality (PM2.5 levels) using data from [data.gov.sg](https://data.gov.sg).

## Overview

This project fetches hourly PM2.5 readings from Singapore's National Environment Agency (NEA) via the [data.gov.sg API](https://api-open.data.gov.sg/v2/real-time/api/pm25), stores them in a local SQLite database, and generates a color-coded heatmap visualization showing pollution trends across five regions over the past 7 days.

The entire pipeline runs automatically via **GitHub Actions** on an hourly schedule, with results published to **GitHub Pages**.

## Features

- **Automated Data Collection**: Hourly sync with data.gov.sg API
- **Historical Database**: SQLite storage for trend analysis
- **Visual Heatmap**: Color-coded PM2.5 levels by region (West, North, Central, South, East)
- **Web Dashboard**: Clean HTML page hosted on GitHub Pages
- **Lightweight**: Designed to run efficiently on minimal infrastructure

## Project Structure

```
├── fetch_pm25.py       # Data fetching script - pulls PM2.5 data from API
├── haze_script.py      # Visualization script - generates heatmap & HTML
├── sg_haze.db          # SQLite database with historical readings
├── haze_latest.png     # Generated heatmap image
├── index.html          # Web dashboard (GitHub Pages)
├── requirements.txt    # Python dependencies
└── .github/workflows/  # GitHub Actions CI/CD configuration
```

## How It Works

### 1. Data Fetching (`fetch_pm25.py`)
- Connects to `https://api-open.data.gov.sg/v2/real-time/api/pm25`
- Backfills data from January 1, 2025 (or last known timestamp)
- Stores readings in `sg_haze.db` with columns for each region
- Implements rate limiting to respect API quotas

### 2. Visualization (`haze_script.py`)
- Reads the latest 7 days of data from the database
- Generates a vertical heatmap using Seaborn/Matplotlib
- Color coding follows NEA PSI standards:
  - 🟢 **Good**: 0-12 µg/m³
  - 🟡 **Moderate**: 12-35 µg/m³
  - 🟠 **Unhealthy**: 35-150 µg/m³
  - 🔴 **Very Unhealthy**: 150-250 µg/m³
  - 🟣 **Hazardous**: 250+ µg/m³
- Updates `index.html` with fresh data and timestamp

### 3. Automation (GitHub Actions)
- Runs hourly via cron schedule (`47 * * * *`)
- Commits updated assets (PNG, DB, HTML) to the `main` branch
- Triggers GitHub Pages rebuild for live updates

## Installation & Local Usage

### Prerequisites
- Python 3.10+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/sg-haze-tracker.git
cd sg-haze-tracker

# Install dependencies
pip install -r requirements.txt
```

### Running Locally

```bash
# Step 1: Fetch latest data from API
python fetch_pm25.py

# Step 2: Generate heatmap and HTML
python haze_script.py
```

Open `index.html` in your browser to view the dashboard.

## Configuration

Edit `haze_script.py` to customize:

```python
@dataclass
class Config:
    days_to_plot: int = 7           # Number of days in heatmap
    vmax_pm25: int = 250            # Max color scale value
    row_height_inches: float = 0.25 # Heatmap row height
    figure_width_inches: float = 11.0
    dpi: int = 120
```

## Data Source

- **API**: [data.gov.sg - PM2.5 Real-time](https://api-open.data.gov.sg/v2/real-time/api/pm25)
- **Update Frequency**: Hourly
- **Regions Covered**: West, North, Central, South, East

## License

MIT License - feel free to use and modify.

## Acknowledgments

- Data provided by [National Environment Agency (NEA)](https://www.nea.gov.sg) via [data.gov.sg](https://data.gov.sg)
- Built with Python, Pandas, Seaborn, and Matplotlib

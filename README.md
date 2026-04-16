# 🇸🇬 Singapore PM2.5 Haze Tracker

A lightweight, real-time dashboard for tracking and visualizing Singapore's air quality (PM2.5 levels) using data from [data.gov.sg](https://data.gov.sg).

**🌐 Live Dashboard:** [View Website](https://joewis.github.io/SGHaze/) *(replace with your actual GitHub Pages URL)*

## Overview

This project fetches hourly PM2.5 readings from Singapore's National Environment Agency (NEA) via the [data.gov.sg API](https://api-open.data.gov.sg/v2/real-time/api/pm25), stores them in a local SQLite database, and displays them in an interactive web dashboard using **sql.js** and **Tabulator**. The dashboard features a swipeable card layout powered by **Swiper**.

The entire pipeline runs automatically via **GitHub Actions** every 15 minutes, with results published to **GitHub Pages**.

## Features

- **Automated Data Collection**: Sync with data.gov.sg API every 15 minutes
- **Historical Database**: SQLite storage for trend analysis
- **Interactive Web Dashboard**: 
  - Real-time PM2.5 table view with Tabulator
  - Swipeable card interface using Swiper.js
  - Color-coded PM2.5 levels by region (West, North, Central, South, East)
  - Mobile-friendly responsive design
- **Client-Side Processing**: Uses sql.js to read SQLite database directly in the browser
- **Lightweight**: Designed to run efficiently on minimal infrastructure

## Project Structure

```
├── fetch_pm25.py       # Data fetching script - pulls PM2.5 data from API
├── sg_haze.db          # SQLite database with historical readings
├── index.html          # Web dashboard (GitHub Pages)
├── app.js              # Client-side logic for loading DB and rendering table
├── swiper-layout.js    # Swiper carousel configuration
├── styles.css          # Dashboard styling
├── requirements.txt    # Python dependencies
└── .github/workflows/  # GitHub Actions CI/CD configuration
```

## How It Works

### 1. Data Fetching (`fetch_pm25.py`)
- Connects to `https://api-open.data.gov.sg/v2/real-time/api/pm25`
- Backfills data from January 1, 2025 (or last known timestamp)
- Stores readings in `sg_haze.db` with columns for each region
- Implements rate limiting to respect API quotas

### 2. Client-Side Dashboard (`app.js`, `swiper-layout.js`)
- **sql.js**: Loads and queries the SQLite database directly in the browser
- **Tabulator**: Renders an interactive, sortable table of PM2.5 readings
- **Swiper.js**: Provides swipeable card navigation for mobile-friendly UX
- Color coding follows NEA PSI standards:
  - 🟢 **Good**: 0-12 µg/m³
  - 🟡 **Moderate**: 12-35 µg/m³
  - 🟠 **Unhealthy**: 35-150 µg/m³
  - 🟣 **Hazardous**: 150+ µg/m³

### 4. Automation (GitHub Actions)
- Runs hourly via cron schedule
- Commits updated assets (DB) to the `main` branch
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

# Step 2: Generate database and HTML
python haze_script.py

# Step 3: Serve locally (optional, for testing)
# Use any static file server, e.g.:
python -m http.server 8000
```

Open `http://localhost:8000` in your browser to view the dashboard.

## Configuration

Edit `haze_script.py` to customize data processing and output settings.

## Data Source

- **API**: [data.gov.sg - PM2.5 Real-time](https://api-open.data.gov.sg/v2/real-time/api/pm25)
- **Update Frequency**: Every 15 minutes
- **Regions Covered**: West, North, Central, South, East

## License

MIT License - feel free to use and modify.

## Acknowledgments

- Data provided by [National Environment Agency (NEA)](https://www.nea.gov.sg) via [data.gov.sg](https://data.gov.sg)
- Built with Python, Pandas, sql.js, Tabulator, and Swiper.js

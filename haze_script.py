import requests
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from datetime import datetime, timedelta
import matplotlib.gridspec as gridspec

# --- 1. FIND THE ANCHOR (Latest Available Data) ---
print("Checking API for the latest available data point...")
latest_url = "https://api-open.data.gov.sg/v2/real-time/api/pm25"
try:
    res = requests.get(latest_url, timeout=10).json()
    # The API returns an array in 'items', get the first one
    latest_item = res.get('data', {}).get('items', [])[0]
    anchor_time = pd.to_datetime(latest_item.get('timestamp'))
    last_updated_str = latest_item.get('updatedTimestamp', anchor_time)
    print(f"Anchor Time found: {anchor_time}")
except Exception as e:
    print(f"Could not fetch latest. Error: {e}")
    raise

# --- 2. FETCH HISTORICAL DATA ---
# Based on the anchor, we need the last 7 days of dates
dates_to_fetch = [(anchor_time - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)]

all_data = []
for date_str in set(dates_to_fetch): # Use set to avoid duplicates if anchor is near midnight
    url = f"https://api-open.data.gov.sg/v2/real-time/api/pm25?date={date_str}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            items = response.json().get('data', {}).get('items', [])
            for item in items:
                row = {'timestamp': item.get('timestamp')}
                row.update(item.get('readings', {}).get('pm25_one_hourly', {}))
                all_data.append(row)
    except Exception as e:
        print(f"Error fetching {date_str}: {e}")
df_master = pd.DataFrame(all_data)
df_master['timestamp'] = pd.to_datetime(df_master['timestamp'])
df_master = df_master.sort_values('timestamp').drop_duplicates('timestamp')

df = df_master

regions = ['west', 'north', 'central', 'south', 'east']
heatmap_data = df.set_index('timestamp')[regions].T
clean_labels = [t.strftime('%d %b %H:%M') for t in heatmap_data.columns]

vmax_full = 300 
anchors = [
    (0/vmax_full,   "#228B22"), (12/vmax_full,  "#66DD00"),
    (35/vmax_full,  "#FFFF00"), (75/vmax_full,  "#FF8800"),
    (150/vmax_full, "#FF0000"), (250/vmax_full, "#800080"),
    (300/vmax_full, "#800000")
]
custom_cmap = LinearSegmentedColormap.from_list("SG_Haze_Scale", anchors)

def generate_vertical_heatmap(days, filename):
    cutoff = anchor_time - pd.Timedelta(days=days)
    df = df_master[df_master['timestamp'] >= cutoff].copy()
    df = df.sort_values('timestamp', ascending=False)
    
    if df.empty or len(df) < 2:
        return

    heatmap_data = df.set_index('timestamp')[regions]
    # Include date in the label to distinguish between different days
    y_labels = [t.strftime('%a %d/%m %H:%M') for t in heatmap_data.index]

    # --- LINEAR SCALING: 0.28 inches per row + 3 inches for headers ---
    row_height = 0.28
    header_area = 3.0
    total_height = header_area + (len(df) * row_height)
    
    fig = plt.figure(figsize=(10, total_height))
    
    # GridSpec: row 0 is for colorbar/title, row 1 is for data
    # We use 'hspace' to create a fixed gap between the legend and the blocks
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.2, len(df) * row_height], hspace=0.15)
    
    cax = fig.add_subplot(gs[0])  # Header axis
    ax = fig.add_subplot(gs[1])   # Heatmap axis

    # Generate Heatmap
    sns.heatmap(heatmap_data, 
                ax=ax,
                cbar_ax=cax,
                cmap=custom_cmap, 
                vmin=0, vmax=300,
                yticklabels=y_labels,
                xticklabels=[r.capitalize() for r in regions],
                cbar_kws={'label': 'PM2.5 Concentration', 'orientation': 'horizontal'},
                annot=True, fmt=".0f", annot_kws={"size": 10},
                linewidths=.5)

    # --- FIX 1: Explicit Title on the Header Axis ---
    cax.set_title(f'SG PM2.5: Latest {days} Day(s) (Newest on Top)', 
                  fontsize=18, pad=25, fontweight='bold')
    
    # Move X-ticks to the top of the heatmap blocks
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position('top')
    
    # --- FIX 2: Formatting cleanup ---
    plt.setp(ax.get_xticklabels(), fontsize=13, fontweight='bold')
    plt.setp(ax.get_yticklabels(), fontsize=8, rotation=0)
    
    # Remove 'tight_layout' as it breaks GridSpec ratios; use bbox_inches instead
    plt.savefig(filename, dpi=110, bbox_inches='tight')
    plt.close()

# --- EXECUTION ---
for d in [14]:
    generate_vertical_heatmap(d, f'haze_{d}d.png')
    print(f"Generated vertical haze_{d}d.png (Newest first)")
    
# --- 5. CREATE THE WEBPAGE (CLEAN VERTICAL VERSION) ---
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
            max-width: 600px; /* Narrower container for vertical flow */
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
            width: 100%; /* Image fills the container width */
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
            <img id="heatmap" src="haze_14d.png" alt="PM2.5 Heatmap">
        </div>
        
        <div class="footer">
            Last updated: {last_updated_str}<br>
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

with open("index.html", "w") as f:
    f.write(html_content)

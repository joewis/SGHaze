import json
import logging
from matplotlib.colors import LinearSegmentedColormap

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
VMAX = 250
OUTPUT_FILE = "pm25_map.json"

# Your specific threshold anchors
PM25_LEVELS = [
    (0, "#228B22"),   # Good
    (12, "#FFFF00"),  # Moderate (Low)
    (35, "#FFCC00"),  # Moderate (High)
    (55, "#FF8800"),  # Unhealthy (Low)
    (150, "#FF0000"), # Unhealthy (High)
    (250, "#800080")  # Hazardous
]

def create_colormap(vmax: int) -> LinearSegmentedColormap:
    """Creates a smooth gradient map based on PM25_LEVELS."""
    valid_levels = [lvl for lvl in PM25_LEVELS if lvl[0] < vmax]
    anchors = [(val/vmax, col) for val, col in valid_levels]
    
    # Ensure it ends at 1.0
    upper_colors = [lvl[1] for lvl in PM25_LEVELS if lvl[0] >= vmax]
    final_color = upper_colors[0] if upper_colors else PM25_LEVELS[-1][1]
    anchors.append((1.0, final_color))
    
    return LinearSegmentedColormap.from_list("SG_Haze", anchors)

def rgb_to_hex(rgb_tuple) -> str:
    r, g, b = rgb_tuple[:3]
    return '#{:02x}{:02x}{:02x}'.format(int(r * 255), int(g * 255), int(b * 255))

def generate():
    logger.info(f"Generating color mapping for 0-{VMAX}...")
    cmap = create_colormap(VMAX)
    
    mapping = {}
    for i in range(VMAX + 1):
        # Sample the colormap at the normalized position
        color_rgb = cmap(i / VMAX)
        mapping[i] = rgb_to_hex(color_rgb)
    
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        json.dump(mapping, f, indent=2)
    
    logger.info(f"Successfully saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    generate()

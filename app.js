document.addEventListener("DOMContentLoaded", async () => {
    const API_URL = "https://api-open.data.gov.sg/v2/real-time/api/pm25";
    const REGIONS = ['west', 'north', 'central', 'south', 'east'];
    const REFRESH_INTERVAL = 15 * 60 * 1000; // 15 minutes in milliseconds

    // Initial load of the color map (static, only needed once)
    let colorMap = {};
    try {
        const colorRes = await fetch('pm25_map.json');
        if (!colorRes.ok) throw new Error("Could not load color map");
        colorMap = await colorRes.json();
    } catch (error) {
        console.error("Critical Error: Color map failed to load", error);
    }

    /**
     * Main function to fetch API data and update UI components
     */
    async function refreshDashboard() {
        try {
            console.log(`Refreshing data from API... ${new Date().toLocaleTimeString()}`);
            const apiRes = await fetch(API_URL);
            
            if (apiRes.ok) {
                const apiData = await apiRes.json();
                
                // 1. Patch missing rows
                fillMissingData(apiData, REGIONS);
                
                // 2. Refresh the footer timestamp
                updateFooterFreshness(apiData);
                
                // 3. Re-apply colors to all rows (including new ones)
                applyHeatmapColors(colorMap);
            }
        } catch (error) {
            console.error("Background refresh failed:", error);
        }
    }

    // --- Start Execution ---
    
    // 1. Run immediately on load
    await refreshDashboard();

    // 2. Set the interval to run every 15 minutes
    setInterval(refreshDashboard, REFRESH_INTERVAL);
});

/**
 * Inserts missing hourly slots by comparing API timestamps with existing table rows
 */
function fillMissingData(apiResponse, regions) {
    const tableBody = document.querySelector(".data-table tbody");
    if (!tableBody) return;

    // Get the timestamp of the newest row (ignoring any style tags or labels)
    const firstRowCell = tableBody.querySelector("tr td");
    const latestTableTime = firstRowCell ? new Date(firstRowCell.textContent).getTime() : 0;

    // Filter for items strictly newer than what is currently visible
    const missingItems = apiResponse.data.items
        .filter(item => new Date(item.timestamp).getTime() > latestTableTime)
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    missingItems.forEach(item => {
        const timestamp = new Date(item.timestamp);
        const timeLabel = formatTimestamp(timestamp);
        const readings = item.readings.pm25_one_hourly;

        const newRow = document.createElement("tr");
        let cellsHTML = `<td style="font-size: 0.75rem; color: #3498db; font-weight: 500;">${timeLabel}</td>`;
        
        regions.forEach(region => {
            const val = readings[region];
            cellsHTML += `<td class="pm25-val" style="text-align: center; font-weight: bold; padding: 4px 2px; min-width: 40px;">${val}</td>`;
        });

        newRow.innerHTML = cellsHTML;
        tableBody.insertBefore(newRow, tableBody.firstChild);
    });
}

/**
 * Updates the footer timestamp
 */
function updateFooterFreshness(apiResponse) {
    const items = apiResponse.data.items;
    const latestItem = items[items.length - 1];
    const updatedTs = new Date(latestItem.updatedTimestamp);
    const freshnessLabel = formatTimestamp(updatedTs);
    
    const footer = document.querySelector(".footer-fixed");
    if (!footer) return;

    footer.innerHTML = footer.innerHTML.replace(
        /<strong>Data Freshness:<\/strong> .*? \(SGT\)/,
        `<strong>Data Freshness:</strong> ${freshnessLabel} (SGT)`
    );
}

/**
 * Applies color coding to all cells with the .pm25-val class
 */
function applyHeatmapColors(colorMap) {
    const dataCells = document.querySelectorAll('.pm25-val');
    dataCells.forEach(cell => {
        const val = parseInt(cell.textContent, 10);
        if (!isNaN(val)) {
            const lookupValue = Math.min(Math.max(val, 0), 250);
            const bgColor = colorMap[lookupValue.toString()] || '#800080';
            
            cell.style.backgroundColor = bgColor;
            cell.style.color = getContrastTextColor(bgColor);
        }
    });
}

function formatTimestamp(date) {
    return date.toLocaleString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', hour12: false
    }).replace(',', '');
}

function getContrastTextColor(hex) {
    hex = hex.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.5 ? '#000000' : '#ffffff';
}

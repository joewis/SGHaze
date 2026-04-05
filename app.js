document.addEventListener("DOMContentLoaded", async () => {
    const API_URL = "https://api-open.data.gov.sg/v2/real-time/api/pm25";
    const REGIONS = ['west', 'north', 'central', 'south', 'east'];

    try {
        const [colorRes, apiRes] = await Promise.all([
            fetch('pm25_map.json'),
            fetch(API_URL)
        ]);

        if (!colorRes.ok) throw new Error("Could not load color map");
        const colorMap = await colorRes.json();

        if (apiRes.ok) {
            const apiData = await apiRes.json();
            
            // Task 1: Fill in missing hours
            fillMissingData(apiData, REGIONS);
            
            // Task 2: Update footer freshness
            updateFooterFreshness(apiData);
        }

        // Task 3: Apply colors
        applyHeatmapColors(colorMap);

    } catch (error) {
        console.error("Error updating dashboard:", error);
    }
});

/**
 * Inserts missing hourly slots without adding extra text labels
 */
function fillMissingData(apiResponse, regions) {
    const tableBody = document.querySelector(".data-table tbody");
    if (!tableBody) return;

    // 1. Get the timestamp of the newest row already in the table
    const firstRowTimeStr = tableBody.querySelector("tr td")?.textContent;
    const latestTableTime = firstRowTimeStr ? new Date(firstRowTimeStr).getTime() : 0;

    // 2. Filter and sort missing items (oldest to newest for correct prepending)
    const missingItems = apiResponse.data.items
        .filter(item => new Date(item.timestamp).getTime() > latestTableTime)
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    if (missingItems.length === 0) return;

    // 3. Prepend rows
    missingItems.forEach(item => {
        const timestamp = new Date(item.timestamp);
        const timeLabel = formatTimestamp(timestamp);
        const readings = item.readings.pm25_one_hourly;

        const newRow = document.createElement("tr");
        
        // Removed "(Live)" - using a subtle blue color for the timestamp instead
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
 * Updates the footer using the latest updatedTimestamp from the API
 */
function updateFooterFreshness(apiResponse) {
    // API items are usually chronological; get the last one for the most recent update
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
 * Standard color-coding logic
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

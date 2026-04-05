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
            
            // Task 1: Add the live data row to the table
            updateTableWithLatest(apiData, REGIONS);
            
            // Task 2: Update the data freshness in the footer
            updateFooterFreshness(apiData);
        }

        // Task 3: Apply the color coding
        applyHeatmapColors(colorMap);

    } catch (error) {
        console.error("Error updating dashboard:", error);
    }
});

/**
 * Prepends the latest 1-hour PM2.5 readings to the table
 */
function updateTableWithLatest(apiResponse, regions) {
    const item = apiResponse.data.items[0];
    const readings = item.readings.pm25_one_hourly;
    const timestamp = new Date(item.timestamp);
    const timeLabel = formatTimestamp(timestamp);

    const tableBody = document.querySelector(".data-table tbody");
    if (!tableBody) return;

    // Avoid duplicating if the first row is already this timestamp
    const firstRowTime = tableBody.querySelector("tr td")?.textContent;
    if (firstRowTime === timeLabel) return;

    const newRow = document.createElement("tr");
    let cellsHTML = `<td style="font-size: 0.75rem; color: #3498db; font-weight: bold;">${timeLabel}</td>`;
    
    regions.forEach(region => {
        const val = readings[region];
        cellsHTML += `<td class="pm25-val" style="text-align: center; font-weight: bold; padding: 4px 2px; min-width: 40px;">${val}</td>`;
    });

    newRow.innerHTML = cellsHTML;
    tableBody.insertBefore(newRow, tableBody.firstChild);
}

/**
 * Updates the "Data Freshness" field in the footer using the API's updatedTimestamp
 */
function updateFooterFreshness(apiResponse) {
    const item = apiResponse.data.items[0];
    const updatedTs = new Date(item.updatedTimestamp);
    const freshnessLabel = formatTimestamp(updatedTs);
    
    const footer = document.querySelector(".footer-fixed");
    if (!footer) return;

    // Updates only the text between "Data Freshness:" and "(SGT)"
    footer.innerHTML = footer.innerHTML.replace(
        /<strong>Data Freshness:<\/strong> .*? \(SGT\)/,
        `<strong>Data Freshness:</strong> ${freshnessLabel} (SGT)`
    );
}

/**
 * Applies background and text colors based on the JSON lookup table
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

/**
 * Helper: Format Date to "DD MMM YYYY HH:mm"
 */
function formatTimestamp(date) {
    return date.toLocaleString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', hour12: false
    }).replace(',', '');
}

/**
 * Helper: Determine if text should be black or white based on background brightness
 */
function getContrastTextColor(hex) {
    hex = hex.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.5 ? '#000000' : '#ffffff';
}

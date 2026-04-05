// Load sql.js from CDN
const SQL_LIB_URL = "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/sql-wasm.js";

document.addEventListener("DOMContentLoaded", async () => {
    const API_URL = "https://api-open.data.gov.sg/v2/real-time/api/pm25";
    const DB_PATH = "sg_haze.db";
    const REGIONS = ['west', 'north', 'central', 'south', 'east'];
    const DAYS_TO_PLOT = 7 * 16; // Number of days to show
    const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes in milliseconds

    let db = null;
    let colorMap = {};
    let SQL = null;

    // Initialize sql.js
    async function initSqlJs() {
        const response = await fetch(SQL_LIB_URL);
        if (!response.ok) throw new Error("Failed to load sql.js");
        const scriptContent = await response.text();
        
        // Create a blob and load it
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.textContent = scriptContent;
            script.onload = () => {
                // sql.js uses initSqlJs global function
                if (typeof initSqlJs !== 'undefined') {
                    resolve(initSqlJs({
                        locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}`
                    }));
                } else {
                    reject(new Error("sql.js not properly loaded"));
                }
            };
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    // Open database using XHR to fetch the file
    async function openDatabase(sqlInstance) {
        const response = await fetch(DB_PATH);
        if (!response.ok) throw new Error("Failed to load database");
        const buffer = await response.arrayBuffer();
        const arr = new Uint8Array(buffer);
        return new sqlInstance.Database(arr);
    }

    // Load color map
    async function loadColorMap() {
        try {
            const colorRes = await fetch('pm25_map.json');
            if (!colorRes.ok) throw new Error("Could not load color map");
            colorMap = await colorRes.json();
        } catch (error) {
            console.error("Critical Error: Color map failed to load", error);
        }
    }

    /**
     * Fetch latest data from API and update database with missing entries
     */
    async function syncWithAPI() {
        try {
            console.log(`Syncing with API... ${new Date().toLocaleTimeString()}`);
            const apiRes = await fetch(API_URL);
            
            if (!apiRes.ok) {
                console.error("API fetch failed:", apiRes.status);
                return;
            }

            const apiData = await apiRes.json();
            const items = apiData.data.items || [];
            
            if (items.length === 0) return;

            // Get the latest timestamp from the database
            const latestDbResult = db.exec("SELECT MAX(timestamp) as max_ts FROM pm25_readings");
            let latestDbTs = null;
            if (latestDbResult.length > 0 && latestDbResult[0].values.length > 0) {
                latestDbTs = latestDbResult[0].values[0][0];
            }

            // Find items that need to be inserted
            const itemsToInsert = items.filter(item => {
                if (!latestDbTs) return true;
                return item.timestamp > latestDbTs;
            });

            if (itemsToInsert.length === 0) {
                console.log("Database is up to date");
                return;
            }

            // Insert missing items
            const stmt = db.prepare(`
                INSERT OR REPLACE INTO pm25_readings (timestamp, west, north, central, south, east)
                VALUES (:timestamp, :west, :north, :central, :south, :east)
            `);

            for (const item of itemsToInsert) {
                const readings = item.readings.pm25_one_hourly;
                stmt.run({
                    ':timestamp': item.timestamp,
                    ':west': readings.west,
                    ':north': readings.north,
                    ':central': readings.central,
                    ':south': readings.south,
                    ':east': readings.east
                });
            }
            stmt.free();

            // Update sync_meta with latest API update timestamp
            const updatedTs = apiData.data.items[apiData.data.items.length - 1]?.updatedTimestamp;
            if (updatedTs) {
                db.run(`INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('last_api_update', :val)`, {
                    ':val': updatedTs
                });
            }

            console.log(`Inserted ${itemsToInsert.length} new records`);
        } catch (error) {
            console.error("API sync failed:", error);
        }
    }

    /**
     * Generate HTML table from database data
     */
    function generateTable() {
        const tableBody = document.querySelector(".data-table tbody");
        const tableHead = document.querySelector(".data-table thead");
        
        if (!tableBody || !tableHead) return;

        // Calculate cutoff date
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - DAYS_TO_PLOT);
        const cutoffStr = cutoffDate.toISOString();

        // Query data from database
        const result = db.exec(`
            SELECT timestamp, west, north, central, south, east 
            FROM pm25_readings 
            WHERE timestamp >= '${cutoffStr}'
            ORDER BY timestamp DESC
        `);

        if (result.length === 0 || result[0].values.length === 0) {
            console.log("No data found in database");
            return;
        }

        const rows = result[0].values;

        // Clear existing body
        tableBody.innerHTML = '';

        // Generate rows
        for (const row of rows) {
            const [timestamp, west, north, central, south, east] = row;
            const timeLabel = formatTimestamp(new Date(timestamp));
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight: 500; white-space: nowrap; font-size: 0.75rem;">${timeLabel}</td>
                <td class="pm25-val" style="text-align: center; font-weight: bold; padding: 4px 2px; min-width: 40px;">${west}</td>
                <td class="pm25-val" style="text-align: center; font-weight: bold; padding: 4px 2px; min-width: 40px;">${north}</td>
                <td class="pm25-val" style="text-align: center; font-weight: bold; padding: 4px 2px; min-width: 40px;">${central}</td>
                <td class="pm25-val" style="text-align: center; font-weight: bold; padding: 4px 2px; min-width: 40px;">${south}</td>
                <td class="pm25-val" style="text-align: center; font-weight: bold; padding: 4px 2px; min-width: 40px;">${east}</td>
            `;
            tableBody.appendChild(tr);
        }

        console.log(`Generated table with ${rows.length} rows`);
    }

    /**
     * Update footer with freshness info from database
     */
    function updateFooterFreshness() {
        const result = db.exec("SELECT value FROM sync_meta WHERE key = 'last_api_update'");
        
        if (result.length === 0 || result[0].values.length === 0) return;

        const lastUpdate = result[0].values[0][0];
        const freshnessLabel = formatTimestamp(new Date(lastUpdate));
        
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
    function applyHeatmapColors() {
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
     * Main refresh function - runs the complete workflow
     */
    async function refreshDashboard() {
        if (!db) return;
        
        // Step 1: Check API and update database with missing entries
        await syncWithAPI();
        
        // Step 2: Regenerate the HTML table from database
        generateTable();
        
        // Step 3: Update footer freshness
        updateFooterFreshness();
        
        // Step 4: Apply color coding
        applyHeatmapColors();
    }

    // --- Start Execution ---
    
    try {
        // Initialize sql.js
        SQL = await initSqlJs();
        console.log("sql.js initialized");

        // Open database
        db = await openDatabase(SQL);
        console.log("Database opened");

        // Load color map
        await loadColorMap();
        console.log("Color map loaded");

        // Run initial refresh
        await refreshDashboard();

        // Set interval for periodic refresh
        setInterval(refreshDashboard, REFRESH_INTERVAL);

    } catch (error) {
        console.error("Initialization failed:", error);
    }
});

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

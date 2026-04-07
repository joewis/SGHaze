document.addEventListener("DOMContentLoaded", async () => {
    const API_URL = "https://api-open.data.gov.sg/v2/real-time/api/pm25";
    const outputTable = document.getElementById('sql-output');
    
    let db; // The in-memory SQLite database
    let colorMap = {};

    async function initApp() {
        try {
            // 1. Initialize SQL.js and Color Map
            const [SQL, colorRes] = await Promise.all([
                initSqlJs({ locateFile: f => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}` }),
                fetch('pm25_map.json')
            ]);
            colorMap = await colorRes.json();

            // 2. Load the base .db file
            const dbRes = await fetch('sg_haze.db');
            const buf = await dbRes.arrayBuffer();
            db = new SQL.Database(new Uint8Array(buf));

            // 3. Initial sync and display
            await syncAndRender();

            // 4. Start the "Smart Scheduler"
            scheduleNextUpdate();

        } catch (err) {
            console.error("Initialization failed:", err);
        }
    }

    /**
     * Logic to fetch, update DB, and refresh UI
     */
    async function syncAndRender() {
        console.log(`[${new Date().toLocaleTimeString()}] Syncing with API...`);
        try {
            const apiRes = await fetch(API_URL);
            if (!apiRes.ok) throw new Error("API Offline");
            const apiData = await apiRes.json();

            // Find latest timestamp in our current memory DB
            const res = db.exec("SELECT MAX(timestamp) FROM pm25_readings");
            const latestDbTime = res[0].values[0][0] || "";

            // Filter for only truly new records
            const newItems = apiData.data.items.filter(item => item.timestamp > latestDbTime);

            if (newItems.length > 0) {
                const stmt = db.prepare("INSERT OR IGNORE INTO pm25_readings (timestamp, west, north, central, south, east) VALUES (?, ?, ?, ?, ?, ?)");
                newItems.forEach(item => {
                    const r = item.readings.pm25_one_hourly;
                    stmt.run([item.timestamp, r.west, r.north, r.central, r.south, r.east]);
                });
                stmt.free();
                console.log(`Added ${newItems.length} new records.`);
            }

            renderData();
        } catch (e) {
            console.warn("Sync failed, will retry next interval.", e);
        }
    }

    /**
     * Calculates the wait time until the next 15-minute window + 2 min buffer
     * Targets: XX:02, XX:17, XX:32, XX:47
     */
    function scheduleNextUpdate() {
        const now = new Date();
        const minutes = now.getMinutes();
        const seconds = now.getSeconds();
    
        // Targets: 2, 17, 32, 47
        const targets = [2, 17, 32, 47];
        let nextTarget = targets.find(t => t > minutes);
    
        let delay;
        if (nextTarget === undefined) {
            // If it's past 47 minutes, target is 02 minutes of the NEXT hour
            delay = ((60 - minutes + 2) * 60 - seconds) * 1000;
        } else {
            delay = ((nextTarget - minutes) * 60 - seconds) * 1000;
        }
    
        // Safety: Never allow a delay shorter than 60 seconds
        const safeDelay = Math.max(delay, 60000);
    
        console.log(`Next sync in ${Math.floor(safeDelay / 1000)}s`);
    
        setTimeout(async () => {
            await syncAndRender();
            scheduleNextUpdate(); // Only call again AFTER sync finishes
        }, safeDelay);
    }

    function renderData() {
        const contents = db.exec("SELECT timestamp, west, north, central, south, east FROM pm25_readings ORDER BY timestamp DESC LIMIT 100");
        if (contents.length === 0) return;

        outputTable.innerHTML = contents[0].values.map(row => `
            <tr>
                <td class="timestamp-cell">${formatTimestamp(new Date(row[0]))}</td>
                <td class="pm25-val">${row[1]}</td>
                <td class="pm25-val">${row[2]}</td>
                <td class="pm25-val">${row[3]}</td>
                <td class="pm25-val">${row[4]}</td>
                <td class="pm25-val">${row[5]}</td>
            </tr>
        `).join('');
        
        applyHeatmapColors();
    }

    function applyHeatmapColors() {
        document.querySelectorAll('.pm25-val').forEach(cell => {
            const val = parseInt(cell.textContent, 10);
            if (!isNaN(val)) {
                const lookup = Math.min(Math.max(val, 0), 250);
                const bgColor = colorMap[lookup.toString()] || '#800080';
                cell.style.backgroundColor = bgColor;
                cell.style.color = getContrastTextColor(bgColor);
            }
        });
    }

    function formatTimestamp(date) {
        return date.toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric', 
            hour: '2-digit', minute: '2-digit'
        }).replace(',', '');
    }

    function getContrastTextColor(hex) {
        const r = parseInt(hex.substring(1, 3), 16);
        const g = parseInt(hex.substring(3, 5), 16);
        const b = parseInt(hex.substring(5, 7), 16);
        return ((r*0.299 + g*0.587 + b*0.114) / 255) > 0.5 ? '#000' : '#fff';
    }

    initApp();
});

document.addEventListener("DOMContentLoaded", async () => {
    const API_URL = "https://corsproxy.io/?https://api-open.data.gov.sg/v2/real-time/api/pm25";
    let db;
    let colorMap = {};
    let table; // Tabulator instance

    async function initApp() {
        try {
            const [SQL, colorRes] = await Promise.all([
                initSqlJs({ locateFile: f => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}` }),
                fetch('pm25_map.json')
            ]);
            colorMap = await colorRes.json();

            const dbRes = await fetch('sg_haze.db');
            const buf = await dbRes.arrayBuffer();
            db = new SQL.Database(new Uint8Array(buf));

            initTable(); // Setup Tabulator
            await syncAndRender();
            scheduleNextUpdate();
        } catch (err) {
            console.error("Initialization failed:", err);
        }
    }

    function initTable() {
        // Define a common formatter for PM2.5 columns
        const pm25Formatter = (cell) => {
            const val = cell.getValue();
            if (val === null || val === undefined) return "";
            
            const lookup = Math.min(Math.max(val, 0), 250);
            const bgColor = colorMap[lookup.toString()] || '#800080';
            
            const el = cell.getElement();
            el.style.backgroundColor = bgColor;
            el.style.color = getContrastTextColor(bgColor);
            el.style.fontWeight = "bold";
            
            return val;
        };


table = new Tabulator("#haze-table", {
        height: "70vh",
        layout: "fitColumns",
	resizableColumnFit: true,
        placeholder: "Loading Data...",
        ajaxURL: "local", // A dummy URL is required to wake up the AJAX engine
        ajaxRequestFunc: function(url, config, params) {
            return new Promise((resolve, reject) => {
                try {
                    // Fallback to 1 and 50 just in case params are missing
                    const page = params.page || 1;
                    const size = params.size || 50;

                    const pageData = getPagedData(page, size);
                    resolve(pageData);
                } catch (err) {
                    console.error("Data fetch error:", err);
                    reject(err);
                }
            });
        },
        progressiveLoad: "scroll", // v5 setting for infinite scrolling
        paginationSize: 50,        // Number of rows fetched per scroll
        // ------------------------------

        columns: [
            {
                title: "Time",
                field: "timestamp",
		width: 125,
                headerSort: true,
                formatter: (cell) => formatTimestamp(new Date(cell.getValue()))
            },
            { title: "West", field: "west", headerSort: true, formatter: pm25Formatter, hozAlign: "center", resizable: false },
            { title: "North", field: "north", headerSort: true, formatter: pm25Formatter, hozAlign: "center", resizable: false },
            { title: "Central", field: "central", headerSort: true, formatter: pm25Formatter, hozAlign: "center", resizable: false },
            { title: "South", field: "south", headerSort: true, formatter: pm25Formatter, hozAlign: "center", resizable: false },
            { title: "East", field: "east", headerSort: true, formatter: pm25Formatter, hozAlign: "center", resizable: false },
        ],
    });
}



/**
 * Helper to fetch specific chunks of data from SQL
 */
function getPagedData(page, size) {
    const offset = (page - 1) * size;
    
    // Query to get the total count for Tabulator's pager
    const countRes = db.exec("SELECT COUNT(*) FROM pm25_readings");
    const lastPage = Math.ceil(countRes[0].values[0][0] / size);

    // Query for the specific "page" of data
    const contents = db.exec(`
        SELECT timestamp, west, north, central, south, east 
        FROM pm25_readings 
        ORDER BY timestamp DESC 
        LIMIT ${size} OFFSET ${offset}
    `);

    let data = [];
    if (contents.length > 0) {
        const columns = contents[0].columns;
        data = contents[0].values.map(row => {
            let obj = {};
            columns.forEach((col, i) => obj[col] = row[i]);
            return obj;
        });
    }

    return {
        last_page: lastPage,
        data: data
    };
}


    async function syncAndRender() {
        try {
            const apiRes = await fetch(API_URL);
            if (!apiRes.ok) throw new Error("API Offline");
            const apiData = await apiRes.json();

            const res = db.exec("SELECT MAX(timestamp) FROM pm25_readings");
            const latestDbTime = res[0].values[0][0] || "";
            const newItems = apiData.data.items.filter(item => item.timestamp => latestDbTime);

            if (newItems.length > 0) {
                const stmt = db.prepare("INSERT OR IGNORE INTO pm25_readings (timestamp, west, north, central, south, east) VALUES (?, ?, ?, ?, ?, ?)");
                newItems.forEach(item => {
                    const r = item.readings.pm25_one_hourly;
                    stmt.run([item.timestamp, r.west, r.north, r.central, r.south, r.east]);
                });
                stmt.free();
            }

            renderData();

            if (table) {
                table.setData(); // This re-triggers the ajaxRequestFunc
            }

	} catch (e) {
            console.warn("Sync failed", e);
            renderData(); // Render existing data even if sync fails
        }
    }

    function renderData() {
        // Fetch data from SQL and convert to Objects for Tabulator
        const contents = db.exec("SELECT timestamp, west, north, central, south, east FROM pm25_readings ORDER BY timestamp DESC LIMIT 500");
        
        if (contents.length > 0) {
            const columns = contents[0].columns;
            const data = contents[0].values.map(row => {
                let obj = {};
                columns.forEach((col, i) => obj[col] = row[i]);
                return obj;
            });

            table.setData(data); // Tabulator takes over the rendering
        }
    }

    // ... Keep your existing scheduleNextUpdate, formatTimestamp, and getContrastTextColor functions ...
    // (Ensure you use the fixed formatTimestamp with the comma after 'numeric')

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
    // Fetch data from SQL
    const contents = db.exec("SELECT timestamp, west, north, central, south, east FROM pm25_readings ORDER BY timestamp DESC LIMIT 500");
    
    if (contents.length > 0) {
        const columns = contents[0].columns;
        const data = contents[0].values.map(row => {
            let obj = {};
            columns.forEach((col, i) => obj[col] = row[i]);
            return obj;
        });

        // Use the Tabulator instance instead of outputTable
        if (table) {
            table.setData(data); 
        }
    }
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

document.addEventListener("DOMContentLoaded", async () => {
    try {
        // 1. Fetch the pre-generated JSON lookup table
        const response = await fetch('pm25_map.json');
        if (!response.ok) throw new Error("Could not load color map");
        
        const colorMap = await response.json();

        // 2. Helper function: Calculate if text should be black or white 
        // based on the background color's brightness for readability.
        function getContrastTextColor(hex) {
            // Remove the hash if it exists
            hex = hex.replace('#', '');
            const r = parseInt(hex.substring(0, 2), 16);
            const g = parseInt(hex.substring(2, 4), 16);
            const b = parseInt(hex.substring(4, 6), 16);
            
            // Standard relative luminance formula
            const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
            return luminance > 0.5 ? '#000000' : '#ffffff';
        }

        // 3. Find all table cells with the data class
        const dataCells = document.querySelectorAll('.pm25-val');

        // 4. Loop through each cell, read the number, and apply the color
        dataCells.forEach(cell => {
            // Parse the number from the cell's text
            const pm25Value = parseInt(cell.textContent, 10);
            
            if (!isNaN(pm25Value)) {
                // Clamp the value between 0 and 250 just to be safe
                const lookupValue = Math.min(Math.max(pm25Value, 0), 250);
                
                // Get color from JSON (using string lookup), default to purple if missing
                const bgColor = colorMap[lookupValue.toString()] || '#800080';
                
                // Apply the styles
                cell.style.backgroundColor = bgColor;
                cell.style.color = getContrastTextColor(bgColor);
            }
        });

    } catch (error) {
        console.error("Error applying heatmap colors:", error);
    }
});

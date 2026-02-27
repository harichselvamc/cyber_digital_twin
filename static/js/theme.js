// Fast Cache Application
const cachedColor = localStorage.getItem("bg_color");
if (cachedColor) {
    applyAdaptiveTheme(cachedColor);
}

// Determine luminance for adaptive contrast
function getLuminance(hex) {
    if (!hex || typeof hex !== 'string') return 1;
    hex = hex.replace(/^#/, '');
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    if (hex.length !== 6) return 1;

    const r = parseInt(hex.substring(0, 2), 16) / 255;
    const g = parseInt(hex.substring(2, 4), 16) / 255;
    const b = parseInt(hex.substring(4, 6), 16) / 255;

    const a = [r, g, b].map(v =>
        v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
    );
    return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
}

// Function to update CSS variables based on background color
function applyAdaptiveTheme(color) {
    if (!color) return;

    const root = document.documentElement;
    root.style.setProperty('--bg-color', color);

    // Dynamic contrast logic
    const luminance = getLuminance(color);
    const isDark = luminance < 0.5;

    // Set text and border variables
    const textColor = isDark ? '#f8fafc' : '#0f172a';
    const textMuted = isDark ? '#94a3b8' : '#475569';
    const borderColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const surfaceColor = isDark ? 'rgba(255, 255, 255, 0.05)' : '#ffffff';

    root.style.setProperty('--text-main', textColor);
    root.style.setProperty('--text-muted', textMuted);
    root.style.setProperty('--border-color', borderColor);
    root.style.setProperty('--surface-color', surfaceColor);

    // Apply directly to body if it exists (might be null during early head execution)
    if (document.body) {
        document.body.style.backgroundColor = color;
    }

    // Notify any listeners of theme change
    window.dispatchEvent(new Event('themeUpdated'));
}

// Load User Theme from API
async function loadUserTheme() {
    try {
        const res = await fetch("/api/settings/color");
        if (!res.ok) return;

        const data = await res.json();
        applyAdaptiveTheme(data.background_color);

        // Cache locally
        localStorage.setItem("bg_color", data.background_color);

        // Sync color picker if available
        const colorPicker = document.getElementById("colorPicker");
        if (colorPicker) {
            colorPicker.value = data.background_color;
        }

    } catch (err) {
        console.error("Failed to load theme:", err);
    }
}

window.addEventListener("DOMContentLoaded", loadUserTheme);

// Save User Theme API Call
async function setBackgroundColor(color) {
    try {
        applyAdaptiveTheme(color); // Apply locally immediately for snappiness

        const res = await fetch("/api/settings/color", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ color: color })
        });

        if (!res.ok) return;

        const data = await res.json();
        applyAdaptiveTheme(data.background_color); // Ensure backend format matches

        // Update cache
        localStorage.setItem("bg_color", data.background_color);

    } catch (err) {
        console.error("Failed to save color:", err);
    }
}

// Listen to Color Picker changes
window.addEventListener("DOMContentLoaded", () => {
    const colorPicker = document.getElementById("colorPicker");
    if (colorPicker) {
        // Use 'input' instead of 'change' for realtime drag preview
        colorPicker.addEventListener("input", function (e) {
            applyAdaptiveTheme(e.target.value);
        });

        colorPicker.addEventListener("change", function (e) {
            setBackgroundColor(e.target.value);
        });

        if (cachedColor) {
            colorPicker.value = cachedColor;
        }
    }
});

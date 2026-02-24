// Dashboard Logic

let monitorRunning = false;
let attackMode = false;
let pollingInterval = null;

// Charts instances
let replayChartInstance = null;
let explainChartInstance = null;
let heatmapChartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    fetchAnalytics();

    // Start polling immediately for status updates
    startPolling();
});

// --- Controls ---

async function toggleMonitor() {
    const btn = document.getElementById('monitorBtn');

    if (!monitorRunning) {
        // Start
        const res = await fetch('/api/start_monitor', { method: 'POST' });
        if (res.ok) {
            monitorRunning = true;
            btn.innerHTML = '<i class="fa-solid fa-square"></i> Stop Monitor';
            btn.classList.replace('btn-primary', 'btn-danger');

            // Pulse logic if element exists (it might not in new UI, or different ID)
            const pulse = document.getElementById('systemPulse');
            if (pulse) pulse.style.backgroundColor = 'var(--success-color)';
        }
    } else {
        // Stop
        const res = await fetch('/api/stop_monitor', { method: 'POST' });
        if (res.ok) {
            monitorRunning = false;
            btn.innerHTML = '<i class="fa-solid fa-play"></i> Start Monitor';
            btn.classList.replace('btn-danger', 'btn-primary');

            const pulse = document.getElementById('systemPulse');
            if (pulse) pulse.style.backgroundColor = 'var(--text-muted)';
        }
    }
}

async function resetSecurity() {
    const res = await fetch('/api/reset_security', { method: 'POST' });
    if (res.ok) {
        const data = await res.json();
        if (data.reset) {
            // Restore UI state
            monitorRunning = false;
            const btn = document.getElementById('monitorBtn');
            btn.innerHTML = '<i class="fa-solid fa-play"></i> Start Monitor';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-primary');

            const pulse = document.getElementById('systemPulse');
            if (pulse) pulse.style.backgroundColor = 'var(--text-muted)';

            // Hide any active alerts
            document.getElementById('alertArea').style.display = 'none';

            // Re-fetch everything to show fresh state
            updateRisk();
            fetchAnalytics();
        }
    }
}

document.getElementById('toggleAttackBtn').addEventListener('click', async () => {
    const btn = document.getElementById('toggleAttackBtn');
    const level = document.getElementById('attackLevel').value;

    attackMode = !attackMode;

    const res = await fetch('/api/attack_mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enable: attackMode, level: parseInt(level) })
    });

    if (res.ok) {
        const data = await res.json();
        if (data.attack_mode) {
            btn.innerText = 'Stop';
            btn.classList.add('btn-danger');
            btn.classList.remove('btn-outline');
        } else {
            btn.innerText = 'Start';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-outline');
        }
    }
});

// --- Polling & Updates ---

function startPolling() {
    pollingInterval = setInterval(async () => {
        try {
            updateRisk();
            updateCharts();
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 1000); // 1s primary poll
}

async function updateRisk() {
    const res = await fetch('/api/risk');
    if (!res.ok) return;
    const data = await res.json();

    // Update Text Metrics
    document.getElementById('riskScore').innerText = Math.round(data.risk_score);
    document.getElementById('confidenceScore').innerText = Math.round(data.confidence) + '%';
    document.getElementById('fingerprintScore').innerText = Math.round(data.fingerprint_score) + '%';
    document.getElementById('actionStatus').innerText = data.action;

    // Analytics (Quick Update)
    fetchAnalytics();

    // Badge styling & Card Border
    const riskCard = document.getElementById('riskCard');
    const badge = document.getElementById('riskLevelBadge');

    badge.innerText = data.level;
    riskCard.className = 'stat-card'; // reset
    badge.className = 'badge'; // reset

    if (data.level === 'LOW') {
        badge.classList.add('badge-green');
        riskCard.classList.add('risk-low');
    } else if (data.level === 'MEDIUM') {
        badge.classList.add('badge-yellow');
        riskCard.classList.add('risk-med');
    } else {
        badge.classList.add('badge-red');
        riskCard.classList.add('risk-high');
    }

    // Handle Alerts (Unified Area)
    const alertArea = document.getElementById('alertArea');
    const alertTitle = document.getElementById('alertTitle');
    const alertMsg = document.getElementById('alertMsg');
    const alertBtn = document.getElementById('alertBtn');
    const alertIcon = document.getElementById('alertIcon');

    if (data.action === 'STEP_UP') {
        alertArea.style.display = 'flex';
        alertArea.style.borderColor = 'var(--warning-color)';
        alertArea.style.background = 'rgba(245, 158, 11, 0.1)';

        alertIcon.className = 'fa-solid fa-fingerprint';
        alertIcon.style.color = 'var(--warning-color)';

        alertTitle.innerText = "Step-Up Authentication Required";
        alertTitle.style.color = 'var(--warning-color)';
        alertMsg.innerText = "Behavioral anomaly detected. Please verify identity.";

        alertBtn.innerText = "Verify OTP";
        alertBtn.href = "/otp";
        alertBtn.className = "btn"; // Reset classes
        alertBtn.style.backgroundColor = "var(--warning-color)";
        alertBtn.style.color = "#000";

    } else if (data.action === 'BLOCK') {
        alertArea.style.display = 'flex';
        alertArea.style.borderColor = 'var(--danger-color)';
        alertArea.style.background = 'rgba(239, 68, 68, 0.1)';

        alertIcon.className = 'fa-solid fa-ban';
        alertIcon.style.color = 'var(--danger-color)';

        alertTitle.innerText = "Session Locked";
        alertTitle.style.color = 'var(--danger-color)';
        alertMsg.innerText = "High risk activity. System access has been suspended.";

        alertBtn.innerText = "Reset Security";
        alertBtn.onclick = (e) => {
            e.preventDefault();
            resetSecurity();
        };
        alertBtn.href = "javascript:void(0)";
        alertBtn.className = "btn btn-danger";
        alertBtn.style.backgroundColor = ""; // Clear inline style
        alertBtn.style.color = "";

        if (monitorRunning) {
            monitorRunning = false;
            const btn = document.getElementById('monitorBtn');
            btn.innerHTML = '<i class="fa-solid fa-play"></i> Start Monitor';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-primary');
        }

    } else {
        alertArea.style.display = 'none';
    }
}

async function fetchAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        const data = await res.json();
        // Update new specific IDs
        const farEl = document.getElementById('metricFAR');
        const frrEl = document.getElementById('metricFRR');
        if (farEl) farEl.innerText = data.FAR.toFixed(4);
        if (frrEl) frrEl.innerText = data.FRR.toFixed(4);
    } catch (e) { }
}

function initCharts() {
    const ctxReplay = document.getElementById('replayChart').getContext('2d');
    const ctxExplain = document.getElementById('explainChart').getContext('2d');
    const ctxHeatmap = document.getElementById('heatmapChart').getContext('2d');

    // Theme Colors (Professional Light)
    const colorBorder = '#e2e8f0';
    const colorText = '#64748b';
    const colorPrimary = '#0f172a';
    const colorDanger = '#ef4444';
    const colorSuccess = '#10b981';

    // Common Options
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                grid: { color: colorBorder, drawBorder: false },
                ticks: { color: colorText, font: { family: 'Inter' } }
            },
            y: {
                grid: { color: colorBorder, drawBorder: false },
                ticks: { color: colorText, font: { family: 'Inter' } }
            }
        },
        interaction: {
            mode: 'index',
            intersect: false,
        }
    };

    // 1. Replay Line Chart
    replayChartInstance = new Chart(ctxReplay, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Risk Score',
                data: [],
                borderColor: colorPrimary,
                backgroundColor: 'rgba(59, 130, 246, 0.1)', // Blue transparent
                borderWidth: 2,
                tension: 0.3,
                fill: true,
                pointRadius: 0,
                pointHoverRadius: 4
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                x: commonOptions.scales.x,
                y: { min: 0, max: 100, grid: { color: colorBorder }, ticks: { color: colorText } }
            },
            animation: false
        }
    });

    // 2. Explain Horizontal Bar
    explainChartInstance = new Chart(ctxExplain, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Importance',
                data: [],
                backgroundColor: colorPrimary,
                borderRadius: 4,
                barThickness: 20
            }]
        },
        options: {
            ...commonOptions,
            indexAxis: 'y',
            scales: {
                x: { grid: { display: false }, ticks: { color: colorText } },
                y: { grid: { display: false }, ticks: { color: colorText } }
            }
        }
    });

    // 3. Heatmap
    heatmapChartInstance = new Chart(ctxHeatmap, {
        type: 'bar',
        data: {
            labels: Array.from({ length: 24 }, (_, i) => `${i}:00`),
            datasets: [{
                label: 'Activity',
                data: [],
                backgroundColor: colorDanger,
                borderRadius: 2
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                x: { grid: { display: false }, ticks: { display: false } }, // Compact view
                y: { grid: { color: colorBorder }, ticks: { color: colorText } }
            }
        }
    });
}


// --- Charts Update Logic ---

async function updateCharts() {
    try {
        // 1. Replay (History)
        const replayRes = await fetch('/api/replay');
        if (replayRes.ok) {
            const replayData = await replayRes.json();

            // Limit to last 50 points
            // Limit to last 50 points
            const recentData = replayData;

            // Format for Chart.js
            const labels = recentData.map(d => new Date(d.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
            const risks = recentData.map(d => d.risk);

            replayChartInstance.data.labels = labels;
            replayChartInstance.data.datasets[0].data = risks;
            replayChartInstance.update();
        }

        // 2. Explainability
        const explainRes = await fetch('/api/explain');
        if (explainRes.ok) {
            const explainData = await explainRes.json();

            const featureLabels = Object.keys(explainData);
            const featureValues = Object.values(explainData);

            explainChartInstance.data.labels = featureLabels;
            explainChartInstance.data.datasets[0].data = featureValues;
            explainChartInstance.update();
        }

        // 3. Heatmap
        const heatmapRes = await fetch('/api/heatmap');
        if (heatmapRes.ok) {
            const heatmapData = await heatmapRes.json();
            heatmapChartInstance.data.datasets[0].data = heatmapData;
            heatmapChartInstance.update();
        }

    } catch (e) {
        console.error("Chart update error:", e);
    }
}

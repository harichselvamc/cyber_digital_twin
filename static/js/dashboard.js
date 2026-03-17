// Dashboard Logic (Enhanced with new modules)

let monitorRunning = false;
let attackMode = false;
let silentMode = false;
let lockdownActive = false;
let pollingInterval = null;

// Charts instances
let replayChartInstance = null;
let explainChartInstance = null;
let heatmapChartInstance = null;

const featureMetadata = {
    "click_rate": {
        "meaning": "How often the user clicks the mouse per second.",
        "explanation": "Measures how fast you click.",
        "example": "5 clicks/s is normal; 15 clicks/s is unusual."
    },
    "hold_mean": {
        "meaning": "Average time a key is held down before being released.",
        "explanation": "How long you normally press each key.",
        "example": "120ms is typical; a drop to 40ms indicates a change."
    },
    "hold_std": {
        "meaning": "Variation in how long keys are held.",
        "explanation": "How consistent your key pressing duration is.",
        "example": "100-130ms is consistent; 30-300ms is erratic/suspicious."
    },
    "iki_mean": {
        "meaning": "Average time between pressing one key and the next.",
        "explanation": "Your average typing speed rhythm.",
        "example": "200ms is normal rhythm; 80ms is faster than usual."
    },
    "iki_std": {
        "meaning": "Variation in typing rhythm between keys.",
        "explanation": "How steady your typing rhythm is.",
        "example": "Steady speed is low variation; random bursts are high variation."
    },
    "key_rate": {
        "meaning": "Number of keys pressed per second.",
        "explanation": "How fast you type overall.",
        "example": "4 keys/s is normal; 12 keys/s is an unusual spike."
    },
    "mouse_speed_mean": {
        "meaning": "Average speed of mouse movement.",
        "explanation": "How fast you normally move your mouse.",
        "example": "Smooth moderate movement is normal; sudden jumps are anomalies."
    },
    "mouse_speed_std": {
        "meaning": "Variation in mouse movement speed.",
        "explanation": "How steady or shaky your mouse movements are.",
        "example": "Smooth movement is low variation; jerky movement is high variation."
    }
};

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    fetchAnalytics();
    startPolling();
});

// --- Controls ---

async function toggleMonitor() {
    const btn = document.getElementById('monitorBtn');

    if (!monitorRunning) {
        const res = await fetch('/api/start_monitor', { method: 'POST' });
        if (res.ok) {
            monitorRunning = true;
            btn.innerHTML = '<i class="fa-solid fa-square"></i> Stop Monitor';
            btn.classList.replace('btn-primary', 'btn-danger');

            const pulse = document.getElementById('systemPulse');
            if (pulse) pulse.style.backgroundColor = 'var(--success-color)';
        }
    } else {
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
            monitorRunning = false;
            const btn = document.getElementById('monitorBtn');
            btn.innerHTML = '<i class="fa-solid fa-play"></i> Start Monitor';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-primary');

            const pulse = document.getElementById('systemPulse');
            if (pulse) pulse.style.backgroundColor = 'var(--text-muted)';

            document.getElementById('alertArea').style.display = 'none';
            document.getElementById('notificationBanner').style.display = 'none';

            updateRisk();
            fetchAnalytics();
        }
    }
}

async function toggleSilentMode() {
    silentMode = !silentMode;
    const btn = document.getElementById('silentModeBtn');

    const res = await fetch('/api/silent_auth/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enable: silentMode })
    });

    if (res.ok) {
        if (silentMode) {
            btn.classList.remove('btn-outline');
            btn.classList.add('btn-primary');
            btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Silent ON';
        } else {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline');
            btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Silent';
        }
    }
}

async function toggleLockdown() {
    lockdownActive = !lockdownActive;
    const btn = document.getElementById('lockdownBtn');

    const endpoint = lockdownActive ? '/api/lockdown/activate' : '/api/lockdown/deactivate';
    const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scope: 'global', reason: 'Admin manual lockdown' })
    });

    if (res.ok) {
        if (lockdownActive) {
            btn.innerHTML = '<i class="fa-solid fa-lock-open"></i> Release';
            btn.style.background = 'rgba(239, 68, 68, 0.1)';
        } else {
            btn.innerHTML = '<i class="fa-solid fa-lock"></i> Lockdown';
            btn.style.background = '';
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
            updateNewModules();
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 1000);
}

async function updateRisk() {
    const res = await fetch('/api/risk');
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('riskScore').innerText = Math.round(data.risk_score);
    document.getElementById('confidenceScore').innerText = Math.round(data.confidence) + '%';
    document.getElementById('fingerprintScore').innerText = Math.round(data.fingerprint_score) + '%';
    document.getElementById('actionStatus').innerText = data.action;

    // Drift status
    const driftEl = document.getElementById('driftStatus');
    const driftBadge = document.getElementById('driftBadge');
    const driftStatus = data.drift_status || 'stable';
    driftEl.innerText = driftStatus.toUpperCase();
    driftBadge.className = 'badge';
    if (driftStatus === 'alarm') {
        driftBadge.classList.add('badge-red');
        driftBadge.innerText = 'Alert';
    } else if (driftStatus === 'drifting') {
        driftBadge.classList.add('badge-yellow');
        driftBadge.innerText = 'Shifting';
    } else {
        driftBadge.classList.add('badge-green');
        driftBadge.innerText = 'Normal';
    }

    // Fusion scores
    const fusion = data.fusion_scores || {};
    const ifScore = Math.round((fusion.isolation_forest || 0) * 100);
    const svmScore = Math.round((fusion.one_class_svm || 0) * 100);
    const aeScore = Math.round((fusion.autoencoder || 0) * 100);

    document.getElementById('fusionIF').innerText = ifScore + '%';
    document.getElementById('fusionSVM').innerText = svmScore + '%';
    document.getElementById('fusionAE').innerText = aeScore + '%';
    document.getElementById('fusionBarIF').style.width = ifScore + '%';
    document.getElementById('fusionBarSVM').style.width = svmScore + '%';
    document.getElementById('fusionBarAE').style.width = aeScore + '%';

    // Context flags
    const flags = data.context_flags || [];
    const ctxFlagsEl = document.getElementById('ctxFlags');
    if (ctxFlagsEl) {
        ctxFlagsEl.innerText = flags.length > 0 ? flags.join(', ') : 'None';
        ctxFlagsEl.style.color = flags.length > 0 ? 'var(--warning-color)' : 'var(--text-main)';
    }

    fetchAnalytics();

    // Badge styling & Card Border
    const riskCard = document.getElementById('riskCard');
    const badge = document.getElementById('riskLevelBadge');

    badge.innerText = data.level;
    riskCard.className = 'stat-card';
    badge.className = 'badge';

    if (data.level === 'LOW') {
        badge.classList.add('badge-green');
    } else if (data.level === 'MEDIUM') {
        badge.classList.add('badge-yellow');
    } else {
        badge.classList.add('badge-red');
    }

    // Handle Alerts
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
        alertBtn.className = "btn";
        alertBtn.style.backgroundColor = "var(--warning-color)";
        alertBtn.style.color = "#000";

    } else if (data.action === 'BLOCK') {
        alertArea.style.display = 'flex';
        alertArea.style.borderColor = 'var(--danger-color)';
        alertArea.style.background = 'rgba(239, 68, 68, 0.1)';

        alertIcon.className = 'fa-solid fa-ban';
        alertIcon.style.color = 'var(--danger-color)';

        alertTitle.innerText = data.lockdown_reason ? "Emergency Lockdown: " + data.lockdown_reason : "Session Locked";
        alertTitle.style.color = 'var(--danger-color)';
        alertMsg.innerText = "High risk activity. System access has been suspended.";

        alertBtn.innerText = "Reset Security";
        alertBtn.onclick = (e) => { e.preventDefault(); resetSecurity(); };
        alertBtn.href = "javascript:void(0)";
        alertBtn.className = "btn btn-danger";
        alertBtn.style.backgroundColor = "";
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

async function updateNewModules() {
    // Context summary
    try {
        const ctxRes = await fetch('/api/context');
        if (ctxRes.ok) {
            const ctx = await ctxRes.json();
            const devEl = document.getElementById('ctxDevices');
            const ipEl = document.getElementById('ctxIPs');
            const loginEl = document.getElementById('ctxLogins');
            if (devEl) devEl.innerText = ctx.known_devices_count || 0;
            if (ipEl) ipEl.innerText = ctx.known_ips_count || 0;
            if (loginEl) loginEl.innerText = ctx.total_logins || 0;
        }
    } catch (e) { }

    // Performance optimizer
    try {
        const perfRes = await fetch('/api/performance');
        if (perfRes.ok) {
            const perf = await perfRes.json();
            const intEl = document.getElementById('perfInterval');
            const savedEl = document.getElementById('perfSaved');
            const effEl = document.getElementById('perfEfficiency');
            const idleEl = document.getElementById('perfIdle');
            if (intEl) intEl.innerText = perf.current_interval + 's';
            if (savedEl) savedEl.innerText = perf.cycles_saved;
            if (effEl) effEl.innerText = perf.efficiency_pct + '%';
            if (idleEl) idleEl.innerText = perf.is_idle ? 'Yes' : 'No';
        }
    } catch (e) { }

    // Drift metric
    try {
        const driftRes = await fetch('/api/drift');
        if (driftRes.ok) {
            const drift = await driftRes.json();
            const driftMetric = document.getElementById('metricDrift');
            if (driftMetric) driftMetric.innerText = (drift.overall_drift || 0).toFixed(4);
        }
    } catch (e) { }

    // Silent auth notifications (gamified)
    try {
        const notifRes = await fetch('/api/silent_auth/notifications');
        if (notifRes.ok) {
            const notifs = await notifRes.json();
            if (notifs.length > 0) {
                const latest = notifs[notifs.length - 1];
                const banner = document.getElementById('notificationBanner');
                const icon = document.getElementById('notifIcon');
                const msg = document.getElementById('notifMessage');

                if (banner && msg) {
                    msg.innerText = latest.message;

                    if (latest.severity === 'critical') {
                        banner.style.background = 'rgba(239, 68, 68, 0.1)';
                        banner.style.borderColor = 'var(--danger-color)';
                        icon.style.color = 'var(--danger-color)';
                    } else if (latest.severity === 'warning') {
                        banner.style.background = 'rgba(245, 158, 11, 0.1)';
                        banner.style.borderColor = 'var(--warning-color)';
                        icon.style.color = 'var(--warning-color)';
                    } else {
                        banner.style.background = 'rgba(59, 130, 246, 0.1)';
                        banner.style.borderColor = 'var(--accent-color)';
                        icon.style.color = 'var(--accent-color)';
                    }
                    banner.style.display = 'flex';
                }
            }
        }
    } catch (e) { }
}

async function fetchAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        const data = await res.json();
        const farEl = document.getElementById('metricFAR');
        const frrEl = document.getElementById('metricFRR');
        if (farEl && data.FAR !== undefined) farEl.innerText = data.FAR.toFixed(4);
        if (frrEl && data.FRR !== undefined) frrEl.innerText = data.FRR.toFixed(4);
    } catch (e) { }
}

function initCharts() {
    const ctxReplay = document.getElementById('replayChart').getContext('2d');
    const ctxExplain = document.getElementById('explainChart').getContext('2d');
    const ctxHeatmap = document.getElementById('heatmapChart').getContext('2d');

    const colorBorder = '#e2e8f0';
    const colorText = '#64748b';
    const colorPrimary = '#0f172a';
    const colorDanger = '#ef4444';

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: '#ffffff',
                titleColor: '#0f172a',
                bodyColor: '#475569',
                borderColor: '#e2e8f0',
                borderWidth: 1,
                padding: 10,
                cornerRadius: 8,
                titleFont: { family: 'Inter', weight: 'bold' },
                bodyFont: { family: 'Inter' }
            }
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

    replayChartInstance = new Chart(ctxReplay, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Risk Score',
                data: [],
                borderColor: colorPrimary,
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
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
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: colorText } },
                y: {
                    grid: { display: false },
                    ticks: { display: false }
                }
            }
        }
    });

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
                x: { grid: { display: false }, ticks: { display: false } },
                y: { grid: { color: colorBorder }, ticks: { color: colorText } }
            }
        }
    });
}

async function updateCharts() {
    try {
        const replayRes = await fetch('/api/replay');
        if (replayRes.ok) {
            const replayData = await replayRes.json();
            const labels = replayData.map(d => new Date(d.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
            const risks = replayData.map(d => d.risk);

            replayChartInstance.data.labels = labels;
            replayChartInstance.data.datasets[0].data = risks;
            replayChartInstance.update();
        }

        const explainRes = await fetch('/api/explain');
        if (explainRes.ok) {
            const explainData = await explainRes.json();
            const featureLabels = Object.keys(explainData);
            const featureValues = Object.values(explainData);

            explainChartInstance.data.labels = featureLabels;
            explainChartInstance.data.datasets[0].data = featureValues;
            explainChartInstance.update();

            renderFeatureLegend(featureLabels);
        }

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

// Theme update listener
window.addEventListener('themeUpdated', () => {
    if (!replayChartInstance || !explainChartInstance || !heatmapChartInstance) return;

    const colorBorder = window.isDarkTheme ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const colorText = window.isDarkTheme ? '#cbd5e1' : '#475569';

    [replayChartInstance, explainChartInstance, heatmapChartInstance].forEach(chart => {
        if (chart.options.scales.x) {
            if (chart.options.scales.x.grid) chart.options.scales.x.grid.color = colorBorder;
            if (chart.options.scales.x.ticks) chart.options.scales.x.ticks.color = colorText;
        }
        if (chart.options.scales.y) {
            if (chart.options.scales.y.grid) chart.options.scales.y.grid.color = colorBorder;
            if (chart.options.scales.y.ticks) chart.options.scales.y.ticks.color = colorText;
        }
        chart.update();
    });

    explainChartInstance.data.datasets[0].backgroundColor = window.isDarkTheme ? '#94a3b8' : '#0f172a';
    explainChartInstance.update();
});

// --- Feature Info UI Logic ---

let currentFeatureLabels = [];

function renderFeatureLegend(labels) {
    const container = document.getElementById('featureLegend');
    if (!container) return;

    if (JSON.stringify(labels) === JSON.stringify(currentFeatureLabels) && container.children.length > 0) {
        return;
    }
    currentFeatureLabels = labels;

    container.innerHTML = '';
    labels.forEach(label => {
        const row = document.createElement('div');
        row.className = 'feature-info-row';
        row.innerHTML = `
            <span class="feature-name">${label}</span>
            <button class="info-btn" onclick="showFeatureInfo('${label}')" title="Click for details">
                <i class="fa-solid fa-circle-info"></i>
            </button>
        `;
        container.appendChild(row);
    });
}

function showFeatureInfo(feature) {
    const meta = featureMetadata[feature];
    if (!meta) return;

    document.getElementById('modalFeatureTitle').innerText = feature;
    document.getElementById('modalMeaning').innerText = meta.meaning;
    document.getElementById('modalExplanation').innerText = meta.explanation;
    document.getElementById('modalExample').innerText = meta.example;

    document.getElementById('featureModal').classList.add('active');
}

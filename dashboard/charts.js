
const COLORS = {
    normal: '#2196F3',
    mild: '#FF9800',
    severe: '#F44336',
    luna: '#9C27B0'
};

function initCharts() {
    initRegimeDonut();
    initMonthlyMix();
    initWithdrawalDist();
    initWithdrawalPaths();
    initSolvencyWaterfall();
    initIFDrawdown();
    initCostCurve();
}

function initRegimeDonut() {
    const ctx = document.getElementById('chart-regimes');
    if (!ctx) return;
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Normal', 'Stressed', 'Crisis'],
            datasets: [{
                data: [DATA.overview.regimes.normal, DATA.overview.regimes.stressed, DATA.overview.regimes.crisis],
                backgroundColor: [COLORS.normal, COLORS.mild, COLORS.severe],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 1,
            cutout: '70%',
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 10, padding: 20 } }
            }
        }
    });
}

function initMonthlyMix() {
    const ctx = document.getElementById('chart-monthly-mix');
    if (!ctx) return;
    const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    // Synthetic seasonal stress
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'Normal', data: [4, 4, 3, 4, 4, 3, 4, 4, 4, 3, 4, 2], backgroundColor: COLORS.normal },
                { label: 'Mild', data: [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 1], backgroundColor: COLORS.mild },
                { label: 'Severe', data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1], backgroundColor: COLORS.severe }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { stacked: true, grid: { display: false } },
                y: { stacked: true, grid: { color: '#334155' } }
            }
        }
    });
}

function initWithdrawalDist() {
    const ctx = document.getElementById('chart-withdrawal-dist');
    if (!ctx) return;

    const datasets = Object.keys(DATA.withdrawalHistograms).map(sc => ({
        label: sc.charAt(0).toUpperCase() + sc.slice(1),
        data: DATA.withdrawalHistograms[sc].hist.map((h, i) => ({ x: DATA.withdrawalHistograms[sc].bins[i], y: h })),
        backgroundColor: COLORS[sc] + '44',
        borderColor: COLORS[sc],
        fill: true,
        tension: 0.4,
        pointRadius: 0
    }));

    new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Withdrawal Amount ($M)' }, grid: { color: '#334155' } },
                y: { title: { display: true, text: 'Density' }, grid: { color: '#334155' } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function initWithdrawalPaths() {
    const ctx = document.getElementById('chart-withdrawal-paths');
    if (!ctx) return;

    const hours = Array.from({ length: 65 }, (_, i) => i);
    const reserveLevel = DATA.overview.totalFiat * 0.10 / 1e6; // Industry baseline 10%

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: hours,
            datasets: [
                ...Object.keys(DATA.hourlyPaths).map(sc => ({
                    label: sc.capitalize(),
                    data: DATA.hourlyPaths[sc].map(v => v / 1e6),
                    borderColor: COLORS[sc],
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 0
                })),
                {
                    label: 'Reserve (10%)',
                    data: new Array(65).fill(reserveLevel),
                    borderColor: '#94a3b8',
                    borderDash: [5, 5],
                    borderWidth: 1,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { title: { display: true, text: 'Hours (64h weekend)' }, grid: { color: '#334155' } },
                y: { title: { display: true, text: 'Cumulative Withdrawal ($M)' }, grid: { color: '#334155' } }
            }
        }
    });
}

function initSolvencyWaterfall() {
    const ctx = document.getElementById('chart-solvency-waterfall');
    if (!ctx) return;

    const s = DATA.solvency.severe;
    const labels = ['Assets', 'Withdrawal (p99)', 'IF Shortfall', 'Market Risk', 'Net Position'];
    const data = [
        s.assets.fiatReserve + s.assets.insuranceFund + s.assets.propCapital,
        -s.liabilities.withdrawal,
        -s.liabilities.derivatives,
        -s.liabilities.marketRisk,
        0 // computed below
    ];
    data[4] = data.reduce((a, b) => a + b, 0);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: data.map(v => v / 1e6),
                backgroundColor: data.map((v, i) => {
                    if (i === 0) return '#43A047';
                    if (i === 4) return v >= 0 ? '#1565C0' : '#C62828';
                    return '#E53935';
                })
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            scales: {
                x: { title: { display: true, text: '$M' }, grid: { color: '#334155' } },
                y: { grid: { display: false } }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function initIFDrawdown() {
    const ctx = document.getElementById('chart-if-drawdown');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: DATA.ifDrawdown.map((_, i) => i),
            datasets: [{
                label: 'Drawdown ($M)',
                data: DATA.ifDrawdown.map(v => v / 1e6),
                borderColor: COLORS.severe,
                backgroundColor: COLORS.severe + '22',
                fill: true,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                y: { title: { display: true, text: 'Drawdown ($M)' }, grid: { color: '#334155' } }
            }
        }
    });
}

function initCostCurve() {
    const ctx = document.getElementById('chart-cost-curve');
    if (!ctx) return;

    // Synthetic U-shape
    const x = Array.from({ length: 20 }, (_, i) => (i + 1) * 5); // 5% to 100%
    const opp = x.map(pct => pct * 2);
    const short = x.map(pct => 1000 / pct);
    const total = x.map((_, i) => opp[i] + short[i]);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: x,
            datasets: [
                { label: 'Total Cost', data: total, borderColor: 'gold', borderWidth: 3, pointRadius: 4 },
                { label: 'Opportunity Cost', data: opp, borderColor: '#388E3C', borderDash: [2, 2], pointRadius: 0 },
                { label: 'Shortfall Cost', data: short, borderColor: '#F44336', borderDash: [2, 2], pointRadius: 0 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { title: { display: true, text: 'Reserve Level (% AUM)' }, grid: { color: '#334155' } },
                y: { title: { display: true, text: 'Annual Cost (arb. units)' }, grid: { color: '#334155' } }
            }
        }
    });
}

String.prototype.capitalize = function () {
    return this.charAt(0).toUpperCase() + this.slice(1);
}

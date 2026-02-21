
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    initCharts();
});

function initApp() {
    // 1. Data Binding - Overview
    bindOverviewStats();

    // 2. Data Binding - Withdrawal Risk
    bindWithdrawalStats();

    // 3. Data Binding - Solvency
    bindSolvencyStats();

    // 4. Data Binding - Reserve Policy
    bindReservePolicy();

    // 5. Navigation handling
    initNavigation();
}

function formatUSD(val) {
    if (val >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
    if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
}

function bindOverviewStats() {
    document.getElementById('stat-total-fiat').textContent = formatUSD(DATA.overview.totalFiat);
    document.getElementById('stat-total-aum').textContent = formatUSD(DATA.overview.totalAUM);
    document.getElementById('stat-oi').textContent = formatUSD(DATA.overview.openInterest);
    document.getElementById('stat-if').textContent = formatUSD(DATA.overview.insuranceFund);

    // Scenario badges
    const scenarios = ['normal', 'mild', 'severe'];
    scenarios.forEach(sc => {
        const s = DATA.scenarios[sc];
        document.getElementById(`prob-${sc}`).textContent = `${(s.failureProb * 100).toFixed(1)}% failure`;
        document.getElementById(`verdict-${sc}`).textContent = s.verdict;
    });
}

function bindWithdrawalStats() {
    document.getElementById('wd-p99-normal').textContent = formatUSD(DATA.scenarios.normal.p99);
    document.getElementById('wd-p99-mild').textContent = formatUSD(DATA.scenarios.mild.p99);
    document.getElementById('wd-p99-severe').textContent = formatUSD(DATA.scenarios.severe.p99);

    // Table
    const tableBody = document.querySelector('#table-withdrawal-stats tbody');
    const scenarios = ['normal', 'mild', 'severe'];
    const triggers = {
        normal: 'Baseline weekend',
        mild: '20-30% drawdown',
        severe: 'FTX-style contagion'
    };
    const rates = {
        normal: '1-3%',
        mild: '5-8%',
        severe: '20-40%'
    };

    scenarios.forEach(sc => {
        const s = DATA.scenarios[sc];
        const row = `
            <tr>
                <td><span class="dot ${sc}"></span> ${s.name}</td>
                <td>${triggers[sc]}</td>
                <td>${rates[sc]}</td>
                <td>${formatUSD(s.mean)}</td>
                <td>${formatUSD(s.p95)}</td>
                <td>${formatUSD(s.p99)}</td>
                <td>${formatUSD(s.cvar99)}</td>
            </tr>
        `;
        tableBody.innerHTML += row;
    });
}

function bindSolvencyStats() {
    document.getElementById('val-ess').textContent = DATA.varComparison.ewma_ess;

    // VaR Table
    const tableBody = document.querySelector('#table-var-comparison tbody');
    tableBody.innerHTML = ''; // Clear previous

    const fiat = DATA.overview.totalFiat;
    const v = DATA.varComparison;

    const rowData = [
        {
            name: 'Historical Simulation',
            p95: v.hs.p95,
            p99: v.hs.p99,
            cvar: v.hs.cvar99,
            note: 'Lookback: 365d'
        },
        {
            name: 'Filtered HS (EWMA)',
            p95: null,
            p99: v.fhs.p99,
            cvar: v.fhs.cvar99,
            note: `ESS = ${v.ewma_ess} days`
        },
        {
            name: 'Stressed VaR',
            p95: null,
            p99: v.stressed.p99,
            cvar: v.stressed.cvar99,
            note: 'Worst 90-day window'
        },
        {
            name: 'Scenario: LUNA',
            p95: null,
            p99: null,
            cvar: v.luna.cvar99,
            note: 'Direct shock'
        },
        {
            name: 'Scenario: SEVERE',
            p95: null,
            p99: null,
            cvar: v.severe_shock.cvar99,
            note: 'Direct shock'
        }
    ];

    rowData.forEach(m => {
        const aumPct = m.cvar ? ((m.cvar / fiat) * 100).toFixed(1) + '%' : '—';
        const row = `
            <tr>
                <td>${m.name}</td>
                <td>${m.p95 ? formatUSD(m.p95) : '—'}</td>
                <td>${m.p99 ? formatUSD(m.p99) : '—'}</td>
                <td>${m.cvar ? formatUSD(m.cvar) : '—'}</td>
                <td>${aumPct}</td>
                <td>${m.note}</td>
            </tr>
        `;
        tableBody.innerHTML += row;
    });
}

function bindReservePolicy() {
    const p = DATA.reservePolicy;
    document.getElementById('res-t1-size').textContent = formatUSD(p.tier1);
    document.getElementById('res-t1-cost').textContent = formatUSD(p.annualCostTier1);
    document.getElementById('res-t2-size').textContent = formatUSD(p.tier2);
    document.getElementById('res-t2-cost').textContent = formatUSD(p.annualCostTier2);
    document.getElementById('res-t3-size').textContent = formatUSD(p.tier3);

    document.getElementById('policy-t1').textContent = formatUSD(p.tier1);
    document.getElementById('policy-t2').textContent = formatUSD(p.tier1 + p.tier2 + p.tier3);

    document.getElementById('policy-p-normal').textContent = `${(DATA.scenarios.normal.failureProb * 100).toFixed(2)}%`;
    document.getElementById('policy-p-severe').textContent = `${(DATA.scenarios.severe.failureProb * 100).toFixed(1)}%`;
}

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.content-section');
    const sectionNameDisplay = document.getElementById('current-section-name');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.getAttribute('data-section');

            // Update active link
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            // Update visible section
            sections.forEach(s => s.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');

            // Update title
            sectionNameDisplay.textContent = item.textContent.replace(/[◈◉≡⊛]/, '').trim();
        });
    });
}


document.addEventListener('DOMContentLoaded', () => {
    initApp();
    initCharts();
});

function initApp() {
    // 0. Currency Toggle Setup
    initCurrencyToggle();

    // 1. Data Binding - Overview KPIs (now inside Status section)
    bindOverviewStats();

    // 2. Data Binding - Withdrawal Risk
    bindWithdrawalStats();

    // 3. Data Binding - Solvency
    bindSolvencyStats();

    // 4. Data Binding - Reserve Policy
    bindReservePolicy();

    // 5. Data Binding - Operational Status
    renderStatus();

    // 6. Navigation handling
    initNavigation();
}

function initCurrencyToggle() {
    const btn = document.getElementById('toggle-currency');
    const label = document.getElementById('currency-label');

    btn.addEventListener('click', () => {
        currentCurrency = currentCurrency === 'IDR' ? 'USD' : 'IDR';
        label.textContent = currentCurrency;

        if (currentCurrency === 'IDR') {
            btn.classList.add('active-idr');
        } else {
            btn.classList.remove('active-idr');
        }

        // Re-render everything
        bindOverviewStats();
        bindWithdrawalStats();
        bindSolvencyStats();
        bindReservePolicy();
        renderStatus();

        // Re-init charts if they depend on currency
        initCharts();
    });
}

function formatCurrency(val) {
    const absVal = Math.abs(val);
    const sign = val < 0 ? '-' : '';

    // Convert if needed
    let displayVal = absVal;
    let symbol = currentCurrency === 'IDR' ? 'Rp ' : '$';

    if (currentCurrency === 'USD') {
        displayVal = absVal / FX_RATE;
    }

    if (displayVal >= 1e12) return `${sign}${symbol}${(displayVal / 1e12).toFixed(2)}T`;
    if (displayVal >= 1e9) return `${sign}${symbol}${(displayVal / 1e9).toFixed(1)}B`;
    if (displayVal >= 1e6) return `${sign}${symbol}${(displayVal / 1e6).toFixed(1)}M`;
    if (displayVal >= 1e3) return `${sign}${symbol}${(displayVal / 1e3).toFixed(1)}k`;

    return `${sign}${symbol}${displayVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

// Keep formatUSD for internal legacy if any, but point to formatCurrency
function formatUSD(val) {
    return formatCurrency(val);
}

function bindOverviewStats() {
    document.getElementById('stat-total-fiat').textContent = formatUSD(DATA.overview.totalFiat);
    document.getElementById('stat-total-aum').textContent = formatUSD(DATA.overview.totalAUM);
    document.getElementById('stat-oi').textContent = formatUSD(DATA.overview.openInterest);
    document.getElementById('stat-if').textContent = formatUSD(DATA.overview.insuranceFund);
}

function bindWithdrawalStats() {
    document.getElementById('wd-p99-normal').textContent = formatUSD(DATA.scenarios.normal.p99);
    document.getElementById('wd-p99-mild').textContent = formatUSD(DATA.scenarios.mild.p99);
    document.getElementById('wd-p99-severe').textContent = formatUSD(DATA.scenarios.severe.p99);

    // Table
    const tableBody = document.querySelector('#table-withdrawal-stats tbody');
    tableBody.innerHTML = ''; // Clear previous before re-rendering
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
    const valEssEl = document.getElementById('val-ess');
    if (valEssEl) valEssEl.textContent = DATA.varComparison.ewma_ess;

    // VaR Table
    const tableBody = document.querySelector('#table-var-comparison tbody');
    if (!tableBody) return;
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

function renderStatus() {
    const s = DATA.operationalStatus;

    // ── Scenario Banner ──────────────────────────────────────────────────
    const scenarioLabels = {
        normal: 'NORMAL — Baseline Weekend',
        mild: 'MILD STRESS — 20–30% Drawdown',
        severe: 'SEVERE STRESS — FTX-Style Contagion'
    };
    document.getElementById('status-scenario-name').textContent =
        scenarioLabels[s.activeScenario] || s.activeScenario.toUpperCase();
    document.getElementById('status-window').textContent =
        `${s.windowStart} → ${s.windowEnd}`;

    // ── Fiat Position Card ───────────────────────────────────────────────
    const fp = s.fiatPosition;
    applyStatusCard('card-fiat', fp.status);
    applyVerdict('verdict-fiat', fp.status);
    setColoredValue('fiat-gap', fp.gap, fp.gap < 0 ? 'red' : 'green');
    setValue('fiat-current', fp.currentReserve, 'currency');
    setValue('fiat-req-l1', fp.requiredLayer1, 'currency');
    setValue('fiat-req-l2', fp.requiredLayer2, 'currency');
    setColoredValue('fiat-gap-label', fp.gap, fp.gap < 0 ? 'red' : 'green');

    // ── Insurance Fund Card ──────────────────────────────────────────────
    const ifp = s.insuranceFundPosition;
    applyStatusCard('card-insurance', ifp.status);
    applyVerdict('verdict-insurance', ifp.status);
    setColoredValue('if-gap', ifp.gap, ifp.gap < 0 ? 'red' : 'green');
    setValue('if-current', ifp.currentBalance, 'currency');
    setValue('if-drawdown', ifp.expectedDrawdown, 'currency');
    setColoredValue('if-prob-exhaustion',
        (ifp.probExhaustion * 100).toFixed(1) + '%',
        ifp.probExhaustion > 0.5 ? 'red' : 'amber', true);
    setValue('if-clawback', ifp.expectedClawback, 'currency');
    document.getElementById('if-clawback').classList.add('red');

    // ── Time Buffer Card ─────────────────────────────────────────────────
    const tb = s.timeBuffer;
    applyStatusCard('card-time', tb.status);
    applyVerdict('verdict-time', tb.status);
    document.getElementById('time-hours').textContent = `~${tb.exhaustionHour} hrs`;
    document.getElementById('time-hours').className =
        'status-primary ' + statusToColor(tb.status);

    // Progress bar
    const pct = Math.min((tb.exhaustionHour / tb.totalHours) * 100, 100);
    document.getElementById('time-bar-fill').style.width = pct + '%';
    document.getElementById('time-bar-fill').style.background = statusToHex(tb.status);
    document.getElementById('time-bar-label-left').textContent =
        `Exhaustion at hr ${tb.exhaustionHour}`;
    document.getElementById('time-bar-label-left').style.color = statusToHex(tb.status);

    // Breakdown
    document.getElementById('time-inst-lead').textContent =
        tb.institutionalLeadDetected
            ? `Yes · +${tb.institutionalLeadHoursAgo} hrs ago`
            : 'Not detected';
    document.getElementById('time-inst-lead').className =
        'bk-val ' + (tb.institutionalLeadDetected ? 'amber' : 'green');
    document.getElementById('time-velocity').textContent =
        formatCurrency(tb.velocityPerHour) + ' / hr';
    document.getElementById('time-retail-onset').textContent =
        `~hr ${tb.retailPanicOnsetHour}`;

    // ── Readiness Card ───────────────────────────────────────────────────
    const r = s.readiness;
    applyStatusCard('card-readiness', r.status);
    applyVerdict('verdict-readiness', r.status);
    setColoredValue('readiness-gap',
        formatCurrency(r.totalCapitalGap),
        r.totalCapitalGap < 0 ? 'red' : 'green', true);
    document.getElementById('readiness-gap').className =
        'status-primary ' + (r.totalCapitalGap < 0 ? 'red' : 'green');

    setColoredValue('readiness-fiat-gap', r.fiatGap, r.fiatGap < 0 ? 'red' : 'green');
    setColoredValue('readiness-if-gap', r.insuranceGap, r.insuranceGap < 0 ? 'red' : 'green');
    setValue('readiness-prop', r.proprietaryBuffer, 'currency');
    document.getElementById('readiness-prop').classList.add('green');
    setColoredValue('readiness-net', r.netPosition, r.netPosition < 0 ? 'red' : 'green');

    // ── Action Row ───────────────────────────────────────────────────────
    const a = s.requiredAction;
    const level = a.level.toLowerCase();
    const row = document.getElementById('action-row');
    if (row) {
        row.className = `action-row level-${level}`;
        const titleEl = document.getElementById('action-title');
        titleEl.textContent = a.title;
        titleEl.className = `action-title ${level}`;

        document.getElementById('action-desc').textContent = a.message;

        const badge = document.getElementById('action-badge');
        badge.textContent = a.level.replace('_', ' ');
        badge.className = `action-badge ${level}`;
    }
}

// ── Helper: apply accent class to card (top bar) ───────────────────────
function applyStatusCard(cardId, status) {
    const el = document.getElementById(cardId);
    if (!el) return;
    el.classList.remove('accent-red', 'accent-gold', 'accent-green');
    const map = {
        'CRITICAL': 'accent-red',
        'AT RISK': 'accent-gold',
        'UNDERFUNDED': 'accent-gold',
        'LIMITED': 'accent-gold',
        'NOT READY': 'accent-red',
        'MONITOR': 'accent-gold',
        'ADEQUATE': 'accent-green',
        'SAFE': 'accent-green',
        'READY': 'accent-green',
    };
    el.classList.add(map[status] || 'accent-gold');
}

// ── Helper: apply verdict badge class (tints) ──────────────────────────
function applyVerdict(elId, status) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = status;
    el.className = 'status-verdict';
    const map = {
        'CRITICAL': 'red',
        'AT RISK': 'gold',
        'UNDERFUNDED': 'gold',
        'LIMITED': 'gold',
        'NOT READY': 'red',
        'MONITOR': 'gold',
        'ADEQUATE': 'green',
        'SAFE': 'green',
        'READY': 'green',
    };
    el.classList.add(map[status] || 'gold');
}

// ── Helper: status string → CSS color class ──────────────────────────────
function statusToColor(status) {
    const map = {
        'CRITICAL': 'red', 'AT RISK': 'gold', 'UNDERFUNDED': 'gold',
        'LIMITED': 'gold', 'NOT READY': 'red',
        'ADEQUATE': 'green', 'SAFE': 'green', 'READY': 'green',
    };
    return map[status] || 'gold';
}

// ── Helper: status string → hex color ───────────────────────────────────
function statusToHex(status) {
    const map = {
        'CRITICAL': '#f87171', 'AT RISK': '#d4a843', 'UNDERFUNDED': '#d4a843',
        'LIMITED': '#d4a843', 'NOT READY': '#f87171',
        'ADEQUATE': '#3ecf8e', 'SAFE': '#3ecf8e', 'READY': '#3ecf8e',
    };
    return map[status] || '#d4a843';
}

// ── Helper: set element text + optional color class ─────────────────────
function setValue(id, val, format) {
    const el = document.getElementById(id);
    if (!el) return;
    if (format === 'currency') el.textContent = formatCurrency(val);
    else el.textContent = val;
}
function setColoredValue(id, val, colorClass, rawText = false) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = rawText ? val : formatCurrency(val);
    el.classList.remove('red', 'green', 'amber', 'gold'); // Clear previous
    el.classList.add(colorClass);
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
            const targetSec = document.getElementById(targetId);
            if (targetSec) targetSec.classList.add('active');

            // Update title
            if (sectionNameDisplay) {
                sectionNameDisplay.textContent = item.textContent.replace(/[◈◉≡⊛⊕]/, '').trim();
            }
        });
    });
}

/**
 * MikroTik Traffic Monitor - Frontend Application
 * Strictly follows prd.md:
 * - Single source of truth: Reads configuration via GET /api/config
 * - No hardcoded interfaces, graph periods, labels, or refresh rates
 * - Generic duration parser (m, h, d) to compare period vs realtime_max
 * - Dynamic creation of Interface Cards, Interface Selectors, and Period Selectors
 * - Real-time polling vs Historical fetch logic
 */

(function () {
  'use strict';

  // State Management
  const state = {
    config: null,
    selectedInterface: null,
    selectedPeriod: null,
    isRealtime: true,
    pollingTimer: null,
    chartInstance: null,
    isDemoMode: false,
    mockTimeCounter: Date.now()
  };

  // DOM Elements
  const elements = {
    mikrotikStatusBadge: document.getElementById('mikrotikStatusBadge'),
    mikrotikStatusText: document.getElementById('mikrotikStatusText'),
    lastPollText: document.getElementById('lastPollText'),
    demoBanner: document.getElementById('demoBanner'),
    interfaceCardsContainer: document.getElementById('interfaceCardsContainer'),
    interfaceSelect: document.getElementById('interfaceSelect'),
    periodSelect: document.getElementById('periodSelect'),
    refreshBtn: document.getElementById('refreshBtn'),
    modeBadge: document.getElementById('modeBadge'),
    modeBadgeText: document.getElementById('modeBadgeText'),
    currentRxSummary: document.getElementById('currentRxSummary'),
    currentTxSummary: document.getElementById('currentTxSummary'),
    chartOverlay: document.getElementById('chartOverlay'),
    chartCanvas: document.getElementById('trafficChart')
  };

  // ==========================================================================
  // Helper Functions
  // ==========================================================================

  /**
   * Generic duration parser (prd.md Section 10 & 14)
   * Parses duration string matching ^\d+(m|h|d)$ into seconds.
   * m = 60s, h = 3600s, d = 86400s
   */
  function parseDurationSeconds(durationStr) {
    if (!durationStr || typeof durationStr !== 'string') return 0;
    const match = durationStr.trim().match(/^(\d+)([mhd])$/);
    if (!match) return 0;
    const value = parseInt(match[1], 10);
    const unit = match[2];
    switch (unit) {
      case 'm': return value * 60;
      case 'h': return value * 3600;
      case 'd': return value * 86400;
      default: return 0;
    }
  }

  /**
   * Bitrate Formatter (prd.md Section 22)
   * Converts bits per second (bps) to Kbps, Mbps, Gbps.
   */
  function formatBitrate(bps) {
    if (bps === undefined || bps === null || isNaN(bps)) return '0 Bps';
    const absVal = Math.abs(bps);
    if (absVal >= 1e9) {
      return (bps / 1e9).toFixed(2) + ' Gbps';
    } else if (absVal >= 1e6) {
      return (bps / 1e6).toFixed(2) + ' Mbps';
    } else if (absVal >= 1e3) {
      return (bps / 1e3).toFixed(2) + ' Kbps';
    } else {
      return Math.round(bps) + ' bps';
    }
  }

  /**
   * Date & Time Formatter
   */
  function formatTimestamp(isoOrMs, includeSeconds = true) {
    if (!isoOrMs) return '--:--:--';
    const date = new Date(isoOrMs);
    if (isNaN(date.getTime())) return '--:--:--';
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: includeSeconds ? '2-digit' : undefined
    });
  }

  // ==========================================================================
  // Application Lifecycle & Initialization
  // ==========================================================================

  document.addEventListener('DOMContentLoaded', initApp);

  async function initApp() {
    setupEventListeners();
    initChart();
    await loadAppConfig();
  }

  function setupEventListeners() {
    elements.interfaceSelect.addEventListener('change', (e) => {
      state.selectedInterface = e.target.value;
      updateActiveCardHighlight();
      fetchTrafficData();
    });

    elements.periodSelect.addEventListener('change', (e) => {
      state.selectedPeriod = e.target.value;
      updateModeAndPollingState();
      fetchTrafficData();
    });

    elements.refreshBtn.addEventListener('click', () => {
      fetchInterfaceStatus();
      fetchTrafficData();
    });
  }

  // ==========================================================================
  // Configuration API & Dynamic UI Building
  // ==========================================================================

  /**
   * Fetches /api/config (prd.md Section 19 & 20)
   */
  async function loadAppConfig() {
    showChartOverlay(true);
    try {
      const response = await fetch('/api/config');
      if (!response.ok) throw new Error('HTTP error ' + response.status);
      const config = await response.json();
      state.config = config;
      state.isDemoMode = false;
      elements.demoBanner.classList.add('hidden');
    } catch (err) {
      console.warn('Could not fetch /api/config from server, enabling simulated demo mode:', err);
      state.isDemoMode = true;
      state.config = getMockConfig();
      elements.demoBanner.classList.remove('hidden');
    }

    buildDynamicUI();
    updateModeAndPollingState();
    await fetchInterfaceStatus();
    await fetchTrafficData();
    showChartOverlay(false);
  }

  /**
   * Build UI options & card placeholders strictly driven by /api/config
   */
  function buildDynamicUI() {
    const config = state.config;
    if (!config) return;

    // 1. Build Interface Dropdown (All Interfaces + dynamic list)
    elements.interfaceSelect.innerHTML = '';

    const allOpt = document.createElement('option');
    allOpt.value = 'all';
    allOpt.textContent = 'All Interfaces (Total)';
    elements.interfaceSelect.appendChild(allOpt);

    config.interfaces.forEach((ifaceName) => {
      const opt = document.createElement('option');
      opt.value = ifaceName;
      opt.textContent = ifaceName;
      elements.interfaceSelect.appendChild(opt);
    });

    // Default interface choice is 'all'
    state.selectedInterface = 'all';
    elements.interfaceSelect.value = 'all';

    // 2. Build Period Dropdown (prd.md Section 12, 19, 35)
    elements.periodSelect.innerHTML = '';
    config.graph_periods.forEach((periodObj) => {
      const opt = document.createElement('option');
      opt.value = periodObj.value;
      opt.textContent = periodObj.label;
      elements.periodSelect.appendChild(opt);
    });

    // Default period choice
    state.selectedPeriod = config.default_period || (config.graph_periods[0] && config.graph_periods[0].value);
    elements.periodSelect.value = state.selectedPeriod;

    // 3. Render Skeleton Interface Cards (prd.md Section 33)
    renderInterfaceCardsSkeleton(config.interfaces);
  }

  /**
   * Determine whether current selected period is Real-Time or Historical
   * (prd.md Section 17, 30, 31)
   */
  function updateModeAndPollingState() {
    if (!state.config) return;

    const selectedSec = parseDurationSeconds(state.selectedPeriod);
    const maxRealtimeSec = parseDurationSeconds(state.config.realtime_max);

    state.isRealtime = selectedSec <= maxRealtimeSec;

    // Update Mode UI Badge
    if (state.isRealtime) {
      elements.modeBadge.className = 'mode-badge';
      elements.modeBadgeText.textContent = `● Real-Time (${(state.config.refresh_interval / 1000).toFixed(0)}s refresh)`;
    } else {
      elements.modeBadge.className = 'mode-badge historical';
      elements.modeBadgeText.textContent = '⏱ Historical Data';
    }

    // Configure Polling Interval
    if (state.pollingTimer) {
      clearInterval(state.pollingTimer);
      state.pollingTimer = null;
    }

    if (state.isRealtime) {
      const intervalMs = state.config.refresh_interval || 5000;
      state.pollingTimer = setInterval(() => {
        fetchInterfaceStatus();
        fetchTrafficData(true); // silent refresh
      }, intervalMs);
    }
  }

  // ==========================================================================
  // Data Fetching & State Updates
  // ==========================================================================

  /**
   * Fetch Status & Interfaces (GET /api/status & GET /api/interfaces)
   */
  async function fetchInterfaceStatus() {
    let statusData = null;
    let interfacesData = null;

    if (state.isDemoMode) {
      statusData = getMockStatus();
      interfacesData = getMockInterfaces(state.config.interfaces);
    } else {
      try {
        const [resStatus, resInterfaces] = await Promise.all([
          fetch('/api/status'),
          fetch('/api/interfaces')
        ]);
        if (resStatus.ok) statusData = await resStatus.json();
        if (resInterfaces.ok) interfacesData = await resInterfaces.json();
      } catch (err) {
        console.error('Error fetching status/interfaces:', err);
        statusData = { status: 'error', mikrotik: false, last_poll: new Date().toISOString() };
      }
    }

    // Update Global MikroTik Status Header Badge
    if (statusData && statusData.mikrotik) {
      elements.mikrotikStatusBadge.className = 'status-badge connected';
      elements.mikrotikStatusText.textContent = 'MikroTik Connected';
    } else {
      elements.mikrotikStatusBadge.className = 'status-badge disconnected';
      elements.mikrotikStatusText.textContent = 'MikroTik Disconnected';
    }

    if (statusData && statusData.last_poll) {
      elements.lastPollText.textContent = `Last poll: ${formatTimestamp(statusData.last_poll)}`;
    }

    // Render Interface Cards (prd.md Section 33)
    if (interfacesData && interfacesData.interfaces) {
      renderInterfaceCards(interfacesData.interfaces);
    }
  }

  /**
   * Fetch Traffic Data for Chart (GET /api/traffic?interface=X&period=Y)
   */
  async function fetchTrafficData(isSilentRefresh = false) {
    if (!state.selectedInterface || !state.selectedPeriod) return;

    if (!isSilentRefresh) {
      showChartOverlay(true);
    }

    let trafficRes = null;

    if (state.isDemoMode) {
      trafficRes = getMockTraffic(state.selectedInterface, state.selectedPeriod);
    } else {
      try {
        const url = `/api/traffic?interface=${encodeURIComponent(state.selectedInterface)}&period=${encodeURIComponent(state.selectedPeriod)}`;
        const response = await fetch(url);
        if (response.ok) {
          trafficRes = await response.json();
        } else {
          console.error('Failed to fetch traffic data:', response.status);
        }
      } catch (err) {
        console.error('Error fetching traffic data:', err);
      }
    }

    if (!isSilentRefresh) {
      showChartOverlay(false);
    }

    if (trafficRes && trafficRes.data) {
      updateChartData(trafficRes.data);
    }
  }

  // ==========================================================================
  // Interface Cards Renderer
  // ==========================================================================

  function renderInterfaceCardsSkeleton(interfacesList) {
    elements.interfaceCardsContainer.innerHTML = '';
    
    // Skeleton for All Interfaces card
    const allSkeleton = document.createElement('div');
    allSkeleton.className = 'skeleton-card';
    allSkeleton.style.height = '120px';
    elements.interfaceCardsContainer.appendChild(allSkeleton);

    interfacesList.forEach((name) => {
      const card = document.createElement('div');
      card.className = 'skeleton-card';
      card.style.height = '120px';
      elements.interfaceCardsContainer.appendChild(card);
    });
  }

  function renderInterfaceCards(interfaceList) {
    elements.interfaceCardsContainer.innerHTML = '';

    // Calculate aggregated total RX and TX rates across all interfaces
    let totalRx = 0;
    let totalTx = 0;
    let anyUp = false;

    interfaceList.forEach((iface) => {
      totalRx += (iface.rx_bps || 0);
      totalTx += (iface.tx_bps || 0);
      const st = (iface.status || 'down').toLowerCase();
      if (st === 'running' || st === 'up') anyUp = true;
    });

    // 1. All Interfaces (Total) Card
    const allCard = document.createElement('div');
    const isAllSelected = state.selectedInterface === 'all';
    allCard.className = `interface-card ${isAllSelected ? 'active' : ''}`;
    
    allCard.innerHTML = `
      <div class="card-header">
        <div class="interface-name">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
          All Interfaces
        </div>
        <span class="interface-status-badge ${anyUp ? 'up' : 'down'}">${anyUp ? 'TOTAL' : 'OFFLINE'}</span>
      </div>
      <div class="metrics-container">
        <div class="metric-box rx">
          <div class="metric-label rx">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            Total RX
          </div>
          <div class="metric-value">${formatBitrate(totalRx)}</div>
        </div>
        <div class="metric-box tx">
          <div class="metric-label tx">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="17 14 12 9 7 14"></polyline><line x1="12" y1="21" x2="12" y2="9"></line></svg>
            Total TX
          </div>
          <div class="metric-value">${formatBitrate(totalTx)}</div>
        </div>
      </div>
    `;

    allCard.addEventListener('click', () => {
      state.selectedInterface = 'all';
      elements.interfaceSelect.value = 'all';
      updateActiveCardHighlight();
      fetchTrafficData();
    });

    elements.interfaceCardsContainer.appendChild(allCard);

    // 2. Individual Interface Cards
    interfaceList.forEach((iface) => {
      const card = document.createElement('div');
      const isSelected = iface.name === state.selectedInterface;
      card.className = `interface-card ${isSelected ? 'active' : ''}`;
      
      const statusClass = (iface.status || 'down').toLowerCase();
      const statusLabel = statusClass === 'running' || statusClass === 'up' ? 'UP' : 'DOWN';
      const badgeClass = statusLabel === 'UP' ? 'up' : 'down';

      card.innerHTML = `
        <div class="card-header">
          <div class="interface-name">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
              <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
              <line x1="6" y1="6" x2="6.01" y2="6"></line>
              <line x1="6" y1="18" x2="6.01" y2="18"></line>
            </svg>
            ${escapeHtml(iface.name)}
          </div>
          <span class="interface-status-badge ${badgeClass}">${statusLabel}</span>
        </div>
        <div class="metrics-container">
          <div class="metric-box rx">
            <div class="metric-label rx">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
              RX Rate
            </div>
            <div class="metric-value">${formatBitrate(iface.rx_bps)}</div>
          </div>
          <div class="metric-box tx">
            <div class="metric-label tx">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="17 14 12 9 7 14"></polyline><line x1="12" y1="21" x2="12" y2="9"></line></svg>
              TX Rate
            </div>
            <div class="metric-value">${formatBitrate(iface.tx_bps)}</div>
          </div>
        </div>
      `;

      card.addEventListener('click', () => {
        state.selectedInterface = iface.name;
        elements.interfaceSelect.value = iface.name;
        updateActiveCardHighlight();
        fetchTrafficData();
      });

      elements.interfaceCardsContainer.appendChild(card);
    });
  }

  function updateActiveCardHighlight() {
    const cards = elements.interfaceCardsContainer.querySelectorAll('.interface-card');
    cards.forEach((card) => {
      const nameEl = card.querySelector('.interface-name');
      if (nameEl) {
        const text = nameEl.textContent.trim();
        if (
          (state.selectedInterface === 'all' && text.includes('All Interfaces')) ||
          (text === state.selectedInterface)
        ) {
          card.classList.add('active');
        } else {
          card.classList.remove('active');
        }
      }
    });
  }

  // ==========================================================================
  // Chart.js Visualization Engine
  // ==========================================================================

  function initChart() {
    const ctx = elements.chartCanvas.getContext('2d');

    // Create Canvas Gradient Fills
    const rxGradient = ctx.createLinearGradient(0, 0, 0, 350);
    rxGradient.addColorStop(0, 'rgba(6, 182, 212, 0.35)');
    rxGradient.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

    const txGradient = ctx.createLinearGradient(0, 0, 0, 350);
    txGradient.addColorStop(0, 'rgba(139, 92, 246, 0.35)');
    txGradient.addColorStop(1, 'rgba(139, 92, 246, 0.0)');

    state.chartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'RX (Download)',
            data: [],
            borderColor: '#06b6d4',
            backgroundColor: rxGradient,
            borderWidth: 2,
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 6,
            pointHoverBackgroundColor: '#06b6d4',
            pointHoverBorderColor: '#ffffff',
            pointHoverBorderWidth: 2
          },
          {
            label: 'TX (Upload)',
            data: [],
            borderColor: '#8b5cf6',
            backgroundColor: txGradient,
            borderWidth: 2,
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 6,
            pointHoverBackgroundColor: '#8b5cf6',
            pointHoverBorderColor: '#ffffff',
            pointHoverBorderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        animation: {
          duration: state.isRealtime ? 300 : 750
        },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            align: 'end',
            labels: {
              color: '#94a3b8',
              font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' },
              usePointStyle: true,
              pointStyle: 'circle',
              padding: 20
            }
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            titleColor: '#f8fafc',
            bodyColor: '#cbd5e1',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            padding: 12,
            boxPadding: 6,
            usePointStyle: true,
            callbacks: {
              label: function (context) {
                const label = context.dataset.label || '';
                const value = context.parsed.y || 0;
                return ` ${label}: ${formatBitrate(value)}`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: {
              color: 'rgba(255, 255, 255, 0.04)',
              drawBorder: false
            },
            ticks: {
              color: '#64748b',
              font: { family: 'Plus Jakarta Sans', size: 11 },
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: 8
            }
          },
          y: {
            beginAtZero: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.04)',
              drawBorder: false
            },
            ticks: {
              color: '#64748b',
              font: { family: 'Plus Jakarta Sans', size: 11 },
              callback: function (value) {
                return formatBitrate(value);
              }
            }
          }
        }
      }
    });
  }

  function updateChartData(samples) {
    if (!state.chartInstance) return;

    const labels = [];
    const rxData = [];
    const txData = [];

    samples.forEach((sample) => {
      labels.push(formatTimestamp(sample.timestamp));
      rxData.push(sample.rx_bps || 0);
      txData.push(sample.tx_bps || 0);
    });

    state.chartInstance.data.labels = labels;
    state.chartInstance.data.datasets[0].data = rxData;
    state.chartInstance.data.datasets[1].data = txData;

    state.chartInstance.update(state.isRealtime ? 'none' : 'normal');

    // Update Live Traffic Summary Text above Chart
    if (samples.length > 0) {
      const latest = samples[samples.length - 1];
      elements.currentRxSummary.textContent = formatBitrate(latest.rx_bps);
      elements.currentTxSummary.textContent = formatBitrate(latest.tx_bps);
    } else {
      elements.currentRxSummary.textContent = '0 bps';
      elements.currentTxSummary.textContent = '0 bps';
    }
  }

  function showChartOverlay(show) {
    if (show) {
      elements.chartOverlay.classList.remove('hidden');
    } else {
      elements.chartOverlay.classList.add('hidden');
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ==========================================================================
  // Simulated API Mock Engine (Active when backend is offline)
  // Ensures frontend is testable/runnable independently while strictly obeying PRD API schema
  // ==========================================================================

  function getMockConfig() {
    return {
      interfaces: ["ether1-BAROKAH", "ether2-BIZ", "ether3-WAHED"],
      graph_periods: [
        { value: "5m", label: "5 Menit" },
        { value: "15m", label: "15 Menit" },
        { value: "30m", label: "30 Menit" },
        { value: "1h", label: "1 Jam" },
        { value: "12h", label: "12 Jam" },
        { value: "24h", label: "24 Jam" }
      ],
      default_period: "15m",
      realtime_max: "30m",
      refresh_interval: 5000,
      max_points: 500
    };
  }

  function getMockStatus() {
    return {
      status: "ok",
      mikrotik: true,
      last_poll: new Date().toISOString()
    };
  }

  function getMockInterfaces(ifaceList) {
    const baseRates = {
      "ether1-BAROKAH": { rx: 125000000, tx: 20000000 },
      "ether2-BIZ": { rx: 250000000, tx: 45000000 },
      "ether3-WAHED": { rx: 300000000, tx: 60000000 }
    };

    const interfaces = (ifaceList || []).map((name) => {
      const base = baseRates[name] || { rx: 50000000, tx: 10000000 };
      const jitterRx = (Math.random() - 0.5) * 15000000;
      const jitterTx = (Math.random() - 0.5) * 5000000;

      return {
        name: name,
        status: "running",
        rx_bps: Math.max(100000, Math.round(base.rx + jitterRx)),
        tx_bps: Math.max(50000, Math.round(base.tx + jitterTx))
      };
    });

    return { interfaces };
  }

  function getMockTraffic(ifaceName, periodStr) {
    const seconds = parseDurationSeconds(periodStr) || 900;
    const pointCount = Math.min(60, Math.max(20, Math.floor(seconds / 15)));
    const now = Date.now();
    const data = [];

    const baseRates = {
      "all": { rx: 640000000, tx: 115000000 },
      "ether1-BAROKAH": { rx: 120000000, tx: 18000000 },
      "ether2-BIZ": { rx: 240000000, tx: 40000000 },
      "ether3-WAHED": { rx: 280000000, tx: 55000000 }
    };

    const base = baseRates[ifaceName] || { rx: 60000000, tx: 12000000 };

    for (let i = pointCount; i >= 0; i--) {
      const t = now - (i * (seconds * 1000 / pointCount));
      const sineWave = Math.sin(i / 3) * 30000000;
      const noiseRx = (Math.random() - 0.5) * 10000000;
      const noiseTx = (Math.random() - 0.5) * 3000000;

      data.push({
        timestamp: new Date(t).toISOString(),
        rx_bps: Math.max(500000, Math.round(base.rx + sineWave + noiseRx)),
        tx_bps: Math.max(200000, Math.round(base.tx + (sineWave * 0.3) + noiseTx))
      });
    }

    return {
      interface: ifaceName,
      period: periodStr,
      data: data
    };
  }

})();

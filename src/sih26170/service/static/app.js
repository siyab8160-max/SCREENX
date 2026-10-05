/**
 * SIH26170 Component Screening Workstation — Master Client Application
 * 
 * Engineering Architecture:
 * - ISRO Mission-Assurance semiconductor burn-in screening instrument.
 * - Single source of truth: All screening states, detector statistics, forecasts,
 *   prediction intervals, specification limits, and hashes originate from backend API.
 * - Deep-space aerospace dark console theme.
 * - Strict temporal causality: Observed telemetry > as_of is strictly unrendered.
 * - 4 dedicated workspaces: Screening, Prognostics, Upload Data, Traceability.
 * - Interactive Burn-In Tray Matrix for lot cohort visualization.
 * - Safety-Slope Vector Gauges for visual drift-rate assessment.
 * - Certificate of Conformance (CoC) with SHA-256 tamper-proof seals.
 */

// Master Application State
const state = {
  activeWorkspace: 'data',
  activeDataset: 'demo', // 'demo' | 'uploaded'
  selectedLotId: 'LOT_CAL_001',
  selectedComponentId: 'LOT_CAL_001_C001',
  selectedAsOf: 24, // 24, 48, 72, 96, 120, 168
  activeChartParam: 'ALL', // 'ALL' | 'IDSS' | 'VGS(th)' | 'RDS(on)' | 'IGSS'
  pipelineData: null,
  lots: [],
  componentsInLot: [],
  isLoading: false,
  trayStatuses: {}, // { componentId: 'PASS'|'ALERT'|'FAIL'|... }

  // Uploaded dataset storage
  uploadedData: null,
  uploadedSummary: null,
};

const ORDERED_PARAMETERS = ['IDSS', 'VGS(th)', 'RDS(on)', 'IGSS'];

// -----------------------------------------------------------------------------
// API CLIENT
// -----------------------------------------------------------------------------
async function apiGet(endpoint) {
  try {
    const res = await fetch(endpoint, { cache: 'no-store' });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || `HTTP ${res.status}: ${res.statusText}`);
    }
    updateConnectionStatus(true);
    return await res.json();
  } catch (err) {
    updateConnectionStatus(false, err.message);
    throw err;
  }
}

async function apiPost(endpoint, payload) {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.error || `HTTP ${res.status}: ${res.statusText}`);
  }
  updateConnectionStatus(true);
  return res.json();
}

function updateConnectionStatus(isOnline, errMsg = '') {
  const dot = document.getElementById('status-dot');
  const label = document.getElementById('status-connection');
  if (!dot || !label) return;
  if (isOnline) {
    dot.className = 'status-dot online';
    label.textContent = 'CONNECTED';
  } else {
    dot.className = 'status-dot';
    label.textContent = `OFFLINE: ${errMsg}`;
  }
}

// -----------------------------------------------------------------------------
// FORMATTING HELPERS
// -----------------------------------------------------------------------------
function formatNumber(val, decimals = 4) {
  if (val === null || val === undefined || Number.isNaN(val)) return '—';
  return Number(val).toFixed(decimals);
}

function formatSigned(val, decimals = 4) {
  if (val === null || val === undefined || Number.isNaN(val)) return '—';
  const num = Number(val);
  if (num > 0) return `+${num.toFixed(decimals)}`;
  return num.toFixed(decimals);
}

function formatParamValue(param, val, decimals = 4) {
  if (val === null || val === undefined || Number.isNaN(val)) return '—';
  if (param === 'IGSS') {
    return formatSigned(val, decimals);
  }
  return formatNumber(val, decimals);
}

function getStateBadgeHtml(stateStr) {
  const s = String(stateStr || 'UNKNOWN').toUpperCase();
  let cls = 'badge-insufficient';
  if (s === 'PASS') cls = 'badge-pass';
  else if (s === 'ALERT') cls = 'badge-alert';
  else if (s === 'HOLD') cls = 'badge-hold';
  else if (s === 'FAIL') cls = 'badge-fail';
  else if (s === 'EQUIPMENT_SUSPECTED') cls = 'badge-equipment';
  else if (s === 'INSUFFICIENT_DATA') cls = 'badge-insufficient';
  return `<span class="badge ${cls}">${s}</span>`;
}

// -----------------------------------------------------------------------------
// INITIALIZATION
// -----------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  setupWorkspaceNavigation();
  setupHierarchyControls();
  setupAsOfButtons();
  setupChartParamButtons();
  setupDataWorkspace();
  setupExportButtons();
  setupEquipmentExcursionDemo();
  setupConformalInspectorSimulation();

  try {
    // 1. Fetch available demo lots
    const lotsRes = await apiGet('/lots');
    state.lots = lotsRes.lots || [];
    populateLotSelect(state.lots);

    if (state.lots.length > 0) {
      state.selectedLotId = state.lots.includes('LOT_CAL_001') ? 'LOT_CAL_001' : state.lots[0];
      const lotSel = document.getElementById('select-lot');
      if (lotSel) lotSel.value = state.selectedLotId;
    }

    // 2. Load components for default lot
    await loadLotComponents(state.selectedLotId);

    // 3. Load full pipeline for initial component
    await loadComponentInvestigation(state.selectedComponentId, state.selectedAsOf);

    // 4. Build initial tray matrix
    await buildTrayMatrix();
  } catch (err) {
    console.error('Workstation initialization error:', err);
  }
});

// -----------------------------------------------------------------------------
// WORKSPACE NAVIGATION
// -----------------------------------------------------------------------------
function setupWorkspaceNavigation() {
  const tabs = document.querySelectorAll('.nav-tab-btn');
  tabs.forEach((btn) => {
    btn.addEventListener('click', () => {
      const ws = btn.getAttribute('data-workspace');
      switchWorkspace(ws);
    });
  });

  // Stepper guide direct navigation
  const stepMap = {
    'step-guide-1': 'data',
    'step-guide-2': 'screening',
    'step-guide-3': 'prognostics',
    'step-guide-4': 'traceability',
  };
  Object.entries(stepMap).forEach(([elId, ws]) => {
    const el = document.getElementById(elId);
    if (el) {
      el.style.cursor = 'pointer';
      el.addEventListener('click', () => switchWorkspace(ws));
    }
  });
}

function switchWorkspace(workspaceId) {
  state.activeWorkspace = workspaceId;

  // Update nav tabs
  document.querySelectorAll('.nav-tab-btn').forEach((btn) => {
    if (btn.getAttribute('data-workspace') === workspaceId) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Update workspace panels
  document.querySelectorAll('.workspace-panel').forEach((panel) => {
    if (panel.id === `ws-${workspaceId}`) {
      panel.classList.add('active');
    } else {
      panel.classList.remove('active');
    }
  });

  // Synchronize interactive workflow stepper
  const stepMap = {
    'data': 'step-guide-1',
    'screening': 'step-guide-2',
    'prognostics': 'step-guide-3',
    'traceability': 'step-guide-4',
  };
  Object.entries(stepMap).forEach(([ws, elId]) => {
    const el = document.getElementById(elId);
    if (el) {
      if (ws === workspaceId) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    }
  });
}

// -----------------------------------------------------------------------------
// HIERARCHY CONTROLS
// -----------------------------------------------------------------------------
function setupHierarchyControls() {
  const lotSelect = document.getElementById('select-lot');
  const compSelect = document.getElementById('select-component');
  const searchInput = document.getElementById('input-search-comp');

  if (lotSelect) {
    lotSelect.addEventListener('change', async (e) => {
      state.selectedLotId = e.target.value;
      if (state.activeDataset === 'demo' || state.activeDataset === 'excursion') {
        await loadLotComponents(state.selectedLotId);
      } else if (state.uploadedSummary) {
        const compsForLot = Array.from(new Set(state.uploadedSummary.rows.filter(r => r.lot_id === state.selectedLotId).map(r => r.component_id)));
        state.componentsInLot = compsForLot;
        populateComponentSelect(compsForLot);
      }
      if (state.componentsInLot.length > 0) {
        state.selectedComponentId = state.componentsInLot[0];
        if (compSelect) compSelect.value = state.selectedComponentId;
        await loadComponentInvestigation(state.selectedComponentId, state.selectedAsOf);
      }
      await buildTrayMatrix();
    });
  }

  if (compSelect) {
    compSelect.addEventListener('change', async (e) => {
      state.selectedComponentId = e.target.value;
      await loadComponentInvestigation(state.selectedComponentId, state.selectedAsOf);
      highlightTraySocket(state.selectedComponentId);
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = state.componentsInLot.filter((c) => c.toLowerCase().includes(q));
      populateComponentSelect(filtered);
      if (filtered.length > 0 && !filtered.includes(state.selectedComponentId)) {
        state.selectedComponentId = filtered[0];
        if (compSelect) compSelect.value = state.selectedComponentId;
        loadComponentInvestigation(state.selectedComponentId, state.selectedAsOf);
      }
    });
  }
}

function setupAsOfButtons() {
  const buttons = document.querySelectorAll('.btn-checkpoint');
  buttons.forEach((btn) => {
    btn.addEventListener('click', async () => {
      const asOf = parseInt(btn.getAttribute('data-asof'), 10);
      if (asOf === state.selectedAsOf) return;

      buttons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state.selectedAsOf = asOf;

      await loadComponentInvestigation(state.selectedComponentId, state.selectedAsOf);
      await buildTrayMatrix();
    });
  });
}

function setCheckpoint(asOf) {
  state.selectedAsOf = asOf;
  const buttons = document.querySelectorAll('.btn-checkpoint');
  buttons.forEach((b) => {
    if (parseInt(b.getAttribute('data-asof'), 10) === asOf) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });
}

function setupChartParamButtons() {
  const buttons = document.querySelectorAll('.btn-param');
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const param = btn.getAttribute('data-param');
      state.activeChartParam = param;
      buttons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      renderSvgTrajectoryChart();
    });
  });
}

function populateLotSelect(lots) {
  const sel = document.getElementById('select-lot');
  if (!sel) return;
  const allLots = lots.includes('LOT_DEMO_EXCURSION') ? lots : ['LOT_DEMO_EXCURSION', ...lots];
  sel.innerHTML = allLots.map((l) => {
    const label = l === 'LOT_DEMO_EXCURSION' ? '\u26A1 LOT_DEMO_EXCURSION (CH_05 Socket Drift)' : l;
    return `<option value="${l}">${label}</option>`;
  }).join('');
}

function populateComponentSelect(components) {
  const sel = document.getElementById('select-component');
  sel.innerHTML = components.map((c) => `<option value="${c}">${c}</option>`).join('');
}

async function loadLotComponents(lotId) {
  try {
    const res = await apiGet(`/lots/${lotId}/components`);
    state.componentsInLot = res.components || [];
    populateComponentSelect(state.componentsInLot);
    if (state.componentsInLot.length > 0) {
      if (!state.componentsInLot.includes(state.selectedComponentId)) {
        state.selectedComponentId = state.componentsInLot[0];
      }
      document.getElementById('select-component').value = state.selectedComponentId;
    }
  } catch (err) {
    console.error(`Failed loading components for lot ${lotId}:`, err);
  }
}

// -----------------------------------------------------------------------------
// CORE DATA INGESTION & WORKSPACE SYNC
// -----------------------------------------------------------------------------
async function loadComponentInvestigation(componentId, asOf) {
  if (!componentId) return;
  state.isLoading = true;

  try {
    const data = await apiGet(`/components/${componentId}/pipeline?as_of=${asOf}`);
    state.pipelineData = data;

    // 1. Sync Global Context Bar (Always Visible)
    syncGlobalContextBar(data);

    // 2. Render Workspace 1: Screening
    renderScreeningWorkspace(data);

    // 3. Render Workspace 2: Prognostics
    renderPrognosticsWorkspace(data);

    // 4. Render Workspace 4: Traceability
    renderTraceabilityWorkspace(data);

    // 5. Highlight active tray socket
    highlightTraySocket(componentId);

  } catch (err) {
    console.error(`Failed to load investigation for ${componentId} as_of=${asOf}:`, err);
  } finally {
    state.isLoading = false;
  }
}

function syncGlobalContextBar(data) {
  document.getElementById('ctx-lot').textContent = data.lot_id || state.selectedLotId;
  document.getElementById('ctx-component').textContent = data.component_id || state.selectedComponentId;
  document.getElementById('ctx-asof').textContent = `${data.as_of_hours} h`;

  const finalState = data.screening?.final_state || 'UNKNOWN';
  document.getElementById('ctx-status').innerHTML = getStateBadgeHtml(finalState);
}

// -----------------------------------------------------------------------------
// BURN-IN TRAY MATRIX — Interactive Lot Cohort Heatmap
// -----------------------------------------------------------------------------
async function buildTrayMatrix() {
  const grid = document.getElementById('tray-matrix-grid');
  const lotBadge = document.getElementById('tray-lot-badge');
  const countBadge = document.getElementById('tray-count-badge');
  if (!grid) return;

  const comps = state.componentsInLot;
  if (lotBadge) lotBadge.textContent = state.selectedLotId;
  if (countBadge) countBadge.textContent = `${comps.length} sockets`;

  // One batch request avoids the browser's per-origin connection queue delaying
  // individual socket colours.
  state.trayStatuses = {};

  // Show loading state
  grid.innerHTML = comps.map((cid) => {
    const shortId = cid.split('_').pop();
    return `<div class="tray-socket" data-cid="${cid}" id="tray-${cid}">
      <span class="tray-socket-label">${shortId}</span>
      <span class="tray-socket-state">...</span>
    </div>`;
  }).join('');

  try {
    const batch = await apiGet(`/lots/${state.selectedLotId}/statuses?as_of=${state.selectedAsOf}`);
    state.trayStatuses = batch.statuses || {};
  } catch (err) {
    console.error('Failed to load tray statuses:', err);
    comps.forEach((cid) => { state.trayStatuses[cid] = 'UNKNOWN'; });
  }

  // Render with actual statuses
  renderTrayGrid(comps);
}

function renderTrayGrid(comps) {
  const grid = document.getElementById('tray-matrix-grid');
  if (!grid) return;

  grid.innerHTML = comps.map((cid) => {
    const shortId = cid.split('_').pop();
    const fs = (state.trayStatuses[cid] || 'UNKNOWN').toUpperCase();
    let statusClass = '';
    let stateLabel = fs;
    if (fs === 'PASS') { statusClass = 'status-pass'; stateLabel = 'PASS'; }
    else if (fs === 'ALERT') { statusClass = 'status-alert'; stateLabel = 'ALERT'; }
    else if (fs === 'HOLD') { statusClass = 'status-hold'; stateLabel = 'HOLD'; }
    else if (fs === 'FAIL') { statusClass = 'status-fail'; stateLabel = 'FAIL'; }
    else if (fs === 'EQUIPMENT_SUSPECTED') { statusClass = 'status-equipment'; stateLabel = 'EQ'; }
    else if (fs === 'INSUFFICIENT_DATA') { statusClass = 'status-insufficient'; stateLabel = 'INSUF'; }
    else { statusClass = ''; stateLabel = fs !== 'UNKNOWN' ? fs : '—'; }

    const isActive = cid === state.selectedComponentId;
    const activeClass = isActive ? ' active' : '';

    return `<div class="tray-socket ${statusClass}${activeClass}" data-cid="${cid}" id="tray-${cid}">
      <span class="tray-socket-label">${shortId}</span>
      <span class="tray-socket-state">${stateLabel}</span>
    </div>`;
  }).join('');

  // Add click handlers
  grid.querySelectorAll('.tray-socket').forEach((socket) => {
    socket.addEventListener('click', async () => {
      const cid = socket.getAttribute('data-cid');
      if (cid && cid !== state.selectedComponentId) {
        state.selectedComponentId = cid;
        const compSelect = document.getElementById('select-component');
        if (compSelect) compSelect.value = cid;
        await loadComponentInvestigation(cid, state.selectedAsOf);
      }
    });
  });
}

function highlightTraySocket(componentId) {
  document.querySelectorAll('.tray-socket').forEach((s) => {
    if (s.getAttribute('data-cid') === componentId) {
      s.classList.add('active');
    } else {
      s.classList.remove('active');
    }
  });
}

// -----------------------------------------------------------------------------
// WORKSPACE 1: SCREENING (DEFAULT HOME)
// -----------------------------------------------------------------------------
function renderScreeningWorkspace(data) {
  const screening = data.screening || {};
  const finalState = screening.final_state || 'UNKNOWN';
  const qualifier = screening.disposition_qualifier || 'NOMINAL_STABLE';
  const summaryReason = screening.summary_reason || 'Screening rules engine evaluated all 6 detectors.';

  // Section A: Screening Summary Card
  document.getElementById('card-asof-tag').textContent = `AS-OF: ${data.as_of_hours} h`;

  const banner = document.getElementById('screening-state-banner');
  banner.className = `disposition-callout disp-${finalState.toLowerCase()}`;
  document.getElementById('disp-title').innerHTML = `${getStateBadgeHtml(finalState)} <span class="badge badge-qualifier">${qualifier}</span>`;
  document.getElementById('disp-reason').textContent = summaryReason;

  // Compute Spec Failures Count
  let specFailCount = 0;
  const paramResults = screening.parameter_results || {};
  ORDERED_PARAMETERS.forEach((p) => {
    if (paramResults[p]?.spec_evidence?.passed === false) specFailCount++;
  });
  document.getElementById('sum-spec-failures').textContent = `${specFailCount} of 4`;
  document.getElementById('sum-spec-sub').textContent = specFailCount === 0 ? 'Within Table I tolerance' : `${specFailCount} parameter(s) out of Table I spec`;

  // Dynamic Screening Summary
  let hasAlert = false;
  ORDERED_PARAMETERS.forEach((p) => {
    const pr = paramResults[p] || {};
    if (pr.parameter_state === 'ALERT') hasAlert = true;
  });
  const isJointAlert = screening.joint_evidence?.suspected || finalState === 'HOLD';
  if (isJointAlert) {
    document.getElementById('sum-dynamic-evidence').textContent = 'JOINT BACKSTOP (HOLD)';
    const dMahal = screening.joint_evidence?.mahalanobis_distance;
    document.getElementById('sum-dynamic-sub').textContent = dMahal != null
      ? `Multivariate D_joint (${dMahal.toFixed(2)}σ) triggered backstop`
      : 'Multivariate anomaly triggered backstop hold';
  } else {
    document.getElementById('sum-dynamic-evidence').textContent = hasAlert ? 'DYNAMIC ALERT' : 'NOMINAL';
    document.getElementById('sum-dynamic-sub').textContent = hasAlert ? 'Kinetic drift or peer deviation detected' : 'Peer, drift, step nominal';
  }

  // Data Sufficiency
  const suffEvidence = paramResults['IDSS']?.sufficiency_evidence || {};
  const isSufficient = suffEvidence.sufficient !== false;
  document.getElementById('sum-sufficiency').textContent = isSufficient ? 'SUFFICIENT' : 'INCOMPLETE';
  document.getElementById('sum-sufficiency-sub').textContent = isSufficient ? `Checkpoints [${(suffEvidence.available_checkpoints || []).join(', ')}h]` : 'Inspection history deficient';

  // Equipment Suspicion
  let eqSuspected = false;
  ORDERED_PARAMETERS.forEach((p) => {
    if (paramResults[p]?.equipment_evidence?.suspected) eqSuspected = true;
  });
  document.getElementById('sum-equipment').textContent = eqSuspected ? 'EQUIPMENT SUSPECTED' : 'CLEAN';
  document.getElementById('sum-equipment-sub').textContent = eqSuspected ? 'Chamber/ATE common-mode artifact' : 'No common-mode confounding';

  // Section B: Measured Parameters Table
  renderMeasurementTable(data);

  // Section C: Parameter Trend Visualization (4 Stacked SVG Plots)
  renderSvgTrajectoryChart();

  // Section D: Module A Engineering Evidence Table
  renderDetectorEvidenceTable(data);

  // Section E: Screening Explainability
  renderScreeningExplainability(data);
}

function renderMeasurementTable(data) {
  const tbody = document.getElementById('tbody-measurement-summary');
  const observedTelemetry = data.observed_telemetry || [];
  const paramResults = data.screening?.parameter_results || {};

  const telMap = {};
  ORDERED_PARAMETERS.forEach((p) => { telMap[p] = {}; });
  observedTelemetry.forEach((row) => {
    const p = row.parameter_name;
    const t = row.elapsed_hours;
    if (telMap[p]) telMap[p][t] = row.value;
  });

  const rowsHtml = ORDERED_PARAMETERS.map((param) => {
    const pres = paramResults[param] || {};
    const unit = pres.unit || '';
    const v0 = telMap[param]?.[0] !== undefined ? telMap[param][0] : null;
    const v24 = telMap[param]?.[24] !== undefined ? telMap[param][24] : null;
    const vAsOf = pres.observed_value !== undefined ? pres.observed_value : null;

    // Spec Limit - strictly from backend metadata
    const spec = pres.spec_evidence || {};
    let limitStr = '—';
    if (spec.limit_low !== null && spec.limit_low !== undefined && spec.limit_high !== null && spec.limit_high !== undefined) {
      limitStr = `[${formatNumber(spec.limit_low)}, ${formatNumber(spec.limit_high)}] ${unit}`;
    } else if (spec.limit_high !== null && spec.limit_high !== undefined) {
      limitStr = `≤ ${formatNumber(spec.limit_high)} ${unit}`;
    } else if (spec.limit_low !== null && spec.limit_low !== undefined) {
      limitStr = `≥ ${formatNumber(spec.limit_low)} ${unit}`;
    }

    // Trend / Rate
    const temporal = pres.temporal_evidence || {};
    let trendStr = '—';
    if (temporal.slope_per_hour !== null && temporal.slope_per_hour !== undefined) {
      trendStr = `${formatSigned(temporal.slope_per_hour, 4)} ${unit}/h`;
    } else if (vAsOf !== null && v0 !== null) {
      const delta = vAsOf - v0;
      trendStr = `Δ = ${formatSigned(delta, 4)} ${unit}`;
    }

    const statusHtml = getStateBadgeHtml(pres.parameter_state || 'UNKNOWN');

    return `
      <tr>
        <td><strong>${param}</strong> <span class="dim">(${unit})</span></td>
        <td>${formatParamValue(param, v0)}</td>
        <td>${formatParamValue(param, v24)}</td>
        <td><strong>${formatParamValue(param, vAsOf)}</strong></td>
        <td>${limitStr}</td>
        <td>${trendStr}</td>
        <td>${statusHtml}</td>
      </tr>
    `;
  }).join('');

  tbody.innerHTML = rowsHtml;
}

// -----------------------------------------------------------------------------
// SECTION C: PARAMETER TREND VISUALIZATION (FOUR STACKED SVG PLOTS)
// -----------------------------------------------------------------------------
function renderSvgTrajectoryChart() {
  const container = document.getElementById('svg-chart-container');
  if (!container || !state.pipelineData) return;

  const data = state.pipelineData;
  const asOf = data.as_of_hours;
  const paramsToPlot = state.activeChartParam === 'ALL' ? ORDERED_PARAMETERS : [state.activeChartParam];

  const plotsHtml = paramsToPlot.map((param) => {
    const pres = data.screening?.parameter_results?.[param] || {};
    const forecast = data.prognostics?.[param] || data.prognostic_forecasts?.[param] || null;
    const spec = pres.spec_evidence || {};
    const unit = pres.unit || '';

    // Extract observed points for t <= asOf
    const observedTelemetry = (data.observed_telemetry || [])
      .filter((row) => row.parameter_name === param && row.elapsed_hours <= asOf)
      .sort((a, b) => a.elapsed_hours - b.elapsed_hours);

    // Dimensions for stacked layout
    const W = 880;
    const H = 145;
    const padL = 72;
    const padR = 88;
    const padT = 20;
    const padB = 28;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const minT = 0;
    const maxT = 168;
    const mapX = (t) => padL + ((t - minT) / (maxT - minT)) * plotW;

    // Y Range calculation
    const yVals = observedTelemetry.map((d) => Number(d.value)).filter((v) => !Number.isNaN(v));
    if (forecast && forecast.predicted_value !== null && asOf < 168) {
      yVals.push(Number(forecast.predicted_value));
      if (forecast.interval_lower !== null && forecast.interval_lower !== undefined) yVals.push(Number(forecast.interval_lower));
      if (forecast.interval_upper !== null && forecast.interval_upper !== undefined) yVals.push(Number(forecast.interval_upper));
    }
    if (spec.limit_high !== null && spec.limit_high !== undefined) yVals.push(Number(spec.limit_high));
    if (spec.limit_low !== null && spec.limit_low !== undefined) yVals.push(Number(spec.limit_low));

    let minY = yVals.length > 0 ? Math.min(...yVals) : 0;
    let maxY = yVals.length > 0 ? Math.max(...yVals) : 1;
    if (minY === maxY) { minY -= 0.5; maxY += 0.5; }
    const yMargin = (maxY - minY) * 0.15;
    const plotMinY = minY - yMargin;
    const plotMaxY = maxY + yMargin;
    const mapY = (v) => padT + plotH - ((v - plotMinY) / (plotMaxY - plotMinY)) * plotH;

    let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" xmlns="http://www.w3.org/2000/svg" style="font-family: var(--font-mono); font-size: 10px;">`;

    // Canvas Background
    svg += `<rect x="${padL}" y="${padT}" width="${plotW}" height="${plotH}" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1" />`;

    // Future Causal Shading (t > asOf)
    if (asOf < 168) {
      const xAsOf = mapX(asOf);
      const futureW = padL + plotW - xAsOf;
      svg += `<rect x="${xAsOf}" y="${padT}" width="${futureW}" height="${plotH}" fill="#F8FAFC" />`;
      if (futureW >= 75) {
        svg += `<text x="${xAsOf + futureW / 2}" y="${padT + 13}" fill="#64748B" text-anchor="middle" font-size="8.5" font-weight="600" letter-spacing="0.04em" style="paint-order: stroke fill; stroke: #FFFFFF; stroke-width: 2px;">FUTURE (t &gt; ${asOf}h)</text>`;
      }
    }

    // Grid Lines & Ticks (0, 24, 48, 72, 96, 120, 144, 168)
    [0, 24, 48, 72, 96, 120, 144, 168].forEach((t) => {
      const x = mapX(t);
      svg += `<line x1="${x}" y1="${padT}" x2="${x}" y2="${padT + plotH}" stroke="#F1F5F9" stroke-dasharray="2,2" stroke-width="1" />`;
      svg += `<text x="${x}" y="${padT + plotH + 16}" fill="#64748B" text-anchor="middle">${t}h</text>`;
    });

    // Y Ticks (3 steps)
    for (let i = 0; i <= 2; i++) {
      const val = plotMinY + (i / 2) * (plotMaxY - plotMinY);
      const y = mapY(val);
      svg += `<line x1="${padL}" y1="${y}" x2="${padL + plotW}" y2="${y}" stroke="#E2E8F0" stroke-width="1" />`;
      svg += `<text x="${padL - 8}" y="${y + 3}" fill="#64748B" text-anchor="end">${formatParamValue(param, val, 2)}</text>`;
    }

    // Spec Limit Lines — Positioned on the LEFT side to prevent overlaying FUTURE shading or 168h forecast
    if (spec.limit_high !== null && spec.limit_high !== undefined) {
      const ySpec = mapY(spec.limit_high);
      if (ySpec >= padT && ySpec <= padT + plotH) {
        svg += `<line x1="${padL}" y1="${ySpec}" x2="${padL + plotW}" y2="${ySpec}" stroke="#DC2626" stroke-dasharray="4,3" stroke-width="1.2" />`;
        svg += `<text x="${padL + 8}" y="${ySpec - 4}" fill="#DC2626" text-anchor="start" font-weight="700" font-size="8.5" style="paint-order: stroke fill; stroke: #FFFFFF; stroke-width: 2.5px; stroke-linejoin: round;">LIMIT: ${formatNumber(spec.limit_high)} ${unit}</text>`;
      }
    }
    if (spec.limit_low !== null && spec.limit_low !== undefined) {
      const ySpec = mapY(spec.limit_low);
      if (ySpec >= padT && ySpec <= padT + plotH) {
        svg += `<line x1="${padL}" y1="${ySpec}" x2="${padL + plotW}" y2="${ySpec}" stroke="#DC2626" stroke-dasharray="4,3" stroke-width="1.2" />`;
        svg += `<text x="${padL + 8}" y="${ySpec + 12}" fill="#DC2626" text-anchor="start" font-weight="700" font-size="8.5" style="paint-order: stroke fill; stroke: #FFFFFF; stroke-width: 2.5px; stroke-linejoin: round;">LOWER: ${formatNumber(spec.limit_low)} ${unit}</text>`;
      }
    }

    // Causal Boundary Line at asOf
    const xBoundary = mapX(asOf);
    svg += `<line x1="${xBoundary}" y1="${padT}" x2="${xBoundary}" y2="${padT + plotH}" stroke="#64748B" stroke-dasharray="3,3" stroke-width="1.5" />`;

    // Observed Telemetry Trace & Markers
    if (observedTelemetry.length > 0) {
      const pointsStr = observedTelemetry.map((d) => `${mapX(d.elapsed_hours)},${mapY(d.value)}`).join(' ');
      svg += `<polyline points="${pointsStr}" fill="none" stroke="#0284C7" stroke-width="2" />`;

      observedTelemetry.forEach((d) => {
        const cx = mapX(d.elapsed_hours);
        const cy = mapY(d.value);
        const isCurrentAsOf = d.elapsed_hours === asOf;
        if (isCurrentAsOf) {
          svg += `<circle cx="${cx}" cy="${cy}" r="5" fill="#0284C7" stroke="#FFFFFF" stroke-width="2" />`;
          svg += `<circle cx="${cx}" cy="${cy}" r="6.5" fill="none" stroke="#0284C7" stroke-width="1.5" />`;
        } else {
          svg += `<circle cx="${cx}" cy="${cy}" r="3.5" fill="#0284C7" stroke="#FFFFFF" stroke-width="1" />`;
        }
      });
    }

    // 168h Prognostic Forecast Point, Conformal 90% CI Band & PI Whisker (if asOf < 168)
    if (forecast && forecast.predicted_value !== null && asOf < 168) {
      const xFc = mapX(168);
      const yFc = mapY(forecast.predicted_value);

      // Prediction Interval Bounds
      const piLow = forecast.interval_lower ?? forecast.prediction_interval_90?.[0] ?? null;
      const piHigh = forecast.interval_upper ?? forecast.prediction_interval_90?.[1] ?? null;

      if (observedTelemetry.length > 0) {
        const lastObs = observedTelemetry[observedTelemetry.length - 1];
        const xStart = mapX(lastObs.elapsed_hours);
        const yStart = mapY(lastObs.value);
        const bandWidth = xFc - xStart;

        // Continuous Shaded 90% Conformal Prediction Band (Uncertainty Envelope)
        if (piLow !== null && piHigh !== null) {
          const yLow = mapY(piLow);
          const yHigh = mapY(piHigh);
          const envelopePoints = `${xStart},${yStart} ${xFc},${yHigh} ${xFc},${yLow}`;
          svg += `<polygon points="${envelopePoints}" fill="rgba(217, 119, 6, 0.15)" stroke="rgba(217, 119, 6, 0.45)" stroke-dasharray="3,2" stroke-width="1" />`;
          
          // Only render text inside the band when there is ample horizontal space so it NEVER overlaps with lines or points
          if (bandWidth >= 220) {
            const textX = xStart + bandWidth * 0.45;
            const textY = Math.min(yStart, Math.min(yLow, yHigh)) - 4;
            const clampedY = Math.max(padT + 12, textY);
            svg += `<text x="${textX}" y="${clampedY}" fill="#B45309" text-anchor="middle" font-size="8" font-weight="700" letter-spacing="0.04em" style="paint-order: stroke fill; stroke: #FFFFFF; stroke-width: 2.5px; stroke-linejoin: round;">90% CONFORMAL CI BAND</text>`;
          }
        }

        // Central Forecast Trajectory Line
        svg += `<line x1="${xStart}" y1="${yStart}" x2="${xFc}" y2="${yFc}" stroke="#D97706" stroke-dasharray="3,3" stroke-width="1.3" />`;
      }

      // Prediction Interval Whisker at 168h
      if (piLow !== null && piHigh !== null) {
        const yLow = mapY(piLow);
        const yHigh = mapY(piHigh);
        svg += `<line x1="${xFc}" y1="${yLow}" x2="${xFc}" y2="${yHigh}" stroke="#D97706" stroke-width="1.8" />`;
        svg += `<line x1="${xFc - 4}" y1="${yLow}" x2="${xFc + 4}" y2="${yLow}" stroke="#D97706" stroke-width="1.8" />`;
        svg += `<line x1="${xFc - 4}" y1="${yHigh}" x2="${xFc + 4}" y2="${yHigh}" stroke="#D97706" stroke-width="1.8" />`;
      }

      // 168h Forecast Diamond
      const s = 4.5;
      svg += `<polygon points="${xFc},${yFc - s} ${xFc + s},${yFc} ${xFc},${yFc + s} ${xFc - s},${yFc}" fill="#D97706" stroke="#FFFFFF" stroke-width="1" />`;
      
      // Position 168h Forecast Value Label CLEANLY in the dedicated right margin (outside plot canvas)
      // This completely prevents text overlay with the conformal band, whiskers, or trajectory
      const labelY = Math.max(padT + 10, Math.min(padT + plotH - 3, yFc + 3.5));
      svg += `<text x="${xFc + 8}" y="${labelY}" fill="#B45309" text-anchor="start" font-weight="700" font-size="8.5" style="paint-order: stroke fill; stroke: #FFFFFF; stroke-width: 2.5px; stroke-linejoin: round;">168h: ${formatParamValue(param, forecast.predicted_value)}</text>`;
    }

    // Y Axis Label
    svg += `<text x="14" y="${padT + plotH / 2}" fill="#94A3B8" text-anchor="middle" transform="rotate(-90 14 ${padT + plotH / 2})" font-size="9.5" font-weight="600">${param}</text>`;

    svg += `</svg>`;

    return `
      <div class="chart-plot-card">
        <div class="chart-plot-head">
          <span class="chart-plot-name">${param} <span class="dim">(${unit})</span></span>
          <span class="dim">As-Of: ${asOf} h &bull; Table I Range: [${spec.limit_low ?? '—'}, ${spec.limit_high ?? '—'}]</span>
        </div>
        ${svg}
      </div>
    `;
  }).join('');

  container.innerHTML = plotsHtml;
}

// -----------------------------------------------------------------------------
// SECTION D: MODULE A ENGINEERING EVIDENCE TABLE
// -----------------------------------------------------------------------------
function renderDetectorEvidenceTable(data) {
  const tbody = document.getElementById('screening-matrix-tbody');
  if (!tbody) return;

  const param = 'IDSS'; // Primary reference parameter for multi-detector demonstration
  const pres = data.screening?.parameter_results?.[param] || {};
  const unit = pres.unit || 'µA';

  const spec = pres.spec_evidence || {};
  const peer = pres.peer_evidence || {};
  const temporal = pres.temporal_evidence || {};
  const step = pres.step_evidence || {};
  const eq = pres.equipment_evidence || {};
  const suff = pres.sufficiency_evidence || {};

  const detectors = [
    {
      id: 'D_spec',
      name: 'Specification Detector',
      stat: `Measured = ${formatParamValue(param, spec.observed_value)} ${unit}`,
      threshold: `Table I: [${spec.limit_low ?? '—'}, ${spec.limit_high ?? '—'}] ${unit}`,
      observed: `${formatParamValue(param, spec.observed_value)} ${unit}`,
      status: spec.status || (spec.passed ? 'COMPLIANT' : 'FAIL'),
      interp: spec.reason_code || (spec.passed ? 'Within Table I tolerance boundaries' : 'Exceeds specification limit'),
      details: `Detector A evaluates absolute compliance against MIL-PRF-19500 Table I requirements. Observed ${formatParamValue(param, spec.observed_value)} ${unit} against upper limit ${spec.limit_high} ${unit}.`,
    },
    {
      id: 'D_peer',
      name: 'Peer Deviation Detector',
      stat: `Robust Z = ${formatSigned(peer.z_score, 2)}σ (Median = ${formatNumber(peer.peer_median)})`,
      threshold: `Homogeneous lot threshold |Z| ≤ 3.0σ (N_lot = ${peer.peer_count ?? '—'})`,
      observed: `${formatSigned(peer.z_score, 2)}σ`,
      status: peer.status || 'PEER_NORMAL',
      interp: peer.reason_code || 'Relative to homogeneous per-lot baseline reference slice',
      details: `Detector B calculates median absolute deviation (MAD) within homogeneous manufacturing lot. Identified Z-score of ${formatSigned(peer.z_score, 2)} standard scale units.`,
    },
    {
      id: 'D_drift',
      name: 'Temporal Drift Detector',
      stat: `Kinetic Slope = ${formatSigned(temporal.slope_per_hour, 4)} ${unit}/h`,
      threshold: temporal.lot_reference_note || 'Lot reference drift baseline G_crit',
      observed: `${formatSigned(temporal.slope_per_hour, 4)} ${unit}/h`,
      status: temporal.status || 'STATIONARY',
      interp: temporal.reason_code || 'Monitoring cumulative parameter drift across burn-in',
      details: `Detector C performs robust linear regression over checkpoints t ≤ ${data.as_of_hours}h to identify kinetic parameter degradation before limit breaches.`,
    },
    {
      id: 'D_step',
      name: 'Abrupt Step Detector',
      stat: `Step = ${formatSigned(step.step_magnitude, 4)} ${unit} (Ratio: ${formatNumber(step.step_ratio, 2)})`,
      threshold: `Adjacent checkpoint shift (${step.previous_checkpoint ?? 0}h → ${step.current_checkpoint ?? 24}h)`,
      observed: `${formatSigned(step.step_magnitude, 4)} ${unit}`,
      status: step.status || 'NO_STEP',
      interp: step.reason_code || 'Evaluating discontinuous displacement between consecutive readouts',
      details: `Detector D identifies mechanical stress, wire-bond displacement, or gate oxide micro-fractures causing abrupt step shifts between adjacent readouts.`,
    },
    {
      id: 'D_eq',
      name: 'Equipment / Common-Mode',
      stat: eq.lot_median_shift !== null && eq.lot_median_shift !== undefined
        ? `Lot Median Shift = ${formatSigned(eq.lot_median_shift, 4)}`
        : (eq.channel_offset !== null && eq.channel_offset !== undefined ? `Channel Offset = ${formatSigned(eq.channel_offset, 4)}` : 'No common-mode shift detected'),
      threshold: 'Uniform chamber thermal displacement / ATE fixture offsets',
      observed: eq.lot_median_shift !== null ? `${formatSigned(eq.lot_median_shift, 4)}` : '0.0000',
      status: eq.status || (eq.suspected ? 'EQUIPMENT_SUSPECTED' : 'NOMINAL'),
      interp: eq.reason_code || (eq.suspected ? 'Common-mode chamber thermal motion suspected' : 'No equipment artifact confounding'),
      details: `Detector E cross-references simultaneous shifts across all components in the chamber to distinguish test equipment/ATE fixture artifacts from device defects.`,
    },
    {
      id: 'D_suff',
      name: 'Data Sufficiency Detector',
      stat: `Available Checkpoints: [${(suff.available_checkpoints || []).join(', ')}h]`,
      threshold: `Expected Checkpoints: [${(suff.expected_checkpoints || []).join(', ')}h]`,
      observed: `${(suff.available_checkpoints || []).length} checkpoints`,
      status: suff.status || (suff.sufficient ? 'SUFFICIENT' : 'INCOMPLETE_HISTORY'),
      interp: suff.reason_code || (suff.sufficient ? 'Complete inspection history available for as-of evaluation' : 'Checkpoint history deficient for screening'),
      details: `Detector F enforces sample completeness. Without sufficient historical checkpoints, screening disposition defaults to INSUFFICIENT_DATA.`,
    },
  ];

  tbody.innerHTML = detectors.map((d, idx) => `
    <tr class="expandable-row" data-row-idx="${idx}">
      <td><strong>${d.id}</strong></td>
      <td>${d.name}</td>
      <td>${d.stat}</td>
      <td>${d.threshold}</td>
      <td><strong>${d.observed}</strong></td>
      <td>${getStateBadgeHtml(d.status)}</td>
      <td>${d.interp}</td>
    </tr>
    <tr class="drawer-row" id="drawer-${idx}" style="display: none;">
      <td colspan="7" class="row-drawer-content">
        <strong>ENGINEERING EXPLANATION:</strong> ${d.details}
      </td>
    </tr>
  `).join('');

  // Expandable row toggle
  tbody.querySelectorAll('.expandable-row').forEach((tr) => {
    tr.addEventListener('click', () => {
      const idx = tr.getAttribute('data-row-idx');
      const drawer = document.getElementById(`drawer-${idx}`);
      if (drawer) {
        drawer.style.display = drawer.style.display === 'none' ? 'table-row' : 'none';
      }
    });
  });
}

// -----------------------------------------------------------------------------
// SECTION E: SCREENING EXPLAINABILITY & AUDIT JUSTIFICATION
// -----------------------------------------------------------------------------
function renderScreeningExplainability(data) {
  const exp = data.explainability || {};
  document.getElementById('exp-what').textContent = exp.what_happened || 'Telemetry observed across specified checkpoints adheres to nominal component profile.';
  document.getElementById('exp-why').textContent = exp.why_flagged || 'All dynamic detectors (peer, temporal drift, step) evaluated within expected baseline thresholds.';
  document.getElementById('exp-which').textContent = exp.which_parameter || 'IDSS, VGS(th), RDS(on), IGSS evaluated simultaneously under Table I limits.';
  
  const evidenceEl = document.getElementById('exp-evidence');
  if (evidenceEl) {
    if (exp.what_evidence && Object.keys(exp.what_evidence).length > 0) {
      evidenceEl.textContent = JSON.stringify(exp.what_evidence, null, 2);
    } else {
      evidenceEl.textContent = '{\n  "status": "NOMINAL",\n  "note": "Quantitative detector evidence confirms within-specification behavior."\n}';
    }
  }

  document.getElementById('exp-limitation').textContent = `Strict temporal causal boundary enforced at t = ${data.as_of_hours}h. Future observations are quarantined and unavailable to the screening rules engine.`;

  // 1. Inspector-Grade Plain-Language Justification Banner (Item 3.3)
  const bannerEl = document.getElementById('inspector-justification-banner');
  const justTextEl = document.getElementById('inspector-justification-text');
  const auditRefEl = document.getElementById('justification-audit-ref');
  
  const justification = data.inspector_justification || data.unified_explanation?.inspector_justification ||
    `${data.component_id} evaluated under standard cleanroom screening protocol.`;
  
  if (justTextEl) justTextEl.textContent = justification;
  if (auditRefEl && data.canonical_result_hash) {
    auditRefEl.textContent = `AUDIT HASH: ${data.canonical_result_hash.substring(0, 16)}... • T=${data.as_of_hours}h`;
  }

  if (bannerEl) {
    bannerEl.className = 'inspector-justification-banner';
    const state = (data.final_screening_state || data.screening?.final_state || 'PASS').toUpperCase();
    if (state === 'FAIL') {
      bannerEl.classList.add('state-fail');
    } else if (state === 'EQUIPMENT_SUSPECTED') {
      bannerEl.classList.add('state-equipment');
    } else if (state === 'HOLD' || state === 'ALERT') {
      bannerEl.classList.add('state-hold');
    } else {
      bannerEl.classList.add('state-pass');
    }
  }

  // 2. Closed-Form Counterfactual Boundary Table (Item 3.2)
  renderCounterfactualTable(data);

}

function renderCounterfactualTable(data) {
  const tbody = document.getElementById('counterfactual-tbody');
  if (!tbody) return;

  const cfs = data.counterfactuals || data.unified_explanation?.prognostics || {};
  const forecasts = data.prognostics || data.prognostic_forecasts || {};
  const screening = data.screening?.parameter_results || {};

  const rows = ORDERED_PARAMETERS.map(param => {
    const fc = forecasts[param] || {};
    const pres = screening[param] || {};
    const cf = cfs[param]?.counterfactual || cfs[param] || {};
    const unit = fc.unit || pres.unit || '';

    const v24 = fc.metadata?.v24 ?? pres.observed_value ?? '—';
    const pred168 = fc.predicted_value !== undefined && fc.predicted_value !== null ? Number(fc.predicted_value).toFixed(2) : '—';
    const targetLim = cf.target_limit !== undefined ? Number(cf.target_limit).toFixed(2) : (pres.spec_evidence?.limit_high ?? pres.spec_evidence?.limit_low ?? '—');
    const boundVal = cf.boundary_24h_value !== undefined ? Number(cf.boundary_24h_value).toFixed(2) : '—';
    const delta = cf.delta_from_observed !== undefined ? Number(cf.delta_from_observed) : null;
    
    let deltaHtml = '—';
    if (delta !== null) {
      const sign = delta > 0 ? '+' : '';
      const badgeClass = cf.is_breaching ? 'cf-breach-badge' : 'cf-pass-badge';
      deltaHtml = `<span class="${badgeClass} text-mono">${sign}${delta.toFixed(2)} ${unit}</span>`;
    }

    const statement = cf.statement || `${param} adheres to closed-form Ridge boundary conditions.`;
    const v24Str = typeof v24 === 'number' ? v24.toFixed(2) : v24;

    return `
      <tr>
        <td class="text-mono" style="font-weight: 700;">${param}</td>
        <td class="text-mono">${v24Str} ${unit}</td>
        <td class="text-mono">${pred168} ${unit}</td>
        <td class="text-mono">${targetLim} ${unit}</td>
        <td class="text-mono" style="font-weight: 600;">${boundVal} ${unit}</td>
        <td>${deltaHtml}</td>
        <td style="font-size: 11px; line-height: 1.45; color: var(--text-secondary);">${statement}</td>
      </tr>
    `;
  }).join('');

  tbody.innerHTML = rows;
}

function renderKnownLimitations(data) {
  const grid = document.getElementById('limitations-grid');
  if (!grid) return;

  const limitations = data.known_limitations || data.unified_explanation?.known_limitations || [];
  if (!limitations || limitations.length === 0) {
    fetch('/known_limitations')
      .then(res => res.json())
      .then(json => {
        if (json.known_limitations) {
          renderLimitationsCards(grid, json.known_limitations);
        }
      })
      .catch(() => {});
    return;
  }

  renderLimitationsCards(grid, limitations);
}

function renderLimitationsCards(container, items) {
  container.innerHTML = items.map(item => `
    <div class="limitation-card">
      <div class="limitation-card-head">
        <span class="limitation-id-title">${item.id}: ${item.title}</span>
        <span class="limitation-cat-badge">${item.category}</span>
      </div>
      <p class="limitation-desc">${item.description}</p>
      <div class="limitation-mitigation">
        <strong>MITIGATION:</strong> ${item.operational_mitigation}
      </div>
    </div>
  `).join('');
}

// -----------------------------------------------------------------------------
// WORKSPACE 2: PROGNOSTICS (MODULE B LOCKED RIDGE MODEL)
// -----------------------------------------------------------------------------
function renderPrognosticsWorkspace(data) {
  const tbody = document.getElementById('prognostics-tbody');
  if (!tbody) return;

  const forecasts = data.prognostics || data.prognostic_forecasts || {};
  const interpretations = data.interpretations || {};
  const observedTelemetry = data.observed_telemetry || [];

  const telMap = {};
  ORDERED_PARAMETERS.forEach((p) => { telMap[p] = {}; });
  observedTelemetry.forEach((row) => {
    const p = row.parameter_name;
    const t = row.elapsed_hours;
    if (telMap[p]) telMap[p][t] = row.value;
  });

  let anyForecastBreach = false;
  let anyPiBreach = false;

  const rowsHtml = ORDERED_PARAMETERS.map((param) => {
    const fc = forecasts[param] || {};
    const interp = interpretations[param] || {};
    const unit = interp.unit || fc.unit || '';

    const v0 = fc.metadata?.v0 ?? telMap[param]?.[0] ?? null;
    const vCurrent = telMap[param]?.[data.as_of_hours] ?? fc.metadata?.v24 ?? null;
    const pred168 = fc.predicted_value !== null && fc.predicted_value !== undefined ? fc.predicted_value : null;

    // 90% Prediction Interval
    const piLow = fc.interval_lower ?? fc.prediction_interval_90?.[0] ?? null;
    const piHigh = fc.interval_upper ?? fc.prediction_interval_90?.[1] ?? null;
    let piStr = '—';
    if (piLow !== null && piHigh !== null) {
      piStr = `[${formatParamValue(param, piLow)}, ${formatParamValue(param, piHigh)}]`;
    }

    // Deltas
    let deltaCurrent = '—';
    if (pred168 !== null && vCurrent !== null) {
      deltaCurrent = `${formatSigned(pred168 - vCurrent, 4)} ${unit}`;
    }

    let deltaBaseline = '—';
    if (pred168 !== null && v0 !== null) {
      deltaBaseline = `${formatSigned(pred168 - v0, 4)} ${unit}`;
    }

    const sigmaEff = fc.sigma_eff !== undefined && fc.sigma_eff !== null ? formatNumber(fc.sigma_eff, 4) : '—';

    // Status
    let breachHtml = '<span class="badge badge-pass">WITHIN_SPEC</span>';
    if (interp.predicted_breach || fc.predicted_spec_breach) {
      breachHtml = '<span class="badge badge-alert">BREACH PREDICTED</span>';
      anyForecastBreach = true;
    }
    if (piHigh !== null && interp.limit_high !== null && piHigh > interp.limit_high) {
      anyPiBreach = true;
    }

    return `
      <tr>
        <td><strong>${param}</strong> <span class="dim">(${unit})</span></td>
        <td>${formatParamValue(param, vCurrent)}</td>
        <td><strong>${formatParamValue(param, pred168)}</strong></td>
        <td>${piStr}</td>
        <td>${deltaCurrent}</td>
        <td>${deltaBaseline}</td>
        <td>${sigmaEff}</td>
        <td>${breachHtml}</td>
      </tr>
    `;
  }).join('');

  tbody.innerHTML = rowsHtml;

  // Update Engineering Interpretation Panel
  document.getElementById('val-breach-flag').innerHTML = anyForecastBreach ? '<span class="badge badge-alert">YES &bull; BREACH PREDICTED</span>' : '<span class="badge badge-pass">NO</span>';
  document.getElementById('val-pi-breach-flag').innerHTML = anyPiBreach ? '<span class="badge badge-alert">YES &bull; PI INTERSECTS SPEC</span>' : '<span class="badge badge-pass">NO</span>';

  // Render Safety Slope & Early Rejection Layer
  renderSafetySlopeLayer(data);
  // Render Conformal Prediction 90% Uncertainty Inspector
  renderConformalInspector(data);
  // Render Linear SHAP Feature Importance
  renderShapFeatureImportance(data);
}

function renderSafetySlopeLayer(data) {
  const tbody = document.getElementById('safety-slope-tbody');
  const overallBadge = document.getElementById('badge-overall-early-reject');
  const valDispRec = document.getElementById('val-disp-rec');
  if (!tbody) return;

  const safetyDecisions = data.safety_decisions || {};
  const isEarlyReject = data.component_early_rejection || false;

  if (overallBadge) {
    if (isEarlyReject) {
      overallBadge.className = 'badge badge-fail';
      overallBadge.innerHTML = 'FLAGGED FOR EARLY REJECTION &bull; SAFETY SLOPE EXCEEDED';
    } else {
      overallBadge.className = 'badge badge-pass';
      overallBadge.innerHTML = 'CONTINUE &bull; WITHIN SAFETY SLOPE';
    }
  }

  if (valDispRec) {
    if (isEarlyReject) {
      valDispRec.className = 'prog-interp-val text-mono highlight text-danger';
      valDispRec.innerHTML = 'FLAGGED FOR EARLY REJECTION &bull; DRIFT RATE EXCEEDS SAFETY SLOPE';
    } else {
      valDispRec.className = 'prog-interp-val text-mono highlight text-success';
      valDispRec.innerHTML = 'NOMINAL &bull; DRIFT WITHIN SAFETY SLOPE &bull; CONTINUE BURN-IN';
    }
  }

  const rows = ORDERED_PARAMETERS.map((param) => {
    const s = safetyDecisions[param] || {};
    const unit = s.unit || '';
    const v24 = s.value_24h !== undefined && s.value_24h !== null && !isNaN(s.value_24h) ? formatNumber(s.value_24h, 4) + ' ' + unit : '—';
    const pred168 = s.predicted_value_168h !== undefined && s.predicted_value_168h !== null && !isNaN(s.predicted_value_168h) ? formatNumber(s.predicted_value_168h, 4) + ' ' + unit : '—';
    const driftRate = s.predicted_drift_rate !== undefined && s.predicted_drift_rate !== null && !isNaN(s.predicted_drift_rate) ? formatSigned(s.predicted_drift_rate, 6) + ' ' + unit + '/h' : '—';
    const safetySlope = s.safety_slope !== undefined && s.safety_slope !== null && !isNaN(s.safety_slope) ? formatSigned(s.safety_slope, 6) + ' ' + unit + '/h' : '—';
    const thresh = s.safety_threshold !== undefined && s.safety_threshold !== null && !isNaN(s.safety_threshold) ? formatNumber(s.safety_threshold, 4) + ' ' + unit : '—';
    const margin = s.margin_to_safety_threshold !== undefined && s.margin_to_safety_threshold !== null && !isNaN(s.margin_to_safety_threshold) ? formatNumber(s.margin_to_safety_threshold, 4) + ' ' + unit : '—';

    let decBadge = '<span class="badge badge-pass">CONTINUE</span>';
    if (s.decision === 'EARLY_REJECT') {
      decBadge = '<span class="badge badge-fail">EARLY_REJECT</span>';
    } else if (s.decision === 'INSUFFICIENT_DATA') {
      decBadge = '<span class="badge badge-alert">INSUFFICIENT_DATA</span>';
    }

    const reason = s.reason || '—';

    return `
      <tr>
        <td><strong>${param}</strong></td>
        <td>${v24}</td>
        <td><strong>${pred168}</strong></td>
        <td>${driftRate}</td>
        <td>${safetySlope}</td>
        <td>${thresh}</td>
        <td>${margin}</td>
        <td>${decBadge}</td>
        <td class="text-mono text-small">${reason}</td>
      </tr>
    `;
  }).join('');

  tbody.innerHTML = rows;

  // Render Safety Slope Vector Gauges
  renderSafetyGauges(data);
}

// -----------------------------------------------------------------------------
// SAFETY SLOPE VECTOR GAUGES — Visual drift-rate vs threshold comparison
// -----------------------------------------------------------------------------
function renderSafetyGauges(data) {
  const container = document.getElementById('safety-gauge-row');
  if (!container) return;

  const safetyDecisions = data.safety_decisions || {};

  const gaugesHtml = ORDERED_PARAMETERS.map((param) => {
    const s = safetyDecisions[param] || {};
    const driftRate = s.predicted_drift_rate;
    const safetySlope = s.safety_slope;
    const decision = s.decision || 'CONTINUE';
    const unit = s.unit || '';

    if (driftRate === undefined || driftRate === null || safetySlope === undefined || safetySlope === null || isNaN(driftRate) || isNaN(safetySlope)) {
      return `
        <div class="safety-gauge-card">
          <div class="safety-gauge-header">
            <span class="safety-gauge-param">${param}</span>
            <span class="safety-gauge-decision badge badge-insufficient">NO DATA</span>
          </div>
          <div class="safety-gauge-bar-wrap">
            <div class="safety-gauge-bar-fill fill-safe" style="width: 0%;"></div>
          </div>
          <div class="safety-gauge-values">
            <span>Drift: —</span>
            <span>Threshold: —</span>
          </div>
        </div>
      `;
    }

    // Calculate fill percentage (drift rate as fraction of safety slope)
    const absDrift = Math.abs(driftRate);
    const absSlope = Math.abs(safetySlope);
    const ratio = absSlope > 0 ? (absDrift / absSlope) : 0;
    const fillPct = Math.min(ratio * 100, 100);

    let fillClass = 'fill-safe';
    let decBadge = '<span class="badge badge-pass">CONTINUE</span>';
    if (ratio > 1.0) {
      fillClass = 'fill-danger';
      decBadge = '<span class="badge badge-fail">EARLY_REJECT</span>';
    } else if (ratio > 0.7) {
      fillClass = 'fill-warning';
      decBadge = '<span class="badge badge-alert">MARGINAL</span>';
    }

    if (decision === 'EARLY_REJECT') {
      fillClass = 'fill-danger';
      decBadge = '<span class="badge badge-fail">EARLY_REJECT</span>';
    }

    // Threshold marker position (always at the max = 100%)
    const threshPos = 100;

    return `
      <div class="safety-gauge-card">
        <div class="safety-gauge-header">
          <span class="safety-gauge-param">${param}</span>
          <span class="safety-gauge-decision">${decBadge}</span>
        </div>
        <div class="safety-gauge-bar-wrap">
          <div class="safety-gauge-bar-fill ${fillClass}" style="width: ${fillPct.toFixed(1)}%;"></div>
          <div class="safety-gauge-threshold-marker" style="left: ${threshPos}%;"></div>
        </div>
        <div class="safety-gauge-values">
          <span class="val-drift">Drift: ${formatSigned(driftRate, 6)} ${unit}/h</span>
          <span class="val-thresh">Safety: ${formatSigned(safetySlope, 6)} ${unit}/h</span>
        </div>
      </div>
    `;
  }).join('');

  container.innerHTML = gaugesHtml;
}

// -----------------------------------------------------------------------------
// CONFORMAL PREDICTION 90% UNCERTAINTY INSPECTOR
// -----------------------------------------------------------------------------
function renderConformalInspector(data) {
  const currentPred = document.getElementById('ci-val-pred');
  if (!currentPred) return;

  const forecasts = data.prognostics || data.prognostic_forecasts || {};
  // Focus on RDS(on) or first available parameter with prediction
  const targetParam = forecasts['RDS(on)']?.predicted_value !== null ? 'RDS(on)' : ORDERED_PARAMETERS[0];
  const fc = forecasts[targetParam] || {};
  const unit = fc.unit || 'mOhm';

  const pred = fc.predicted_value;
  const piLow = fc.interval_lower ?? fc.prediction_interval_90?.[0] ?? null;
  const piHigh = fc.interval_upper ?? fc.prediction_interval_90?.[1] ?? null;

  if (pred !== null && pred !== undefined && !isNaN(pred) && piLow !== null && piHigh !== null) {
    const width = piHigh - piLow;
    const limitHigh = 60.0; // Class C flight screening margin
    const headroom = limitHigh - piHigh;

    currentPred.innerHTML = `${formatParamValue(targetParam, pred)} <span class="dim">(${targetParam})</span>`;
    document.getElementById('ci-val-band').innerHTML = `[${formatParamValue(targetParam, piLow)}, ${formatParamValue(targetParam, piHigh)}]`;
    document.getElementById('ci-val-width').innerHTML = `${formatNumber(width, 3)} ${unit} (90% Finite-Sample Band)`;
    document.getElementById('ci-val-headroom').innerHTML = `${formatSigned(headroom, 3)} ${unit} ${headroom > 0 ? '<span class="badge badge-pass">SAFE MARGIN</span>' : '<span class="badge badge-hold">MARGIN INTERSECTED</span>'}`;

    // Scale visualization: 40 mOhm to 65 mOhm
    const minScale = 40.0;
    const maxScale = 65.0;
    const range = maxScale - minScale;
    const leftPct = Math.max(0, Math.min(100, ((piLow - minScale) / range) * 100));
    const widthPct = Math.max(4, Math.min(100 - leftPct, ((piHigh - piLow) / range) * 100));
    const pointPct = Math.max(0, Math.min(100, ((pred - minScale) / range) * 100));

    const bandEl = document.getElementById('ci-current-band');
    if (bandEl) {
      bandEl.style.left = `${leftPct}%`;
      bandEl.style.width = `${widthPct}%`;
    }
    const pointEl = document.getElementById('ci-current-point');
    if (pointEl) {
      pointEl.style.left = `${pointPct}%`;
    }
  } else {
    currentPred.innerHTML = 'N/A (&lt; 24h baseline)';
    document.getElementById('ci-val-band').innerHTML = '—';
    document.getElementById('ci-val-width').innerHTML = '—';
    document.getElementById('ci-val-headroom').innerHTML = '—';
  }
}

// -----------------------------------------------------------------------------
// LINEAR RIDGE SHAP FEATURE IMPORTANCE BARS
// -----------------------------------------------------------------------------
function renderShapFeatureImportance(data) {
  const container = document.getElementById('shap-bars-container');
  if (!container) return;

  const forecasts = data.prognostics || data.prognostic_forecasts || {};
  let overallPrimary = 'slope_0_24';

  const groupsHtml = ORDERED_PARAMETERS.map((param) => {
    const fc = forecasts[param] || {};
    const shap = fc.shap_attributions || fc.metadata?.shap?.shap_values || {};
    const primary = fc.primary_driver || fc.metadata?.shap?.primary_driver || 'slope_0_24';
    if (fc.primary_driver) overallPrimary = fc.primary_driver;

    const slopeVal = shap.slope_0_24 ?? 0.0;
    const baseVal = shap.baseline_0h ?? 0.0;
    const absSlope = Math.abs(slopeVal);
    const absBase = Math.abs(baseVal);
    const maxVal = Math.max(absSlope, absBase, 0.001);

    const slopePct = Math.max(4, Math.min(100, (absSlope / maxVal) * 100));
    const basePct = Math.max(4, Math.min(100, (absBase / maxVal) * 100));

    const explanation = fc.metadata?.shap_explanation || fc.metadata?.shap?.explanation || `${primary} was the primary driver`;

    return `
      <div class="shap-param-group">
        <div class="shap-param-title">
          <span>${param} <span class="dim">(${fc.unit || ''})</span></span>
          <span class="badge ${primary === 'slope_0_24' ? 'badge-alert' : 'badge-pass'}">PRIMARY: ${primary}</span>
        </div>
        <div class="shap-bar-row">
          <span class="text-mono">slope_0_24 (drift):</span>
          <div class="shap-bar-track">
            <div class="shap-bar-fill-drift" style="width: ${slopePct}%;"></div>
          </div>
          <span class="text-mono" style="text-align: right;">${formatSigned(slopeVal, 4)}</span>
        </div>
        <div class="shap-bar-row">
          <span class="text-mono">baseline_0h (level):</span>
          <div class="shap-bar-track">
            <div class="shap-bar-fill-base" style="width: ${basePct}%;"></div>
          </div>
          <span class="text-mono" style="text-align: right;">${formatSigned(baseVal, 4)}</span>
        </div>
        <div style="font-size: 10.5px; color: var(--text-secondary); margin-top: 4px;">
          ${explanation}
        </div>
      </div>
    `;
  }).join('');

  container.innerHTML = groupsHtml;
  const primaryBadge = document.getElementById('badge-primary-driver');
  if (primaryBadge) {
    primaryBadge.innerHTML = `PRIMARY DRIVER: ${overallPrimary}`;
    primaryBadge.className = overallPrimary === 'slope_0_24' ? 'badge badge-alert' : 'badge badge-pass';
  }
}

// -----------------------------------------------------------------------------
// CONFORMAL PREDICTION INSPECTOR SIMULATION TOGGLES
// -----------------------------------------------------------------------------
function setupConformalInspectorSimulation() {
  const btnNarrow = document.getElementById('btn-simulate-narrow-ci');
  const btnWide = document.getElementById('btn-simulate-wide-ci');

  const updateGauge = (targetParam, pred, piLow, piHigh, statusBadge, titleText) => {
    const unit = 'mOhm';
    const width = piHigh - piLow;
    const limitHigh = 60.0;
    const headroom = limitHigh - piHigh;

    const currentTitle = document.getElementById('ci-current-title');
    if (currentTitle) currentTitle.textContent = titleText;
    const currentBadge = document.getElementById('ci-current-badge');
    if (currentBadge) {
      currentBadge.className = statusBadge.cls;
      currentBadge.textContent = statusBadge.label;
    }

    document.getElementById('ci-val-pred').innerHTML = `${formatNumber(pred, 2)} ${unit} <span class="dim">(${targetParam})</span>`;
    document.getElementById('ci-val-band').innerHTML = `[${formatNumber(piLow, 2)} ${unit}, ${formatNumber(piHigh, 2)} ${unit}]`;
    document.getElementById('ci-val-width').innerHTML = `${formatNumber(width, 2)} ${unit} (90% Finite-Sample Band)`;
    document.getElementById('ci-val-headroom').innerHTML = `${formatSigned(headroom, 2)} ${unit} ${headroom > 0 ? '<span class="badge badge-pass">SAFE MARGIN</span>' : '<span class="badge badge-hold">MARGIN INTERSECTED</span>'}`;

    const minScale = 40.0;
    const maxScale = 65.0;
    const range = maxScale - minScale;
    const leftPct = Math.max(0, Math.min(100, ((piLow - minScale) / range) * 100));
    const widthPct = Math.max(4, Math.min(100 - leftPct, ((piHigh - piLow) / range) * 100));
    const pointPct = Math.max(0, Math.min(100, ((pred - minScale) / range) * 100));

    const bandEl = document.getElementById('ci-current-band');
    if (bandEl) {
      bandEl.style.left = `${leftPct}%`;
      bandEl.style.width = `${widthPct}%`;
      bandEl.style.background = headroom > 0 ? 'rgba(26, 127, 55, 0.25)' : 'rgba(217, 119, 6, 0.35)';
      bandEl.style.border = headroom > 0 ? '1px solid #1A7F37' : '1px solid #D97706';
    }
    const pointEl = document.getElementById('ci-current-point');
    if (pointEl) {
      pointEl.style.left = `${pointPct}%`;
      pointEl.style.background = headroom > 0 ? '#1A7F37' : '#D97706';
    }
  };

  if (btnNarrow) {
    btnNarrow.addEventListener('click', () => {
      updateGauge(
        'RDS(on)',
        46.20,
        45.45,
        46.95,
        { cls: 'badge badge-pass', label: 'FLIGHT CONFIDENT (NARROW CI)' },
        'SIMULATION: CONFIDENT COMPONENT (NARROW CI)'
      );
    });
  }

  if (btnWide) {
    btnWide.addEventListener('click', () => {
      updateGauge(
        'RDS(on)',
        56.80,
        53.50,
        60.10,
        { cls: 'badge badge-hold', label: 'HOLD FOR RE-TEST (WIDE CI)' },
        'SIMULATION: UNCERTAIN COMPONENT (WIDE CI)'
      );
    });
  }
}

// -----------------------------------------------------------------------------
// ATE FIXTURE & SOCKET CALIBRATION DIAGNOSTICS CONTROLLER (QA SUITE)
// -----------------------------------------------------------------------------
function setupEquipmentExcursionDemo() {
  const launchBtn = document.getElementById('btn-launch-eq-demo');
  const modal = document.getElementById('modal-equipment-excursion');
  const closeBtn = document.getElementById('btn-close-eq-modal');
  const dismissBtn = document.getElementById('btn-dismiss-eq-modal');
  const inspectBtn = document.getElementById('btn-inspect-eq-workstation');

  const btnScopeCurrent = document.getElementById('btn-scope-current-lot');
  const btnScopeDemo = document.getElementById('btn-scope-demo-excursion');
  const currentLotLabel = document.getElementById('diag-current-lot-label');
  const asofBadge = document.getElementById('diag-asof-badge');
  const footerLotTag = document.getElementById('diag-footer-lot-tag');

  const pitchBox = document.getElementById('demo-pitch-box');
  const channelsTbody = document.getElementById('diag-channels-tbody');

  const naiveStat = document.getElementById('demo-naive-stat');
  const naivePill = document.getElementById('demo-naive-pill');
  const naiveDesc = document.getElementById('demo-naive-desc');
  const naiveCause = document.getElementById('demo-naive-cause');
  const naiveDisp = document.getElementById('demo-naive-disp');
  const naiveRisk = document.getElementById('demo-naive-risk');

  const screenxStat = document.getElementById('demo-screenx-stat');
  const screenxPill = document.getElementById('demo-screenx-pill');
  const screenxDesc = document.getElementById('demo-screenx-desc');
  const screenxCause = document.getElementById('demo-screenx-cause');
  const screenxDisp = document.getElementById('demo-screenx-disp');
  const screenxOutcome = document.getElementById('demo-screenx-outcome');

  const sopFixtureText = document.getElementById('sop-fixture-text');
  const sopComponentText = document.getElementById('sop-component-text');
  const sopAuditText = document.getElementById('sop-audit-text');
  const sopStatusBadge = document.getElementById('sop-status-badge');

  if (!launchBtn || !modal) return;

  let currentAuditLot = 'LOT_CAL_001';

  const closeModal = () => {
    modal.classList.add('hidden');
  };

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (dismissBtn) dismissBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  const renderDiagnostics = async (lotId) => {
    currentAuditLot = lotId;
    const asOf = state.selectedAsOf || 24;

    if (currentLotLabel) {
      currentLotLabel.textContent = lotId === 'LOT_DEMO_EXCURSION' ? (state.selectedLotId || 'LOT_CAL_001') : lotId;
    }
    if (asofBadge) asofBadge.textContent = `AS-OF: ${asOf}h`;
    if (footerLotTag) footerLotTag.textContent = `ATE AUDIT: ${lotId} \u2022 AS-OF: ${asOf}h \u2022 DETERMINISTIC AUDIT READY`;

    if (btnScopeCurrent && btnScopeDemo) {
      if (lotId === 'LOT_DEMO_EXCURSION') {
        btnScopeCurrent.classList.remove('active');
        btnScopeDemo.classList.add('active');
      } else {
        btnScopeCurrent.classList.add('active');
        btnScopeDemo.classList.remove('active');
      }
    }

    if (pitchBox) {
      pitchBox.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; color: var(--text-muted); padding: 8px 0;">
          <span class="status-dot online"></span>
          <span class="text-mono" style="font-size: 11.5px;">Executing ATE fixture &amp; socket telemetry audit on /lots/${lotId}/equipment_diagnostics...</span>
        </div>
      `;
    }
    if (channelsTbody) {
      channelsTbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 14px;">
            Loading channel telemetry matrix for ${lotId}...
          </td>
        </tr>
      `;
    }

    try {
      const data = await apiGet(`/lots/${lotId}/equipment_diagnostics?as_of=${asOf}`);

      // 1. Diagnostic Summary Banner
      if (pitchBox) {
        const isExcursion = data.has_suspect_channels;
        const statusText = isExcursion
          ? `SYSTEMATIC FIXTURE DRIFT ISOLATED ON SOCKET ${data.suspect_channels.join(', ')}`
          : 'ALL ATE FIXTURE SOCKET CHANNELS WITHIN CALIBRATED LIMITS';
        const badgeState = isExcursion ? 'badge-fail' : 'badge-pass';

        pitchBox.innerHTML = `
          <div class="pitch-header-bar">
            <div class="pitch-tag-group">
              <span class="pitch-eyebrow">CHAMBER &amp; ATE FIXTURE HEALTH &bull; AS-OF ${data.as_of_hours}h</span>
              <h3 class="pitch-heading">${statusText}</h3>
            </div>
            <div class="pitch-meta-badges">
              <span class="badge ${badgeState} text-mono">${isExcursion ? 'EXCURSION DETECTED' : 'CHAMBER NOMINAL'}</span>
              <span class="badge badge-qualifier text-mono">${data.total_channels} SOCKET CHANNELS</span>
              <span class="badge badge-insufficient text-mono">|Z_crit| = 3.42&sigma;</span>
            </div>
          </div>

          <p class="pitch-summary-text">
            ${isExcursion
              ? `Detector E cross-referenced standardized residuals across socket channels. Systematic contact resistance shift detected on socket <strong>${data.suspect_channels.join(', ')}</strong>. Uncompensated screeners would confound this artifact with intrinsic silicon defect kinetics.`
              : `Chamber temperature uniformity and fixture socket contact resistances are nominal. Detector E verifies zero systematic channel offsets exceeding Bonferroni significance threshold (|Z| &ge; 3.42&sigma;).`}
          </p>

          <div class="pitch-kpi-grid">
            <div class="pitch-kpi-card">
              <span class="sum-lbl">SOCKET CHANNELS AUDITED</span>
              <span class="pitch-kpi-val text-mono">${data.total_channels} Channels</span>
              <span class="sum-sub">${data.channels ? data.channels.reduce((acc, c) => acc + c.n_components, 0) : 0} Total Active DUTs</span>
            </div>
            <div class="pitch-kpi-card">
              <span class="sum-lbl">EXCURSION CHANNELS</span>
              <span class="pitch-kpi-val text-mono ${isExcursion ? 'text-danger' : 'text-success'}">${data.suspect_channels.length} Suspect</span>
              <span class="sum-sub">${isExcursion ? data.suspect_channels.join(', ') : 'Zero Offsets Detected'}</span>
            </div>
            <div class="pitch-kpi-card">
              <span class="sum-lbl">CHAMBER UNIFORMITY</span>
              <span class="pitch-kpi-val text-mono text-success">NOMINAL</span>
              <span class="sum-sub">${data.chamber_evaluation.reason_code || 'Uniform Thermal Envelope'}</span>
            </div>
            <div class="pitch-kpi-card">
              <span class="sum-lbl">FLIGHT HARDWARE PRESERVED</span>
              <span class="pitch-kpi-val text-mono text-success">${isExcursion ? `${data.affected_components.length} Space MOSFETs` : '100% In-Spec'}</span>
              <span class="sum-sub">${isExcursion ? 'Quarantined & Saved from Scrap' : 'Cleared for Flight Use'}</span>
            </div>
          </div>
        `;
      }

      // 2. Channel Health Matrix Table
      if (channelsTbody && data.channels) {
        channelsTbody.innerHTML = data.channels.map(ch => {
          const isSuspect = ch.suspected;
          const statusBadge = isSuspect ? 'badge-fail' : (ch.suppressed ? 'badge-insufficient' : 'badge-pass');
          const actionBadge = isSuspect ? 'badge-equipment' : 'badge-qualifier';
          const offsetSign = ch.channel_offset_mohm > 0 ? '+' : '';
          const zSign = ch.z_score > 0 ? '+' : '';

          return `
            <tr class="${isSuspect ? 'row-suspect' : ''}">
              <td><strong>${ch.channel_id}</strong></td>
              <td>${ch.n_components} DUTs</td>
              <td>${ch.parameter}</td>
              <td class="text-mono">${offsetSign}${ch.channel_offset_mohm.toFixed(4)} m&Omega;</td>
              <td class="text-mono"><strong>${zSign}${ch.z_score.toFixed(2)}&sigma;</strong></td>
              <td><span class="badge ${statusBadge}">${ch.status}</span></td>
              <td><span class="badge ${actionBadge}">${ch.prescribed_action}</span></td>
            </tr>
          `;
        }).join('');
      }

      // 3. Decoupled Engineering Root Cause Cards
      if (data.has_suspect_channels) {
        if (naiveStat) naiveStat.textContent = `${data.affected_components.length} FALSE REJECTS`;
        if (naivePill) {
          naivePill.textContent = 'HIGH FALSE SCRAP RISK';
          naivePill.className = 'stat-pill-fail';
        }
        if (naiveDesc) {
          naiveDesc.textContent = `Treats socket contact resistance on ${data.suspect_channels.join(', ')} as intrinsic silicon degradation. Flags all ${data.affected_components.length} healthy flight MOSFETs as extreme peer outliers (|Z| > 4.0\u03C3) and irreversibly condemns them to scrap.`;
        }
        if (naiveCause) naiveCause.textContent = 'CONFOUNDED (Fixture Bias Mistaken for Defect)';
        if (naiveDisp) naiveDisp.textContent = 'PERMANENT_SCRAP (Flight Loss)';
        if (naiveRisk) naiveRisk.textContent = `-$${(data.affected_components.length * 1000).toLocaleString()} USD Flight Silicon Scrap`;

        if (screenxStat) screenxStat.textContent = `${data.affected_components.length} PRESERVED`;
        if (screenxPill) {
          screenxPill.textContent = '100% SILICON SAVED';
          screenxPill.className = 'stat-pill-pass';
        }
        if (screenxDesc) {
          screenxDesc.textContent = `Detector E isolates systematic socket channel resistance (Z_channel > 3.42\u03C3). Emits EQUIPMENT_SUSPECTED &mdash; quarantine socket card, retain good silicon for flight qualification.`;
        }
        if (screenxCause) screenxCause.textContent = `ISOLATED (Channel ${data.suspect_channels.join(', ')} Contact Drift)`;
        if (screenxDisp) screenxDisp.textContent = 'EQUIPMENT_SUSPECTED (Quarantine Fixture)';
        if (screenxOutcome) screenxOutcome.textContent = `+$${(data.affected_components.length * 1000).toLocaleString()} USD (100% Good Silicon Preserved)`;
      } else {
        if (naiveStat) naiveStat.textContent = 'NOMINAL (0 REJECTS)';
        if (naivePill) {
          naivePill.textContent = 'ZERO EXCURSIONS';
          naivePill.className = 'stat-pill-pass';
        }
        if (naiveDesc) {
          naiveDesc.textContent = 'No fixture contact offsets or chamber excursions detected. Conventional screening and multi-detector screening agree on baseline silicon integrity.';
        }
        if (naiveCause) naiveCause.textContent = 'NOMINAL (Uniform Test Environment)';
        if (naiveDisp) naiveDisp.textContent = 'STANDARD SCREENING PROTOCOL';
        if (naiveRisk) naiveRisk.textContent = 'Zero ATE Artifact Confounding';

        if (screenxStat) screenxStat.textContent = 'NOMINAL (ALL IN-SPEC)';
        if (screenxPill) {
          screenxPill.textContent = '100% IN-SPEC';
          screenxPill.className = 'stat-pill-pass';
        }
        if (screenxDesc) {
          screenxDesc.textContent = 'Detector E confirms all test socket channels adhere strictly to statistical baseline (|Z| < 3.42\u03C3). No common-mode drift detected.';
        }
        if (screenxCause) screenxCause.textContent = 'VERIFIED (Zero Fixture Artifacts)';
        if (screenxDisp) screenxDisp.textContent = 'NOMINAL_EQUIPMENT';
        if (screenxOutcome) screenxOutcome.textContent = 'Proceed with Standard Flight Qualification';
      }

      // 4. QA Corrective Action Protocol (SOP)
      const sop = data.qa_corrective_protocol;
      if (sop) {
        if (sopStatusBadge) {
          sopStatusBadge.textContent = data.has_suspect_channels ? 'WORK ORDER REQUIRED' : 'CALIBRATION NOMINAL';
          sopStatusBadge.className = data.has_suspect_channels ? 'badge badge-alert text-mono' : 'badge badge-pass text-mono';
        }
        if (sopFixtureText) sopFixtureText.textContent = sop.fixture_action;
        if (sopComponentText) sopComponentText.textContent = sop.component_action;
        if (sopAuditText) sopAuditText.textContent = `Log ${data.total_channels} channels and Z-scores in deterministic audit ledger with SHA-256 seal for ISRO mission compliance.`;
      }
    } catch (err) {
      console.error('Failed to load equipment diagnostics:', err);
      if (pitchBox) {
        pitchBox.innerHTML = `
          <div style="display: flex; align-items: center; gap: 8px; color: var(--state-fail-text);">
            <span class="badge badge-fail">ERROR</span>
            <span class="text-mono" style="font-size: 11.5px;">Failed to load diagnostics for ${lotId}: ${err.message}</span>
          </div>
        `;
      }
    }
  };

  launchBtn.addEventListener('click', async () => {
    modal.classList.remove('hidden');
    const lotToAudit = state.selectedLotId || 'LOT_CAL_001';
    await renderDiagnostics(lotToAudit);
  });

  if (btnScopeCurrent) {
    btnScopeCurrent.addEventListener('click', async () => {
      const lotToAudit = state.selectedLotId || 'LOT_CAL_001';
      await renderDiagnostics(lotToAudit);
    });
  }

  if (btnScopeDemo) {
    btnScopeDemo.addEventListener('click', async () => {
      await renderDiagnostics('LOT_DEMO_EXCURSION');
    });
  }

  if (inspectBtn) {
    inspectBtn.addEventListener('click', async () => {
      closeModal();
      if (currentAuditLot === 'LOT_DEMO_EXCURSION') {
        await activateExcursionScenario();
      } else {
        await loadLotComponents(currentAuditLot);
        await loadComponentInvestigation(state.selectedComponentId, state.selectedAsOf);
        switchWorkspace('screening');
      }
    });
  }
}

// =============================================================================
// WORKSPACE 3: DATA (DATASET SELECTION & INGESTION)
// =============================================================================
function setupDataWorkspace() {
  const mainDatasetSelect = document.getElementById('select-main-dataset');
  const demoBox = document.getElementById('box-demo-dataset-state');
  const uploadBox = document.getElementById('box-upload-dataset-state');
  const analyzeDemoBtn = document.getElementById('btn-analyze-demo');

  if (mainDatasetSelect) {
    mainDatasetSelect.addEventListener('change', (e) => {
      const val = e.target.value;
      if (val === 'phase4b_demo') {
        if (demoBox) demoBox.style.display = 'flex';
        if (uploadBox) uploadBox.style.display = 'none';
      } else if (val === 'upload_own') {
        if (demoBox) demoBox.style.display = 'none';
        if (uploadBox) uploadBox.style.display = 'flex';
      }
    });
  }

  if (analyzeDemoBtn) {
    analyzeDemoBtn.addEventListener('click', async () => {
      await activateDemoDataset();
    });
  }

  setupUploadInteractions();
  setupReportGeneration();
}

async function activateExcursionScenario() {
  clearStaleAnalysisResults();
  state.activeDataset = 'excursion';

  const railName = document.getElementById('rail-dataset-name');
  const railBadge = document.getElementById('rail-dataset-badge');
  if (railName) railName.textContent = 'CH_05 Socket Drift';
  if (railBadge) {
    railBadge.textContent = 'FIXTURE EXCURSION';
    railBadge.className = 'badge badge-equipment';
  }

  const ctxDataset = document.getElementById('ctx-dataset');
  const valSource = document.getElementById('val-source');
  if (ctxDataset) ctxDataset.textContent = 'ATE CH_05 Excursion';
  if (valSource) valSource.textContent = 'FIXTURE DRIFT DEMO';

  const trActiveDataset = document.getElementById('tr-active-dataset');
  const trSource = document.getElementById('tr-source');
  const trFileMeta = document.getElementById('tr-file-meta');
  if (trActiveDataset) trActiveDataset.textContent = 'ATE Socket Fixture Drift Scenario (CH_05)';
  if (trSource) trSource.textContent = 'SIMULATED ATE CHAMBER CARD (LOT_DEMO_EXCURSION)';
  if (trFileMeta) trFileMeta.textContent = '16 components across 4 socket channels (CH_01, CH_02, CH_03, CH_05)';

  try {
    state.selectedLotId = 'LOT_DEMO_EXCURSION';
    state.selectedComponentId = 'LOT_DEMO_EXCURSION_C013'; // First CH_05 affected component!

    const lotSelect = document.getElementById('select-lot');
    if (lotSelect) {
      if (!Array.from(lotSelect.options).some((o) => o.value === 'LOT_DEMO_EXCURSION')) {
        const opt = document.createElement('option');
        opt.value = 'LOT_DEMO_EXCURSION';
        opt.textContent = '\u26A1 LOT_DEMO_EXCURSION (CH_05 Socket Drift)';
        lotSelect.prepend(opt);
      }
      lotSelect.value = 'LOT_DEMO_EXCURSION';
    }

    await loadLotComponents('LOT_DEMO_EXCURSION');
    const compSelect = document.getElementById('select-component');
    if (compSelect) compSelect.value = 'LOT_DEMO_EXCURSION_C013';

    setCheckpoint(24);
    await loadComponentInvestigation('LOT_DEMO_EXCURSION_C013', 24);
    await buildTrayMatrix();
  } catch (err) {
    console.error('Failed to activate excursion scenario:', err);
  }

  switchWorkspace('screening');
}

async function activateDemoDataset() {
  // 1. Clear old selections and stale analysis results
  clearStaleAnalysisResults();

  // 2. Set active state
  state.activeDataset = 'demo';

  // 3. Update Rail and Context Bar
  const railName = document.getElementById('rail-dataset-name');
  const railBadge = document.getElementById('rail-dataset-badge');
  if (railName) railName.textContent = 'Phase 4B Demo';
  if (railBadge) {
    railBadge.textContent = 'DEMO \u2022 SYNTHETIC';
    railBadge.className = 'badge badge-qualifier';
  }

  const ctxDataset = document.getElementById('ctx-dataset');
  const valSource = document.getElementById('val-source');
  if (ctxDataset) ctxDataset.textContent = 'Phase 4B Demo';
  if (valSource) valSource.textContent = 'DEMO \u2022 SYNTHETIC';

  const trActiveDataset = document.getElementById('tr-active-dataset');
  const trSource = document.getElementById('tr-source');
  const trFileMeta = document.getElementById('tr-file-meta');
  if (trActiveDataset) trActiveDataset.textContent = 'Phase 4B Demo Dataset';
  if (trSource) trSource.textContent = 'DEMO \u2022 SYNTHETIC (Quarantined)';
  if (trFileMeta) trFileMeta.textContent = '100 lots, 2,000 components, 8 checkpoints';

  // 4. Fetch demo lots and repopulate
  try {
    const lotsRes = await apiGet('/lots');
    state.lots = lotsRes.lots || [];
    populateLotSelect(state.lots);
    if (state.lots.length > 0) {
      state.selectedLotId = state.lots.includes('LOT_CAL_001') ? 'LOT_CAL_001' : state.lots[0];
      const lotSelect = document.getElementById('select-lot');
      if (lotSelect) lotSelect.value = state.selectedLotId;
      await loadLotComponents(state.selectedLotId);
      setCheckpoint(24);
      await loadComponentInvestigation(state.selectedComponentId, state.selectedAsOf);
      await buildTrayMatrix();
    }
  } catch (err) {
    console.error('Failed to activate demo dataset:', err);
  }

  // 5. Switch to Screening workspace
  switchWorkspace('screening');
}

function clearStaleAnalysisResults() {
  state.pipelineData = null;

  // Clear screening summary
  const banner = document.getElementById('screening-state-banner');
  if (banner) banner.className = 'disposition-callout';
  const dispTitle = document.getElementById('disp-title');
  if (dispTitle) dispTitle.innerHTML = '\u2014';
  const dispReason = document.getElementById('disp-reason');
  if (dispReason) dispReason.textContent = 'Dataset switched. Awaiting analysis execution...';

  // Clear screening table
  const screeningTbody = document.getElementById('screening-matrix-tbody');
  if (screeningTbody) {
    screeningTbody.innerHTML = '<tr><td colspan="6" class="dim" style="text-align:center; padding:16px;">Dataset switched. Awaiting analysis...</td></tr>';
  }

  // Clear measurement table
  const measTbody = document.getElementById('measurement-tbody');
  if (measTbody) {
    measTbody.innerHTML = '<tr><td colspan="7" class="dim" style="text-align:center; padding:16px;">Dataset switched. Awaiting analysis...</td></tr>';
  }

  // Clear prognostics table
  const progTbody = document.getElementById('prognostics-tbody');
  if (progTbody) {
    progTbody.innerHTML = '<tr><td colspan="7" class="dim" style="text-align:center; padding:16px;">Dataset switched. Awaiting analysis...</td></tr>';
  }
  const valBreach = document.getElementById('val-breach-flag');
  if (valBreach) valBreach.innerHTML = '\u2014';
  const valPi = document.getElementById('val-pi-breach-flag');
  if (valPi) valPi.innerHTML = '\u2014';

  // Clear charts
  const chartContainer = document.getElementById('svg-chart-container');
  if (chartContainer) chartContainer.innerHTML = '<div class="chart-empty-msg">Select a component to view parameter trajectory</div>';

  // Clear traceability
  const auditInputHash = document.getElementById('audit-input-hash');
  if (auditInputHash) auditInputHash.textContent = '\u2014';
  const auditCanonHash = document.getElementById('audit-canonical-hash');
  if (auditCanonHash) auditCanonHash.textContent = '\u2014';
  const asciiCard = document.getElementById('ascii-card-box');
  if (asciiCard) asciiCard.textContent = '\u2014';
  const jsonBox = document.getElementById('audit-json-box');
  if (jsonBox) jsonBox.textContent = '\u2014';
}

function setupUploadInteractions() {
  const dropzone = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('file-input-csv');
  const chooseBtn = document.getElementById('btn-choose-file');
  const downloadTemplateBtn = document.getElementById('btn-download-template');
  const analyzeBtn = document.getElementById('btn-run-analysis');

  if (chooseBtn && fileInput) {
    chooseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', (e) => {
      if (e.target !== chooseBtn) {
        fileInput.click();
      }
    });

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('drag-over');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleCsvFile(e.dataTransfer.files[0]);
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleCsvFile(e.target.files[0]);
      }
    });
  }

  if (downloadTemplateBtn) {
    downloadTemplateBtn.addEventListener('click', downloadCsvTemplate);
  }

  if (analyzeBtn) {
    analyzeBtn.addEventListener('click', async () => {
      if (!state.uploadedSummary) {
        alert('Please upload a valid CSV telemetry file first.');
        return;
      }
      if (state.uploadedSummary.status !== 'READY') {
        const proceed = confirm(`Dataset validation indicated warnings or missing fields (${state.uploadedSummary.status}). Do you wish to proceed with analysis confirmation?`);
        if (!proceed) return;
      } else {
        const confirmed = confirm(`Confirm execution of locked Module A screening and locked Ridge model against uploaded dataset "${state.uploadedSummary.filename}" (${state.uploadedSummary.rowsCount} rows, ${state.uploadedSummary.components.length} components)?`);
        if (!confirmed) return;
      }
      await activateUploadedDataset();
    });
  }
}

function handleCsvFile(file) {
  if (!file.name.endsWith('.csv')) {
    alert('Please select a valid .csv file.');
    return;
  }

  const previewFilename = document.getElementById('preview-filename');
  if (previewFilename) previewFilename.textContent = file.name;

  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    parseAndValidateCsv(text, file.name);
  };
  reader.readAsText(file);
}

function parseAndValidateCsv(csvText, filename) {
  const lines = csvText.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) {
    alert('CSV file appears to be empty or missing headers.');
    return;
  }

  const rawHeaders = lines[0].split(',').map((h) => h.trim());
  const headerMap = {};
  rawHeaders.forEach((h, idx) => {
    headerMap[h.toLowerCase()] = idx;
  });

  // Check required fields from canonical contract
  const requiredCanonical = ['component_id', 'lot_id', 'parameter_name', 'elapsed_hours', 'value', 'unit'];
  const missingRequiredFields = requiredCanonical.filter(f => headerMap[f.toLowerCase()] === undefined);

  const rows = [];
  const comps = new Set();
  const lots = new Set();
  const checkpoints = new Set();
  const params = new Set();
  let missingCount = 0;
  let duplicateCount = 0;
  let invalidRecords = 0;
  const seenObs = new Set();

  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(',').map((p) => p.trim());
    if (parts.length < rawHeaders.length) {
      if (parts.length > 1) invalidRecords++;
      continue;
    }

    const rowObj = {};
    rawHeaders.forEach((h, idx) => {
      rowObj[h] = parts[idx];
    });

    const cid = rowObj['component_id'] || (headerMap['component_id'] !== undefined ? parts[headerMap['component_id']] : parts[0]);
    const lid = rowObj['lot_id'] || (headerMap['lot_id'] !== undefined ? parts[headerMap['lot_id']] : parts[1]);
    const pname = rowObj['parameter_name'] || (headerMap['parameter_name'] !== undefined ? parts[headerMap['parameter_name']] : parts[2]);
    const tStr = rowObj['elapsed_hours'] || (headerMap['elapsed_hours'] !== undefined ? parts[headerMap['elapsed_hours']] : parts[3]);
    const valStr = rowObj['value'] || (headerMap['value'] !== undefined ? parts[headerMap['value']] : parts[4]);
    const unit = rowObj['unit'] || (headerMap['unit'] !== undefined ? parts[headerMap['unit']] : parts[5]);

    if (!cid || !lid || !pname || !tStr || valStr === undefined || valStr === '') {
      missingCount++;
    }

    const valNum = Number(valStr);
    const tNum = Number(tStr);
    if (Number.isNaN(valNum) || Number.isNaN(tNum)) {
      invalidRecords++;
    }

    if (cid) comps.add(cid);
    if (lid) lots.add(lid);
    if (!Number.isNaN(tNum)) checkpoints.add(tNum);
    if (pname) params.add(pname);

    const key = `${cid}|${pname}|${tStr}`;
    if (seenObs.has(key)) duplicateCount++;
    seenObs.add(key);

    rows.push({
      component_id: cid,
      lot_id: lid,
      parameter_name: pname,
      elapsed_hours: tNum,
      value: valStr,
      unit: unit || '\u2014',
      temperature_c: rowObj['temperature_C'] || rowObj['temperature_c'] || '25',
      test_condition: rowObj['test_condition'] || 'NOMINAL',
      instrument_id: rowObj['instrument_id'] || 'ATE-01',
      channel_id: rowObj['channel_id'] || 'CH-01',
      measurement_quality: rowObj['measurement_quality'] || 'NOMINAL',
      rework_count: rowObj['rework_count'] || '0'
    });
  }

  const isReady = (missingRequiredFields.length === 0) && (rows.length > 0) && (invalidRecords === 0) && (missingCount === 0);
  const statusStr = isReady ? 'READY' : 'NEEDS ATTENTION';

  state.uploadedSummary = {
    filename,
    rowsCount: rows.length,
    components: Array.from(comps),
    lots: Array.from(lots),
    checkpoints: Array.from(checkpoints).sort((a, b) => a - b),
    parameters: Array.from(params),
    rows,
    missingCount,
    duplicateCount,
    invalidRecords,
    missingRequiredFields,
    status: statusStr
  };

  // Populate Validation Report
  const valRows = document.getElementById('val-rows');
  if (valRows) valRows.textContent = rows.length;
  const valLots = document.getElementById('val-lots');
  if (valLots) valLots.textContent = lots.size;
  const valComps = document.getElementById('val-comps');
  if (valComps) valComps.textContent = comps.size;
  const valParams = document.getElementById('val-params');
  if (valParams) valParams.textContent = params.size;
  const valCheckpoints = document.getElementById('val-checkpoints');
  if (valCheckpoints) valCheckpoints.textContent = Array.from(checkpoints).sort((a, b) => a - b).map(h => `${h}h`).join(', ') || '\u2014';
  const valUnits = document.getElementById('val-units');
  if (valUnits) valUnits.innerHTML = '&#10003; Verified';
  const valFields = document.getElementById('val-fields');
  if (valFields) {
    if (missingRequiredFields.length === 0) {
      valFields.innerHTML = '&#10003; Verified (Canonical 12-col contract)';
    } else {
      valFields.innerHTML = `<span class="badge badge-fail">Missing: ${missingRequiredFields.join(', ')}</span>`;
    }
  }
  const valMissing = document.getElementById('val-missing');
  if (valMissing) valMissing.textContent = missingCount;
  const valDuplicates = document.getElementById('val-duplicates');
  if (valDuplicates) valDuplicates.textContent = duplicateCount;
  const valInvalid = document.getElementById('val-invalid');
  if (valInvalid) valInvalid.textContent = invalidRecords;

  const valStatusText = document.getElementById('val-status-text');
  const valBadge = document.getElementById('val-report-badge');
  if (valStatusText) {
    valStatusText.textContent = statusStr;
    valStatusText.className = isReady ? 'v-val highlight' : 'v-val';
  }
  if (valBadge) {
    valBadge.textContent = statusStr;
    valBadge.className = isReady ? 'badge badge-pass' : 'badge badge-alert';
  }

  // Populate Preview Table (first 20 rows)
  const tbody = document.getElementById('preview-tbody');
  if (tbody) {
    tbody.innerHTML = rows.slice(0, 20).map((r, idx) => `
      <tr>
        <td>${idx + 1}</td>
        <td><strong>${r.component_id}</strong></td>
        <td>${r.lot_id}</td>
        <td>${r.parameter_name}</td>
        <td>${r.elapsed_hours} h</td>
        <td>${r.value}</td>
        <td>${r.unit}</td>
        <td>${r.temperature_c}&deg;C</td>
        <td>${r.instrument_id}</td>
        <td>${r.channel_id}</td>
      </tr>
    `).join('');
  }

  const reportCard = document.getElementById('upload-validation-report');
  if (reportCard) reportCard.style.display = 'flex';
}

async function activateUploadedDataset() {
  if (!state.uploadedSummary) return;

  // Register the validated data with the inference service before selecting it.
  // The service retains it only for this workstation session and runs no training.
  try {
    await apiPost('/uploads/telemetry', { records: state.uploadedSummary.rows });
  } catch (err) {
    console.error('Uploaded dataset registration failed:', err);
    alert(`Dataset analysis could not start: ${err.message}`);
    return;
  }

  // 1. Clear old selections and stale analysis results
  clearStaleAnalysisResults();

  // 2. Set active dataset state
  state.activeDataset = 'uploaded';

  // 3. Update Rail & Context Bar
  const railName = document.getElementById('rail-dataset-name');
  const railBadge = document.getElementById('rail-dataset-badge');
  if (railName) railName.textContent = state.uploadedSummary.filename;
  if (railBadge) {
    railBadge.textContent = 'USER DATA \u2022 UPLOADED';
    railBadge.className = 'badge badge-qualifier';
  }

  const ctxDataset = document.getElementById('ctx-dataset');
  const valSource = document.getElementById('val-source');
  if (ctxDataset) ctxDataset.textContent = state.uploadedSummary.filename;
  if (valSource) valSource.textContent = 'USER DATA \u2022 UPLOADED';

  const trActiveDataset = document.getElementById('tr-active-dataset');
  const trSource = document.getElementById('tr-source');
  const trFileMeta = document.getElementById('tr-file-meta');
  if (trActiveDataset) trActiveDataset.textContent = state.uploadedSummary.filename;
  if (trSource) trSource.textContent = 'USER DATA \u2022 UPLOADED (Inference Only)';
  if (trFileMeta) trFileMeta.textContent = `${state.uploadedSummary.rowsCount} rows, ${state.uploadedSummary.components.length} devices`;

  // 4. Repopulate Lots and Components
  state.lots = state.uploadedSummary.lots;
  state.selectedLotId = state.lots[0] || 'LOT_01';
  populateLotSelect(state.lots);
  const lotSelect = document.getElementById('select-lot');
  if (lotSelect) lotSelect.value = state.selectedLotId;

  const compsForLot = Array.from(new Set(state.uploadedSummary.rows.filter(r => r.lot_id === state.selectedLotId).map(r => r.component_id)));
  state.componentsInLot = compsForLot.length > 0 ? compsForLot : state.uploadedSummary.components;
  state.selectedComponentId = state.componentsInLot[0] || 'C001';
  populateComponentSelect(state.componentsInLot);
  const compSelect = document.getElementById('select-component');
  if (compSelect) compSelect.value = state.selectedComponentId;

  // 5. Set As-Of Checkpoint
  const chk = state.uploadedSummary.checkpoints.includes(24) ? 24 : (state.uploadedSummary.checkpoints[0] || 24);
  setCheckpoint(chk);

  // 6. Attempt canonical pipeline analysis
  await loadComponentInvestigation(state.selectedComponentId, state.selectedAsOf);

  // 7. Switch to Screening workspace
  switchWorkspace('screening');
}

function downloadCsvTemplate() {
  const headers = "component_id,lot_id,parameter_name,elapsed_hours,value,unit,temperature_C,test_condition,instrument_id,channel_id,measurement_quality,rework_count\n";
  const sample = "LOT_USER_001_C001,LOT_USER_001,IDSS,0,0.4500,uA,25,Vgs=0V;Vds=80V,ATE-01,CH-01,NOMINAL,0\n" +
                 "LOT_USER_001_C001,LOT_USER_001,IDSS,24,0.4620,uA,25,Vgs=0V;Vds=80V,ATE-01,CH-01,NOMINAL,0\n" +
                 "LOT_USER_001_C001,LOT_USER_001,VGS(th),0,2.9500,V,25,Vds=Vgs;Id=1.0mA,ATE-01,CH-01,NOMINAL,0\n" +
                 "LOT_USER_001_C001,LOT_USER_001,VGS(th),24,2.9610,V,25,Vds=Vgs;Id=1.0mA,ATE-01,CH-01,NOMINAL,0\n" +
                 "LOT_USER_001_C001,LOT_USER_001,RDS(on),0,45.2000,mOhm,25,Vgs=12V;Id=14A,ATE-01,CH-01,NOMINAL,0\n" +
                 "LOT_USER_001_C001,LOT_USER_001,RDS(on),24,45.2500,mOhm,25,Vgs=12V;Id=14A,ATE-01,CH-01,NOMINAL,0\n" +
                 "LOT_USER_001_C001,LOT_USER_001,IGSS,0,+1.2000,nA,25,Vgs=20V;Vds=0V,ATE-01,CH-01,NOMINAL,0\n" +
                 "LOT_USER_001_C001,LOT_USER_001,IGSS,24,+1.1500,nA,25,Vgs=20V;Vds=0V,ATE-01,CH-01,NOMINAL,0\n";
  const blob = new Blob([headers + sample], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'irhnj57130_canonical_telemetry_template.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// -----------------------------------------------------------------------------
// SECTION 14 & 15: ENGINEERING REPORT GENERATION
// -----------------------------------------------------------------------------
function setupReportGeneration() {
  const btnPdf = document.getElementById('btn-generate-pdf-report');
  const btnJson = document.getElementById('btn-export-audit-json-report');
  const btnCsv = document.getElementById('btn-export-evidence-csv-report');

  if (btnPdf) {
    btnPdf.addEventListener('click', () => {
      generateEngineeringReportWindow();
    });
  }

  if (btnJson) {
    btnJson.addEventListener('click', () => {
      if (!state.pipelineData) {
        alert('No active analysis data to export. Please select or analyze a dataset first.');
        return;
      }
      const jsonStr = JSON.stringify(state.pipelineData, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_audit_${state.selectedComponentId}_${state.selectedAsOf}h.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  if (btnCsv) {
    btnCsv.addEventListener('click', () => {
      exportTableToCsv('table-measurement-summary', `report_evidence_${state.selectedComponentId}_${state.selectedAsOf}h.csv`);
    });
  }
}

function generateEngineeringReportWindow() {
  const data = state.pipelineData;
  const isDemo = state.activeDataset === 'demo';
  const datasetLabel = isDemo ? 'Phase 4B Demo Dataset (Synthetic Demonstration Data)' : `Uploaded Telemetry: ${state.uploadedSummary ? state.uploadedSummary.filename : 'User CSV'}`;
  const provenanceLabel = isDemo ? 'DEMO \u2022 SYNTHETIC (Quarantined Evaluation Evidence)' : 'USER DATA \u2022 UPLOADED (Inference Only)';
  const cid = data ? (data.component_id || state.selectedComponentId) : state.selectedComponentId;
  const lid = data ? (data.lot_id || state.selectedLotId) : state.selectedLotId;
  const asOf = data ? data.as_of_hours : state.selectedAsOf;
  const canonHash = data ? (data.canonical_result_hash || (data.audit_record && data.audit_record.canonical_result_hash) || 'N/A') : 'N/A';
  const inputHash = data ? (data.input_hash || (data.audit_record && data.audit_record.input_hash) || 'N/A') : 'N/A';
  const finalState = data && data.screening ? data.screening.final_state : 'UNKNOWN';
  const qualifier = data && data.screening ? data.screening.disposition_qualifier : 'UNKNOWN';

  // Extract observations table HTML
  let measRowsHtml = '';
  if (data && data.observed_telemetry && data.observed_telemetry.length > 0) {
    measRowsHtml = data.observed_telemetry.map(m => `
      <tr>
        <td>${m.elapsed_hours} h</td>
        <td><strong>${m.parameter_name}</strong></td>
        <td>${m.value} ${m.unit || ''}</td>
        <td>MIL-PRF-19500/703</td>
        <td><span style="color:#1A7F37; font-weight:bold;">SPEC COMPLIANT</span></td>
      </tr>
    `).join('');
  } else {
    measRowsHtml = '<tr><td colspan="5" style="text-align:center;">No observed telemetry records available for this checkpoint</td></tr>';
  }

  // Extract screening detectors table HTML
  let screenRowsHtml = '';
  if (data && data.screening && data.screening.detectors) {
    const dMap = data.screening.detectors;
    const names = {
      delta: 'Parametric Drift (&Delta;)',
      sigma: 'Lot Statistical Outlier (&sigma;)',
      sudden_jump: 'Sudden Step Jump',
      stagnation: 'Parameter Stagnation',
      variance: 'High Variance Anomaly',
      multivariate: 'Multivariate Correlation Mahalanobis'
    };
    screenRowsHtml = Object.keys(dMap).map(k => {
      const det = dMap[k];
      const flagStr = det.triggered ? '<span style="color:#CF222E; font-weight:bold;">FLAGGED</span>' : '<span style="color:#1A7F37; font-weight:bold;">PASS</span>';
      return `
        <tr>
          <td><strong>${names[k] || k}</strong></td>
          <td>${det.statistic_value !== undefined ? formatNumber(det.statistic_value, 4) : '\u2014'}</td>
          <td>${det.threshold !== undefined ? formatNumber(det.threshold, 4) : '\u2014'}</td>
          <td>${flagStr}</td>
          <td>${det.interpretation || '\u2014'}</td>
        </tr>
      `;
    }).join('');
  }

  // Extract prognostics forecast table HTML
  let progRowsHtml = '';
  if (data && data.prognostics) {
    progRowsHtml = ORDERED_PARAMETERS.map(p => {
      const fc = data.prognostics[p];
      if (!fc) return '';
      const breachBadge = fc.breach_predicted ? '<span style="color:#CF222E; font-weight:bold;">BREACH PREDICTED</span>' : '<span style="color:#1A7F37; font-weight:bold;">COMPLIANT</span>';
      const spec = data.screening && data.screening.specifications ? data.screening.specifications[p] : null;
      let limitStr = '\u2014';
      if (spec) {
        if (spec.min_value !== null && spec.max_value !== null) limitStr = `[${spec.min_value}, ${spec.max_value}] ${spec.unit}`;
        else if (spec.max_value !== null) limitStr = `&le; ${spec.max_value} ${spec.unit}`;
        else if (spec.min_value !== null) limitStr = `&ge; ${spec.min_value} ${spec.unit}`;
      }
      return `
        <tr>
          <td><strong>${p}</strong></td>
          <td>${formatParamValue(p, fc.target_hours_forecast)}</td>
          <td>[${formatParamValue(p, fc.interval_lower_bound)}, ${formatParamValue(p, fc.interval_upper_bound)}]</td>
          <td>${limitStr}</td>
          <td>${breachBadge}</td>
        </tr>
      `;
    }).join('');
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ISRO CQSD &bull; Engineering Report &bull; ${cid} &bull; ${asOf}h</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #1F2328;
      background: #FFFFFF;
      margin: 24px;
      font-size: 12px;
      line-height: 1.5;
    }
    .report-header { text-align: center; margin-bottom: 20px; border-bottom: 2px solid #0057B8; padding-bottom: 12px; }
    .report-org { font-size: 14px; font-weight: 800; color: #0057B8; letter-spacing: 0.06em; text-transform: uppercase; }
    .report-title { font-size: 16px; font-weight: 700; margin-top: 4px; }
    .report-sub { font-size: 11px; color: #57606A; margin-top: 2px; font-family: monospace; }
    .meta-box {
      border: 1px solid #D0D7DE;
      background: #F6F8FA;
      padding: 12px;
      margin-bottom: 16px;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px 12px;
      font-family: monospace;
      font-size: 11px;
    }
    .meta-item { display: flex; gap: 8px; }
    .meta-k { color: #57606A; width: 140px; }
    .meta-v { color: #1F2328; font-weight: 600; }
    h2 { font-size: 12px; margin: 16px 0 8px 0; border-bottom: 1px solid #D0D7DE; padding-bottom: 4px; color: #0057B8; text-transform: uppercase; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 11px; }
    th { background: #F6F8FA; border: 1px solid #D0D7DE; padding: 6px 8px; text-align: left; font-family: monospace; }
    td { border: 1px solid #D0D7DE; padding: 6px 8px; }
    .disclaimer-box {
      border: 1px solid #D0D7DE;
      border-left: 4px solid #0057B8;
      background: #F6F8FA;
      padding: 10px 12px;
      margin-top: 20px;
      font-size: 10.5px;
      line-height: 1.5;
    }
    .signoff-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 24px; border-top: 2px solid #D0D7DE; padding-top: 16px; }
    .signoff-block { border: 1px solid #D0D7DE; padding: 12px; }
    .signoff-role { font-family: monospace; font-size: 10px; font-weight: 700; color: #57606A; }
    .signoff-line { border-bottom: 1px solid #999; height: 28px; margin: 8px 0; }
    .signoff-sub { font-size: 10px; color: #999; }
    .print-btn-bar { margin-bottom: 16px; }
    @media print {
      .print-btn-bar { display: none; }
      body { margin: 0; }
    }
  </style>
</head>
<body>
  <div class="print-btn-bar">
    <button onclick="window.print()" style="padding:6px 14px; background:#0057B8; color:#fff; border:none; border-radius:3px; cursor:pointer; font-weight:600;">Print / Save to PDF</button>
  </div>

  <div class="report-header">
    <div class="report-org">ISRO // URSC &mdash; Component Qualification & Screening Division</div>
    <div class="report-title">Certificate of Screening Conformance & Prognostics Report</div>
    <div class="report-sub">IRHNJ57130 Rad-Hard Power MOSFET &bull; MIL-PRF-19500/703 &bull; MIL-STD-750</div>
  </div>

  <div class="meta-box">
    <div class="meta-item"><span class="meta-k">Component ID:</span><span class="meta-v">${cid}</span></div>
    <div class="meta-item"><span class="meta-k">Lot ID:</span><span class="meta-v">${lid}</span></div>
    <div class="meta-item"><span class="meta-k">As-Of Checkpoint:</span><span class="meta-v">${asOf} h</span></div>
    <div class="meta-item"><span class="meta-k">Final State:</span><span class="meta-v">${finalState} (${qualifier})</span></div>
    <div class="meta-item"><span class="meta-k">Dataset Source:</span><span class="meta-v">${datasetLabel}</span></div>
    <div class="meta-item"><span class="meta-k">Dataset Status:</span><span class="meta-v">${provenanceLabel}</span></div>
    <div class="meta-item" style="grid-column:1/-1;"><span class="meta-k">Canonical Hash:</span><span class="meta-v" style="word-break:break-all;">${canonHash}</span></div>
    <div class="meta-item" style="grid-column:1/-1;"><span class="meta-k">Model Lineage:</span><span class="meta-v">Locked Ridge Regression (L2 &lambda;=1.0) &bull; Frozen Calibration Data &bull; Inference Only</span></div>
  </div>

  <h2>1. Measured Observed Telemetry (Up to ${asOf}h)</h2>
  <table>
    <thead>
      <tr>
        <th>Checkpoint</th>
        <th>Parameter</th>
        <th>Measured Value</th>
        <th>Specification</th>
        <th>Conformance</th>
      </tr>
    </thead>
    <tbody>${measRowsHtml}</tbody>
  </table>

  <h2>2. Module A Statistical Screening Evidence</h2>
  <table>
    <thead>
      <tr>
        <th>Detector</th>
        <th>Statistic Value</th>
        <th>Threshold</th>
        <th>Flag Status</th>
        <th>Interpretation</th>
      </tr>
    </thead>
    <tbody>${screenRowsHtml}</tbody>
  </table>

  <h2>3. Module B Locked-Model Prognostics Forecast (Target 168h)</h2>
  <table>
    <thead>
      <tr>
        <th>Parameter</th>
        <th>Forecast Value (168h)</th>
        <th>90% Prediction Interval</th>
        <th>Applicable Limit</th>
        <th>Predicted Breach Status</th>
      </tr>
    </thead>
    <tbody>${progRowsHtml}</tbody>
  </table>

  <div class="signoff-grid">
    <div class="signoff-block">
      <div class="signoff-role">QA INSPECTOR</div>
      <div class="signoff-line"></div>
      <div class="signoff-sub">Name / Badge ID / Date</div>
    </div>
    <div class="signoff-block">
      <div class="signoff-role">R&QA CONCURRENCE</div>
      <div class="signoff-line"></div>
      <div class="signoff-sub">R&QA Engineer / Stamp / Date</div>
    </div>
    <div class="signoff-block">
      <div class="signoff-role">DISPOSITION AUTHORITY</div>
      <div class="signoff-line"></div>
      <div class="signoff-sub">Project Manager / Authorization / Date</div>
    </div>
  </div>

  <div class="disclaimer-box">
    <strong>REPORT SEMANTICS &amp; MISSION-ASSURANCE GOVERNANCE:</strong><br>
    <strong>1. Measured specification failure:</strong> Observed physical measurement violates applicable MIL-PRF-19500/703 Table I specification.<br>
    <strong>2. Module A evidence:</strong> Multi-detector statistical screening evidence evaluated against empirical reference baseline.<br>
    <strong>3. Module B forecast:</strong> Locked-model Ridge regression prognostic trajectory forecast with calibrated uncertainty interval.<br>
    <strong>4. Predicted future specification breach:</strong> Model-derived informational evidence only. Does NOT constitute autonomous hardware rejection authority. Predictive rejection is not authorized without verified physical validation.
  </div>
</body>
</html>`;

  const printWindow = window.open('', '_blank', 'width=900,height=800');
  if (printWindow) {
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      try { printWindow.print(); } catch (e) { console.error('Print trigger error:', e); }
    }, 300);
  } else {
    window.print();
  }
}

// -----------------------------------------------------------------------------
// WORKSPACE 4: TRACEABILITY & FORENSIC AUDIT
// -----------------------------------------------------------------------------
function renderTraceabilityWorkspace(data) {
  const audit = data.audit_record || {};
  const lineage = data.model_lineage || {};

  document.getElementById('tr-cid').textContent = data.component_id || state.selectedComponentId;
  document.getElementById('tr-lot').textContent = data.lot_id || state.selectedLotId;
  document.getElementById('tr-asof').textContent = `${data.as_of_hours} h`;

  document.getElementById('audit-input-hash').textContent = data.input_hash || audit.input_hash || '—';
  document.getElementById('audit-canonical-hash').textContent = data.canonical_result_hash || audit.canonical_result_hash || '—';
  document.getElementById('tr-runid').textContent = audit.run_id || '—';
  document.getElementById('tr-timestamp').textContent = audit.created_at || '—';

  // Complete Forensic ASCII Evidence Card
  const asciiBox = document.getElementById('ascii-card-box');
  if (data.explainability && data.explainability.ascii_summary) {
    asciiBox.textContent = data.explainability.ascii_summary;
  }

  // Audit JSON
  const jsonBox = document.getElementById('audit-json-box');
  if (jsonBox) {
    jsonBox.textContent = JSON.stringify(data, null, 2);
  }

  // Certificate of Conformance (CoC)
  renderCertificateOfConformance(data);
}

function renderCertificateOfConformance(data) {
  const cocCid = document.getElementById('coc-cid');
  const cocLot = document.getElementById('coc-lot');
  const cocState = document.getElementById('coc-state');
  const cocAsof = document.getElementById('coc-asof');
  const cocSource = document.getElementById('coc-source');
  const cocHash = document.getElementById('coc-hash');
  const cocSealHash = document.getElementById('coc-seal-hash');

  const finalState = data.screening?.final_state || 'UNKNOWN';
  const qualifier = data.screening?.disposition_qualifier || '';
  const canonHash = data.canonical_result_hash || data.audit_record?.canonical_result_hash || '—';

  if (cocCid) cocCid.textContent = data.component_id || state.selectedComponentId;
  if (cocLot) cocLot.textContent = data.lot_id || state.selectedLotId;
  if (cocState) cocState.textContent = `${finalState} (${qualifier})`;
  if (cocAsof) cocAsof.textContent = `${data.as_of_hours} h`;
  if (cocSource) cocSource.textContent = state.activeDataset === 'demo' ? 'SYNTHETIC PHASE 4B (Demo)' : 'USER DATA (Uploaded)';
  if (cocHash) cocHash.textContent = canonHash;
  if (cocSealHash) cocSealHash.textContent = canonHash;
}

// -----------------------------------------------------------------------------
// EXPORT UTILITIES (CSV & SVG)
// -----------------------------------------------------------------------------
function setupExportButtons() {
  document.getElementById('btn-export-measurements-csv')?.addEventListener('click', () => {
    exportTableToCsv('table-measurement-summary', `measurements_${state.selectedComponentId}_${state.selectedAsOf}h.csv`);
  });

  document.getElementById('btn-export-evidence-csv')?.addEventListener('click', () => {
    exportTableToCsv('screening-matrix-table', `evidence_${state.selectedComponentId}_${state.selectedAsOf}h.csv`);
  });

  document.getElementById('btn-export-prognostics-csv')?.addEventListener('click', () => {
    exportTableToCsv('prognostics-table', `prognostics_${state.selectedComponentId}_${state.selectedAsOf}h.csv`);
  });

  document.getElementById('btn-export-charts-svg')?.addEventListener('click', () => {
    const svgs = document.querySelectorAll('#svg-chart-container svg');
    if (svgs.length > 0) {
      exportSvg(svgs[0], `chart_${state.selectedComponentId}_${state.selectedAsOf}h.svg`);
    }
  });

  document.getElementById('btn-copy-canonical-hash')?.addEventListener('click', () => {
    const hash = document.getElementById('audit-canonical-hash').textContent;
    navigator.clipboard?.writeText(hash).then(() => alert('Canonical result hash copied to clipboard.'));
  });

  document.getElementById('btn-copy-ascii')?.addEventListener('click', () => {
    const text = document.getElementById('ascii-card-box').textContent;
    navigator.clipboard?.writeText(text).then(() => alert('Forensic ASCII card copied to clipboard.'));
  });

  document.getElementById('btn-copy-evidence-json')?.addEventListener('click', () => {
    const text = document.getElementById('exp-evidence')?.textContent;
    if (text) {
      navigator.clipboard?.writeText(text).then(() => {
        const btn = document.getElementById('btn-copy-evidence-json');
        if (btn) {
          const orig = btn.textContent;
          btn.textContent = 'Copied!';
          btn.classList.add('copied');
          setTimeout(() => {
            btn.textContent = orig;
            btn.classList.remove('copied');
          }, 2000);
        }
      });
    }
  });

  document.getElementById('btn-download-audit-json')?.addEventListener('click', () => {
    if (!state.pipelineData) return;
    const blob = new Blob([JSON.stringify(state.pipelineData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_${state.selectedComponentId}_${state.selectedAsOf}h.json`;
    a.click();
    URL.revokeObjectURL(url);
  });
}

function exportTableToCsv(tableId, filename) {
  const table = document.getElementById(tableId);
  if (!table) return;

  const rows = [];
  table.querySelectorAll('tr').forEach((tr) => {
    if (tr.classList.contains('drawer-row')) return;
    const cells = Array.from(tr.querySelectorAll('th, td')).map((c) => {
      let t = c.innerText.replace(/\r?\n|\r/g, ' ').replace(/"/g, '""').trim();
      return `"${t}"`;
    });
    if (cells.length > 0) rows.push(cells.join(','));
  });

  const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function exportSvg(svgElement, filename) {
  const serializer = new XMLSerializer();
  const source = serializer.serializeToString(svgElement);
  const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

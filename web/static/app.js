const API = "";
const LIVE_BUFFER_SIZE = 120;
const CONTROL_DEBOUNCE_MS = 400;

const PHASES = {
  GT: { tipo: "temperatura", selectId: "selectTestGT", statusId: "analyzeStatusGT", resultId: "resultSectionGT", formulaId: "ftFormulaGT", paramsId: "ftParamsGT", chartId: "chartGT" },
  GF: { tipo: "fluxo", selectId: "selectTestGF", statusId: "analyzeStatusGF", resultId: "resultSectionGF", formulaId: "ftFormulaGF", paramsId: "ftParamsGF", chartId: "chartGF" },
  GFT: { tipo: "perturbacao", selectId: "selectTestGFT", statusId: "analyzeStatusGFT", resultId: "resultSectionGFT", formulaId: "ftFormulaGFT", paramsId: "ftParamsGFT", chartId: "chartGFT" },
};

let chartInstances = { GT: null, GF: null, GFT: null };
let chartLiveInstance = null;
let controlState = { resistencia: 0, cooler: 0 };
let liveBuffer = [];
let ws = null;
let wsReconnectTimer = null;
let controlDebounceTimer = null;
let wsUserDisconnect = false;
let lastLiveSample = null;

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

function showStatus(elId, text, isError = false) {
  const el = $(elId);
  if (!el) return;
  el.textContent = text;
  el.className = "status" + (isError ? " error" : text ? " success" : "");
}

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const isActive = btn.getAttribute("data-tab") === tabId;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", isActive);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    const panelId = "panel-" + tabId;
    const isActive = panel.id === panelId;
    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
  });
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab")));
  });
  document.querySelectorAll(".link-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab")));
  });
}

function updateDashboard() {
  const countEl = $("dashboardTestCount");
  if (countEl) {
    const list = $("testList");
    countEl.textContent = list ? list.querySelectorAll("li").length : 0;
  }
  if (lastLiveSample) {
    const t = $("dashboardLiveTemp");
    const v = $("dashboardLiveVazao");
    if (t) t.textContent = lastLiveSample.temperatura != null ? lastLiveSample.temperatura.toFixed(2) + " °C" : "— °C";
    if (v) v.textContent = lastLiveSample.vazao != null ? lastLiveSample.vazao.toFixed(2) + " L/min" : "— L/min";
  }
}

async function listTests() {
  const res = await fetch(API + "/api/tests");
  if (!res.ok) throw new Error("Falha ao listar testes");
  const data = await res.json();
  const list = $("testList");
  const selects = [$("selectTestGT"), $("selectTestGF"), $("selectTestGFT")];
  const currentValues = selects.map((s) => (s ? s.value : ""));

  const optionHtml = '<option value="">— Selecione —</option>';
  selects.forEach((select) => {
    if (select) select.innerHTML = optionHtml;
  });
  if (list) list.innerHTML = "";

  data.tests.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = t.filename || t.id;
    selects.forEach((select) => {
      if (select) select.appendChild(opt.cloneNode(true));
    });
    if (list) {
      const li = document.createElement("li");
      const nameSpan = document.createElement("span");
      nameSpan.className = "test-name";
      nameSpan.textContent = t.filename || t.id;
      const idSpan = document.createElement("span");
      idSpan.textContent = t.id.slice(0, 8) + "\u2026";
      li.appendChild(nameSpan);
      li.appendChild(idSpan);
      list.appendChild(li);
    }
  });

  selects.forEach((select, i) => {
    if (select && currentValues[i] && data.tests.some((t) => t.id === currentValues[i])) select.value = currentValues[i];
  });
  updateDashboard();
}

async function upload() {
  const input = $("fileInput");
  if (!input.files.length) {
    showStatus("uploadStatus", "Selecione um arquivo CSV.", true);
    return;
  }
  const file = input.files[0];
  if (!file.name.toLowerCase().endsWith(".csv")) {
    showStatus("uploadStatus", "O arquivo deve ser .csv", true);
    return;
  }
  showStatus("uploadStatus", "Enviando…");
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch(API + "/api/upload", { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();
    showStatus("uploadStatus", `Salvo: ${data.filename} (${data.id})`);
    await listTests();
    [$("selectTestGT"), $("selectTestGF"), $("selectTestGFT")].forEach((s) => {
      if (s) s.value = data.id;
    });
    input.value = "";
  } catch (e) {
    showStatus("uploadStatus", e.message || "Erro no upload", true);
  }
}

async function analyzePhase(phaseKey) {
  const phase = PHASES[phaseKey];
  const select = $(phase.selectId);
  const testId = select ? select.value : "";
  if (!testId) {
    showStatus(phase.statusId, "Selecione um teste.", true);
    return;
  }
  showStatus(phase.statusId, "Analisando…");
  try {
    const res = await fetch(API + `/api/tests/${encodeURIComponent(testId)}/analyze?tipo=${encodeURIComponent(phase.tipo)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();
    showResultInPhase(phaseKey, data);
    showStatus(phase.statusId, "Análise concluída.");
  } catch (e) {
    showStatus(phase.statusId, e.message || "Erro na análise", true);
  }
}

function showResultInPhase(phaseKey, data) {
  const phase = PHASES[phaseKey];
  const section = $(phase.resultId);
  if (!section) return;
  section.hidden = false;

  const formulaEl = $(phase.formulaId);
  if (formulaEl) formulaEl.textContent = data.formula || "";

  const paramsEl = $(phase.paramsId);
  if (paramsEl) {
    paramsEl.innerHTML = `
      <span><strong>K (ganho)</strong>${escapeHtml(data.K != null ? String(data.K) : "—")}</span>
      <span><strong>τ (s)</strong>${escapeHtml(data.tau != null ? String(data.tau) : "—")}</span>
      <span><strong>L (s)</strong>${escapeHtml(data.L != null ? String(data.L) : "—")}</span>
      <span><strong>Ref. inicial</strong>${escapeHtml(data.ref_inicial != null ? String(data.ref_inicial) : "—")}</span>
    `;
  }

  const tempo = data.tempo || [];
  const dado = data.dado || [];
  const delta = data.delta || [];
  const ajuste = data.ajuste || [];

  if (chartInstances[phaseKey]) chartInstances[phaseKey].destroy();
  const chartEl = $(phase.chartId);
  if (!chartEl) return;
  chartInstances[phaseKey] = new Chart(chartEl.getContext("2d"), {
    type: "line",
    data: {
      labels: tempo,
      datasets: [
        { label: data.saida || "Saída", data: dado, borderColor: "#58a6ff", backgroundColor: "transparent", tension: 0.1 },
        { label: "Δ (ref. inicial)", data: delta, borderColor: "#3fb950", backgroundColor: "transparent", tension: 0.1 },
        { label: "Ajuste FOPDT", data: ajuste, borderColor: "#f85149", borderDash: [4, 2], backgroundColor: "transparent", tension: 0.1 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "Tempo (s)" } },
        y: { title: { display: true, text: data.saida || "Valor" } },
      },
    },
  });
}

async function getControl() {
  try {
    const res = await fetch(API + "/api/control");
    if (!res.ok) return;
    const data = await res.json();
    controlState = data;
    $("sliderResistencia").value = data.resistencia;
    $("resistenciaValue").textContent = data.resistencia;
    $("sliderCooler").value = data.cooler;
    $("coolerValue").textContent = data.cooler;
  } catch (e) {
    showStatus("controlStatus", "Servidor indisponível.", true);
  }
}

async function sendControl() {
  showStatus("controlStatus", "Enviando…");
  try {
    const res = await fetch(API + "/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resistencia: controlState.resistencia, cooler: controlState.cooler }),
    });
    if (!res.ok) throw new Error("Falha ao enviar");
    const data = await res.json();
    controlState = data;
    $("resistenciaValue").textContent = data.resistencia;
    $("coolerValue").textContent = data.cooler;
    showStatus("controlStatus", "Comando enviado.");
  } catch (e) {
    showStatus("controlStatus", e.message || "Erro ao enviar", true);
  }
}

function updateControlUI() {
  $("resistenciaValue").textContent = controlState.resistencia;
  $("coolerValue").textContent = controlState.cooler;
  $("sliderResistencia").value = controlState.resistencia;
  $("sliderCooler").value = controlState.cooler;
}

function scheduleSendControl() {
  if (controlDebounceTimer) clearTimeout(controlDebounceTimer);
  controlDebounceTimer = setTimeout(() => {
    controlDebounceTimer = null;
    sendControl();
  }, CONTROL_DEBOUNCE_MS);
}

function getWsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return proto + "//" + location.host + "/ws";
}

function updateLiveUI(sample) {
  lastLiveSample = sample;
  if (!sample) return;
  const el = (id) => document.getElementById(id);
  if (el("liveTemp")) el("liveTemp").textContent = sample.temperatura != null ? sample.temperatura.toFixed(2) : "—";
  if (el("liveVazao")) el("liveVazao").textContent = sample.vazao != null ? sample.vazao.toFixed(2) : "—";
  if (el("liveCooler")) el("liveCooler").textContent = sample.cooler != null ? sample.cooler : "—";
  if (el("liveResistencia")) el("liveResistencia").textContent = sample.resistencia || "—";
  if (el("liveTimestamp")) el("liveTimestamp").textContent = sample.timestamp ? new Date(sample.timestamp).toLocaleTimeString() : "—";
  updateDashboard();
}

function pushLiveChart(sample) {
  if (sample.temperatura == null && sample.vazao == null) return;
  liveBuffer.push({ t: sample.timestamp || Date.now(), temperatura: sample.temperatura, vazao: sample.vazao });
  if (liveBuffer.length > LIVE_BUFFER_SIZE) liveBuffer.shift();
  if (!chartLiveInstance) return;
  chartLiveInstance.data.labels = liveBuffer.map((_, i) => i);
  chartLiveInstance.data.datasets[0].data = liveBuffer.map((d) => d.temperatura);
  chartLiveInstance.data.datasets[1].data = liveBuffer.map((d) => d.vazao);
  chartLiveInstance.update("none");
}

function updateWsButton(connected) {
  const btn = $("btnWsToggle");
  if (btn) btn.textContent = connected ? "Desconectar" : "Conectar";
}

function disconnectWs() {
  wsUserDisconnect = true;
  if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  if (ws) { ws.close(); ws = null; }
  const wsStatus = document.getElementById("wsStatus");
  if (wsStatus) { wsStatus.textContent = "Desconectado"; wsStatus.className = "ws-status disconnected"; }
  updateWsButton(false);
}

function connectWs() {
  wsUserDisconnect = false;
  if (ws && ws.readyState === WebSocket.OPEN) return;
  const wsStatus = document.getElementById("wsStatus");
  if (wsStatus) { wsStatus.textContent = "Conectando…"; wsStatus.className = "ws-status"; }
  ws = new WebSocket(getWsUrl());
  ws.onopen = () => {
    if (wsStatus) { wsStatus.textContent = "Conectado"; wsStatus.className = "ws-status connected"; }
    updateWsButton(true);
  };
  ws.onmessage = (ev) => {
    try {
      const sample = JSON.parse(ev.data);
      updateLiveUI(sample);
      pushLiveChart(sample);
    } catch (e) {}
  };
  ws.onclose = () => {
    if (wsStatus) { wsStatus.textContent = "Desconectado"; wsStatus.className = "ws-status disconnected"; }
    ws = null;
    updateWsButton(false);
    if (!wsUserDisconnect && wsReconnectTimer == null) {
      wsReconnectTimer = setTimeout(() => { wsReconnectTimer = null; connectWs(); }, 3000);
    }
  };
  ws.onerror = () => { if (wsStatus) wsStatus.textContent = "Erro"; };
}

function initLiveChart() {
  const ctx = document.getElementById("chartLive");
  if (!ctx) return;
  chartLiveInstance = new Chart(ctx.getContext("2d"), {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { label: "Temperatura (°C)", data: [], borderColor: "#58a6ff", backgroundColor: "transparent", tension: 0.1 },
        { label: "Vazão (L/min)", data: [], borderColor: "#3fb950", backgroundColor: "transparent", tension: 0.1 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { x: { title: { display: true, text: "Amostra" } }, y: { title: { display: true, text: "Valor" } } },
    },
  });
}

function setupControl() {
  const sliderR = $("sliderResistencia");
  const sliderC = $("sliderCooler");
  if (sliderR) sliderR.addEventListener("input", () => { controlState.resistencia = parseInt(sliderR.value, 10); updateControlUI(); scheduleSendControl(); });
  if (sliderC) sliderC.addEventListener("input", () => { controlState.cooler = parseInt(sliderC.value, 10); updateControlUI(); scheduleSendControl(); });
  document.querySelectorAll(".control-quick button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const ctrl = btn.getAttribute("data-control");
      const val = parseInt(btn.getAttribute("data-value"), 10);
      controlState[ctrl] = val;
      updateControlUI();
      sendControl();
    });
  });
}

$("btnUpload").addEventListener("click", upload);
$("btnRefreshTests").addEventListener("click", () => listTests().catch(console.error));
$("btnAnalyzeGT").addEventListener("click", () => analyzePhase("GT"));
$("btnAnalyzeGF").addEventListener("click", () => analyzePhase("GF"));
$("btnAnalyzeGFT").addEventListener("click", () => analyzePhase("GFT"));
$("btnWsToggle").addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) disconnectWs();
  else connectWs();
});

setupTabs();
listTests().catch((e) => {
  console.error(e);
  showStatus("uploadStatus", "Servidor indisponível. Verifique se o backend está rodando.", true);
});
getControl().catch(console.error);
setupControl();
initLiveChart();
connectWs();
updateDashboard();

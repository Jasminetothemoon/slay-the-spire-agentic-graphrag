const runIdInput = document.querySelector("#runId");
const statusEl = document.querySelector("#status");
const answerEl = document.querySelector("#answer");
const scoresEl = document.querySelector("#scores");
const evidenceEl = document.querySelector("#evidence");
const languageSelect = document.querySelector("#languageSelect");
const overlayToggle = document.querySelector("#overlayToggle");
const stateSummaryEl = document.querySelector("#stateSummary");
const connectionStatusEl = document.querySelector("#connectionStatus");
const decisionTypeLabelEl = document.querySelector("#decisionTypeLabel");
const lastUpdatedEl = document.querySelector("#lastUpdated");
const topRecommendationEl = document.querySelector("#topRecommendation");
const queryTypeInput = document.querySelector("#queryType");
const optionsInput = document.querySelector("#options");
const recommendButton = document.querySelector("#recommend");

const translations = {
  en: {
    appTitle: "Spire Agentic GraphRAG",
    appSubtitle: "Realtime decision assistant for deck, route, shop, and combat states.",
    language: "Language",
    overlayMode: "Overlay Mode",
    fullMode: "Full Mode",
    startRun: "Start Demo Run",
    runState: "Run State",
    runId: "Run ID",
    runIdPlaceholder: "run id",
    class: "Class",
    hp: "HP",
    gold: "Gold",
    deck: "Deck",
    relics: "Relics",
    syncState: "Sync State",
    recommendation: "Recommendation",
    initialStatus: "Create a run, then request a recommendation.",
    cardPick: "Card Pick",
    relicPick: "Relic Pick",
    shop: "Shop",
    pathing: "Pathing",
    combat: "Combat",
    options: "Options",
    getRecommendation: "Get Recommendation",
    graphEvidence: "Graph Evidence",
    connecting: "Connecting",
    connected: "Live",
    disconnected: "Offline",
    decision: "Decision",
    lastUpdated: "Updated",
    confidence: "Confidence",
    validity: "Validity",
    valid: "Valid",
    invalid: "Invalid",
    keyRisk: "Risk",
    startFirst: "Start a run first.",
    started: (runId) => `Started ${runId}.`,
    stateSynced: "State synced.",
    returned: (latency) => `Recommendation returned in ${latency}ms.`,
    realtimeUpdate: (runId) => `Realtime update for ${runId}.`,
    websocketUnavailable: "WebSocket unavailable; HTTP mode still works.",
    score: "Score",
    reasons: "Reasons",
    risks: "Risks",
    stateSummary: "State",
    topPick: "Top pick",
    noScores: "No recommendation yet.",
    noLiveOptions: "No live decision options are available yet.",
    waitingForDecision: "Live state synced. Waiting for a real game decision.",
    act: "Act",
    floor: "Floor",
    source: "Source",
    liveConnected: "Live bridge connected.",
    liveState: (runId) => `Live state synced from ${runId}.`,
    liveRecommendation: (runId) => `Live recommendation rendered for ${runId}.`,
  },
  zh: {
    appTitle: "尖塔 Agentic GraphRAG",
    appSubtitle: "面向卡组、路线、商店与战斗状态的实时决策助手。",
    language: "语言",
    overlayMode: "覆盖层模式",
    fullMode: "完整模式",
    startRun: "开始演示局",
    runState: "当前局面",
    runId: "局面 ID",
    runIdPlaceholder: "局面 ID",
    class: "职业",
    hp: "血量",
    gold: "金币",
    deck: "卡组",
    relics: "遗物",
    syncState: "同步状态",
    recommendation: "推荐结果",
    initialStatus: "先创建一局，然后请求推荐。",
    cardPick: "选牌",
    relicPick: "选遗物",
    shop: "商店",
    pathing: "路线",
    combat: "战斗",
    options: "候选项",
    getRecommendation: "获取推荐",
    graphEvidence: "图谱证据",
    connecting: "连接中",
    connected: "实时",
    disconnected: "离线",
    decision: "决策",
    lastUpdated: "更新",
    confidence: "置信度",
    validity: "有效性",
    valid: "有效",
    invalid: "无效",
    keyRisk: "风险",
    startFirst: "请先开始一局。",
    started: (runId) => `已开始 ${runId}。`,
    stateSynced: "状态已同步。",
    returned: (latency) => `推荐已返回，用时 ${latency}ms。`,
    realtimeUpdate: (runId) => `${runId} 有实时更新。`,
    websocketUnavailable: "WebSocket 不可用；HTTP 模式仍可使用。",
    score: "分数",
    reasons: "理由",
    risks: "风险",
    stateSummary: "状态",
    topPick: "首选",
    noScores: "还没有推荐。",
    noLiveOptions: "当前还没有实时候选项。",
    waitingForDecision: "已同步实时状态，正在等待真实游戏决策。",
    act: "阶段",
    floor: "楼层",
    source: "来源",
    liveConnected: "实时桥接已连接。",
    liveState: (runId) => `已同步 ${runId} 的实时状态。`,
    liveRecommendation: (runId) => `已渲染 ${runId} 的实时推荐。`,
  },
};

let currentLanguage = localStorage.getItem("spireLanguage") || "en";
let overlayMode = localStorage.getItem("spireOverlayMode") === "true";
let latestState = {};
let lastUpdatedAt = null;
let connectionState = "connecting";
window.lastRecommendation = null;

function t(key, ...args) {
  const value = translations[currentLanguage][key] || translations.en[key] || key;
  return typeof value === "function" ? value(...args) : value;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function applyLanguage() {
  document.documentElement.lang = currentLanguage === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  languageSelect.value = currentLanguage;
  overlayToggle.textContent = overlayMode ? t("fullMode") : t("overlayMode");
  updateConnectionStatus(connectionState);
  renderStateInputs();
  if (window.lastRecommendation) {
    answerEl.textContent = localizedReasoning(window.lastRecommendation);
    evidenceEl.textContent = JSON.stringify(localizedGraphContext(window.lastRecommendation), null, 2);
  }
  renderScores(window.lastRecommendation?.option_scores || []);
  renderStateSummary();
  renderTopRecommendation();
  updateLiveStrip();
}

function applyOverlayMode() {
  document.body.classList.toggle("overlay-mode", overlayMode);
  localStorage.setItem("spireOverlayMode", String(overlayMode));
  overlayToggle.textContent = overlayMode ? t("fullMode") : t("overlayMode");
  renderScores(window.lastRecommendation?.option_scores || []);
  renderStateSummary();
  renderTopRecommendation();
}

languageSelect.addEventListener("change", () => {
  currentLanguage = languageSelect.value;
  localStorage.setItem("spireLanguage", currentLanguage);
  applyLanguage();
  renderScores(window.lastRecommendation?.option_scores || []);
  if (window.lastRecommendation) {
    statusEl.textContent = t("returned", window.lastRecommendation.latency_ms);
  }
});

overlayToggle.addEventListener("click", () => {
  overlayMode = !overlayMode;
  applyOverlayMode();
});

function lines(id) {
  return document
    .querySelector(id)
    .value.split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function setLines(id, values) {
  if (Array.isArray(values)) {
    document.querySelector(id).value = values.join("\n");
  }
}

function currentStatePayload() {
  return {
    run_id: runIdInput.value,
    source: latestState.source || "web_demo",
    character_class: document.querySelector("#characterClass").value,
    current_hp: Number(document.querySelector("#hp").value),
    max_hp: Number(latestState.max_hp || 70),
    gold: Number(document.querySelector("#gold").value),
    act: Number(latestState.act || 1),
    current_floor: Number(latestState.current_floor || 10),
    energy: Number(latestState.energy || 3),
    deck: lines("#deck"),
    upgraded_cards: latestState.upgraded_cards || [],
    relics: lines("#relics"),
    potions: latestState.potions || [],
    combat_state: latestState.combat_state || {},
    enemies: latestState.enemies || [],
    hand_cards: latestState.hand_cards || [],
    draw_pile: latestState.draw_pile || [],
    discard_pile: latestState.discard_pile || [],
    map_options: latestState.map_options || [],
    boss: latestState.boss || null,
  };
}

function zhState() {
  return latestState.localized?.zh || {};
}

function localizedList(key, fallback) {
  if (currentLanguage === "zh" && Array.isArray(zhState()[key])) {
    return zhState()[key];
  }
  return fallback || [];
}

function renderStateInputs() {
  if (!latestState || !Object.keys(latestState).length) {
    return;
  }
  setLines("#deck", localizedList("deck", latestState.deck));
  setLines("#relics", localizedList("relics", latestState.relics));
  if (Array.isArray(latestState.options) && latestState.options.length) {
    setLines("#options", localizedList("options", latestState.options));
  }
}

function localizedScore(score, index) {
  if (currentLanguage !== "zh") {
    return score;
  }
  const localized = window.lastRecommendation?.localized?.zh?.option_scores?.[index] || {};
  return {
    ...score,
    name: localized.name || score.name,
    reasons: localized.reasons || score.reasons,
    risks: localized.risks || score.risks,
  };
}

function localizedReasoning(data) {
  if (currentLanguage === "zh") {
    return data.localized?.zh?.reasoning || data.reasoning;
  }
  return data.reasoning;
}

function localizedGraphContext(data) {
  if (currentLanguage === "zh") {
    return data.localized?.zh?.graph_context || data.graph_context;
  }
  return data.graph_context;
}

function markUpdated() {
  lastUpdatedAt = new Date();
  updateLiveStrip();
}

function updateConnectionStatus(status) {
  connectionState = status;
  connectionStatusEl.classList.remove("connected", "disconnected");
  if (status === "connected") {
    connectionStatusEl.classList.add("connected");
    connectionStatusEl.textContent = t("connected");
    return;
  }
  connectionStatusEl.classList.add("disconnected");
  connectionStatusEl.textContent = status === "connecting" ? t("connecting") : t("disconnected");
}

function updateLiveStrip() {
  decisionTypeLabelEl.textContent = queryTypeInput.value;
  lastUpdatedEl.textContent = lastUpdatedAt ? lastUpdatedAt.toLocaleTimeString() : "-";
}

function applyIncomingState(state) {
  latestState = { ...latestState, ...state };
  markUpdated();
  if (state.run_id) {
    runIdInput.value = state.run_id;
  }
  if (state.character_class) {
    document.querySelector("#characterClass").value = state.character_class;
  }
  if (Number.isFinite(Number(state.current_hp))) {
    document.querySelector("#hp").value = state.current_hp;
  }
  if (Number.isFinite(Number(state.gold))) {
    document.querySelector("#gold").value = state.gold;
  }
  renderStateInputs();
  if (state.query_type) {
    queryTypeInput.value = state.query_type;
  }
  if (Array.isArray(state.options) && state.options.length) {
    setLines("#options", localizedList("options", state.options));
  } else if (state.source === "mod_bridge") {
    setLines("#options", []);
  }
  updateRecommendationAvailability();
  renderStateSummary();
}

function renderRecommendation(data) {
  window.lastRecommendation = data;
  markUpdated();
  answerEl.textContent = localizedReasoning(data);
  evidenceEl.textContent = JSON.stringify(localizedGraphContext(data), null, 2);
  renderScores(data.option_scores || []);
  renderStateSummary();
  renderTopRecommendation();
}

function renderStateSummary() {
  const state = currentStatePayload();
  const topScore = window.lastRecommendation?.option_scores?.[0];
  const displayTopScore = topScore ? localizedScore(topScore, 0) : null;
  const stateClass = currentLanguage === "zh" ? zhState().character_class || state.character_class : state.character_class;
  const chips = [
    `${t("class")}: ${stateClass || "-"}`,
    `${t("hp")}: ${state.current_hp}/${state.max_hp}`,
    `${t("gold")}: ${state.gold}`,
    `${t("act")}: ${state.act}`,
    `${t("floor")}: ${state.current_floor}`,
    `${t("source")}: ${state.source}`,
  ];

  stateSummaryEl.innerHTML = `
    <div class="state-chip-row">
      <span class="state-label">${t("stateSummary")}</span>
      ${chips.map((chip) => `<span class="state-chip">${escapeHtml(chip)}</span>`).join("")}
    </div>
    <div class="top-pick">
      <span>${t("topPick")}</span>
      <strong>${escapeHtml(displayTopScore ? `${displayTopScore.name} / ${displayTopScore.score}` : t("noScores"))}</strong>
    </div>
  `;
}

function renderTopRecommendation() {
  const topScore = window.lastRecommendation?.option_scores?.[0];
  if (!topScore) {
    topRecommendationEl.innerHTML = `<div class="empty-top">${escapeHtml(t("noScores"))}</div>`;
    return;
  }
  const displayScore = localizedScore(topScore, 0);
  const keyReason = displayScore.reasons?.[0] || "";
  const keyRisk = displayScore.risks?.[0] || "";
  topRecommendationEl.innerHTML = `
    <div class="top-rank">#1</div>
    <div class="top-copy">
      <span>${escapeHtml(t("topPick"))}</span>
      <strong>${escapeHtml(displayScore.name)}</strong>
      <p>${escapeHtml(keyReason)}</p>
      ${keyRisk ? `<p class="risk-line">${escapeHtml(t("keyRisk"))}: ${escapeHtml(keyRisk)}</p>` : ""}
    </div>
    <div class="top-metrics">
      <span>${escapeHtml(t("score"))}<strong>${escapeHtml(topScore.score)}</strong></span>
      <span>${escapeHtml(t("confidence"))}<strong>${escapeHtml(topScore.confidence ?? "-")}</strong></span>
      <span>${escapeHtml(t("validity"))}<strong>${escapeHtml(topScore.valid === false ? t("invalid") : t("valid"))}</strong></span>
    </div>
  `;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function loadLiveStateFallback() {
  try {
    const response = await fetch("/mod/live");
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    const state = payload.state || payload;
    applyIncomingState(state);
    statusEl.textContent = t("liveState", state.run_id || "mod_live");
  } catch {
    // The live run may not exist yet; WebSocket updates will fill it in later.
  }
}

document.querySelector("#startRun").addEventListener("click", async () => {
  const data = await postJson("/start_run", {
    character_class: document.querySelector("#characterClass").value,
    ascension_level: 20,
    max_hp: 70,
    source: "web_demo",
  });
  runIdInput.value = data.run_id;
  statusEl.textContent = t("started", data.run_id);
  await syncState();
});

async function syncState() {
  if (!runIdInput.value) {
    statusEl.textContent = t("startFirst");
    return;
  }
  await postJson("/update_state", currentStatePayload());
  statusEl.textContent = t("stateSynced");
  markUpdated();
  renderStateSummary();
}

document.querySelector("#syncState").addEventListener("click", syncState);

document.querySelectorAll("#characterClass, #hp, #gold, #deck, #relics").forEach((node) => {
  node.addEventListener("input", renderStateSummary);
});

queryTypeInput.addEventListener("change", () => {
  updateLiveStrip();
  updateRecommendationAvailability();
});

recommendButton.addEventListener("click", async () => {
  if (!runIdInput.value) {
    statusEl.textContent = t("startFirst");
    return;
  }
  if (latestState.source !== "mod_bridge") {
    await syncState();
  }
  const options = lines("#options");
  const queryType = queryTypeInput.value;
  if (queryType !== "combat" && !options.length) {
    statusEl.textContent = t("noLiveOptions");
    return;
  }
  const data = await postJson("/get_recommendation", {
    run_id: runIdInput.value,
    query_type: queryType,
    options,
    user_query: "Recommend the best option.",
  });
  renderRecommendation(data);
  statusEl.textContent = t("returned", data.latency_ms);
});

function updateRecommendationAvailability() {
  const options = lines("#options");
  const hasCombatHand = Array.isArray(latestState.hand_cards) && latestState.hand_cards.length > 0;
  const hasDecision = options.length > 0 || (queryTypeInput.value === "combat" && hasCombatHand);
  recommendButton.disabled = !hasDecision;
  if (!hasDecision && latestState.source === "mod_bridge") {
    statusEl.textContent = t("waitingForDecision");
  }
}

function renderScores(optionScores) {
  if (!optionScores.length) {
    scoresEl.innerHTML = "";
    return;
  }

  scoresEl.innerHTML = optionScores
    .map(
      (rawScore, index) => {
        const score = localizedScore(rawScore, index);
        return `
      <article class="score-card ${index === 0 ? "top-score" : ""}">
        <header>
          <span>${escapeHtml(score.name)}</span>
          <span>${t("score")}: ${escapeHtml(score.score)} / ${t("confidence")}: ${escapeHtml(score.confidence ?? "-")}</span>
        </header>
        <ul>
          <li><strong>${t("reasons")}:</strong></li>
          ${(score.reasons || []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
          ${(score.risks || []).length ? `<li class="risk"><strong>${t("risks")}:</strong></li>` : ""}
          ${(score.risks || []).map((risk) => `<li class="risk">${escapeHtml(risk)}</li>`).join("")}
        </ul>
      </article>`;
      }
    )
    .join("");
}

try {
  const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  updateConnectionStatus("connecting");
  socket.onopen = () => {
    updateConnectionStatus("connected");
    statusEl.textContent = t("liveConnected");
    loadLiveStateFallback();
  };
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "state_updated") {
      applyIncomingState(data.state || {});
      statusEl.textContent = t("liveState", data.run_id);
    }
    if (data.type === "recommendation" && data.response) {
      renderRecommendation(data.response);
      statusEl.textContent = t("liveRecommendation", data.run_id);
    } else if (data.type === "recommendation") {
      statusEl.textContent = t("realtimeUpdate", data.run_id);
    }
  };
  socket.onclose = () => updateConnectionStatus("disconnected");
  socket.onerror = () => updateConnectionStatus("disconnected");
} catch {
  updateConnectionStatus("disconnected");
  statusEl.textContent = t("websocketUnavailable");
}

applyOverlayMode();
applyLanguage();
renderTopRecommendation();
updateLiveStrip();
loadLiveStateFallback();
updateRecommendationAvailability();

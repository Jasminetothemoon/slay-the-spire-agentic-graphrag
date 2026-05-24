const runIdInput = document.querySelector("#runId");
const statusEl = document.querySelector("#status");
const answerEl = document.querySelector("#answer");
const scoresEl = document.querySelector("#scores");
const evidenceEl = document.querySelector("#evidence");
const languageSelect = document.querySelector("#languageSelect");
const overlayToggle = document.querySelector("#overlayToggle");
const stateSummaryEl = document.querySelector("#stateSummary");

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
    floor: "Floor",
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
    floor: "楼层",
  },
};

let currentLanguage = localStorage.getItem("spireLanguage") || "en";
let overlayMode = localStorage.getItem("spireOverlayMode") === "true";
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
  renderStateSummary();
}

function applyOverlayMode() {
  document.body.classList.toggle("overlay-mode", overlayMode);
  localStorage.setItem("spireOverlayMode", String(overlayMode));
  overlayToggle.textContent = overlayMode ? t("fullMode") : t("overlayMode");
  renderScores(window.lastRecommendation?.option_scores || []);
  renderStateSummary();
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

function currentStatePayload() {
  return {
    run_id: runIdInput.value,
    character_class: document.querySelector("#characterClass").value,
    current_hp: Number(document.querySelector("#hp").value),
    max_hp: 70,
    gold: Number(document.querySelector("#gold").value),
    act: 1,
    current_floor: 10,
    deck: lines("#deck"),
    relics: lines("#relics"),
    potions: [],
  };
}

function renderStateSummary() {
  const state = currentStatePayload();
  const topScore = window.lastRecommendation?.option_scores?.[0];
  const chips = [
    `${t("class")}: ${state.character_class || "-"}`,
    `${t("hp")}: ${state.current_hp}/${state.max_hp}`,
    `${t("gold")}: ${state.gold}`,
    `${t("floor")}: ${state.current_floor}`,
  ];

  stateSummaryEl.innerHTML = `
    <div class="state-chip-row">
      <span class="state-label">${t("stateSummary")}</span>
      ${chips.map((chip) => `<span class="state-chip">${escapeHtml(chip)}</span>`).join("")}
    </div>
    <div class="top-pick">
      <span>${t("topPick")}</span>
      <strong>${escapeHtml(topScore ? `${topScore.name} · ${topScore.score}` : t("noScores"))}</strong>
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
  renderStateSummary();
}

document.querySelector("#syncState").addEventListener("click", syncState);

document.querySelectorAll("#characterClass, #hp, #gold, #deck, #relics").forEach((node) => {
  node.addEventListener("input", renderStateSummary);
});

document.querySelector("#recommend").addEventListener("click", async () => {
  if (!runIdInput.value) {
    statusEl.textContent = t("startFirst");
    return;
  }
  await syncState();
  const data = await postJson("/get_recommendation", {
    run_id: runIdInput.value,
    query_type: document.querySelector("#queryType").value,
    options: lines("#options"),
    user_query: "Recommend the best option.",
  });
  window.lastRecommendation = data;
  answerEl.textContent = data.reasoning;
  evidenceEl.textContent = JSON.stringify(data.graph_context, null, 2);
  renderScores(data.option_scores);
  renderStateSummary();
  statusEl.textContent = t("returned", data.latency_ms);
});

function renderScores(optionScores) {
  if (!optionScores.length) {
    scoresEl.innerHTML = "";
    return;
  }

  scoresEl.innerHTML = optionScores
    .map(
      (score, index) => `
      <article class="score-card ${index === 0 ? "top-score" : ""}">
        <header><span>${escapeHtml(score.name)}</span><span>${t("score")}: ${escapeHtml(score.score)}</span></header>
        <ul>
          <li><strong>${t("reasons")}:</strong></li>
          ${score.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
          ${(score.risks || []).length ? `<li class="risk"><strong>${t("risks")}:</strong></li>` : ""}
          ${(score.risks || []).map((risk) => `<li class="risk">${escapeHtml(risk)}</li>`).join("")}
        </ul>
      </article>`
    )
    .join("");
}

try {
  const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "recommendation") {
      statusEl.textContent = t("realtimeUpdate", data.run_id);
    }
  };
} catch {
  statusEl.textContent = t("websocketUnavailable");
}

applyOverlayMode();
applyLanguage();

const runIdInput = document.querySelector("#runId");
const statusEl = document.querySelector("#status");
const answerEl = document.querySelector("#answer");
const scoresEl = document.querySelector("#scores");
const evidenceEl = document.querySelector("#evidence");

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
  statusEl.textContent = `Started ${data.run_id}.`;
  await syncState();
});

async function syncState() {
  if (!runIdInput.value) {
    statusEl.textContent = "Start a run first.";
    return;
  }
  await postJson("/update_state", currentStatePayload());
  statusEl.textContent = "State synced.";
}

document.querySelector("#syncState").addEventListener("click", syncState);

document.querySelector("#recommend").addEventListener("click", async () => {
  if (!runIdInput.value) {
    statusEl.textContent = "Start a run first.";
    return;
  }
  await syncState();
  const data = await postJson("/get_recommendation", {
    run_id: runIdInput.value,
    query_type: document.querySelector("#queryType").value,
    options: lines("#options"),
    user_query: "Recommend the best option.",
  });
  answerEl.textContent = data.reasoning;
  evidenceEl.textContent = JSON.stringify(data.graph_context, null, 2);
  scoresEl.innerHTML = data.option_scores
    .map(
      (score) => `
      <article class="score-card">
        <header><span>${score.name}</span><span>${score.score}</span></header>
        <ul>
          ${score.reasons.map((reason) => `<li>${reason}</li>`).join("")}
          ${(score.risks || []).map((risk) => `<li class="risk">${risk}</li>`).join("")}
        </ul>
      </article>`
    )
    .join("");
  statusEl.textContent = `Recommendation returned in ${data.latency_ms}ms.`;
});

try {
  const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "recommendation") {
      statusEl.textContent = `Realtime update for ${data.run_id}.`;
    }
  };
} catch {
  statusEl.textContent = "WebSocket unavailable; HTTP mode still works.";
}

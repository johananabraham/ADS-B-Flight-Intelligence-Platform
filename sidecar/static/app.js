const tracks = new Map();
let newestFirst = true;
const byId = (id) => document.getElementById(id);
const escapeText = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);

async function json(path) {
  const response = await fetch(path, {cache: "no-store"});
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function stateClass(state) { return state.toLowerCase(); }
function shortId(value) { return value.slice(0, 8); }
function renderTracks() {
  const values = [...tracks.values()].sort((a,b) => newestFirst ? b.observed_at.localeCompare(a.observed_at) : a.observed_at.localeCompare(b.observed_at));
  for (const state of ["NOMINAL","QUESTIONABLE","INSUFFICIENT_DATA"]) {
    byId(`count-${state === "INSUFFICIENT_DATA" ? "insufficient" : state.toLowerCase()}`).textContent = values.filter((item) => item.state === state).length;
  }
  byId("tracks").replaceChildren(...(values.length ? values.map((item) => {
    const row = document.createElement("tr"); row.dataset.track = item.track_id; row.tabIndex = 0;
    row.innerHTML = `<td>${shortId(item.track_id)}</td><td><span class="state ${stateClass(item.state)}">${item.state}</span></td><td>${item.observation_count}</td><td>${item.window_seconds.toFixed(1)}s</td><td>${item.active_evidence.length}</td>`;
    row.addEventListener("click", () => showTrack(item.track_id));
    row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") showTrack(item.track_id); });
    return row;
  }) : [Object.assign(document.createElement("tr"), {innerHTML:'<td colspan="5">Waiting for observations…</td>'})]));
}

function evidenceCard(item) {
  const values = Object.entries(item.measured).map(([key,value]) => `<div>${escapeText(key)}<br><strong>${escapeText(value)}</strong></div>`).join("");
  const limits = Object.entries(item.thresholds).map(([key,value]) => `<div>${escapeText(key)} limit<br><strong>${escapeText(value)}</strong></div>`).join("");
  return `<article class="evidence"><strong>${escapeText(item.kind)} · ${escapeText(item.severity)}</strong><p>${escapeText(item.summary)}</p><div class="measure">${values}${limits}</div></article>`;
}

async function showTrack(trackId) {
  const item = await json(`/api/v1/integrity/tracks/${encodeURIComponent(trackId)}`);
  const evidence = item.active_evidence.length ? item.active_evidence.map(evidenceCard).join("") : "<p>No active integrity evidence.</p>";
  byId("track-detail").innerHTML = `<p class="eyebrow">TRACK ${shortId(item.track_id)}</p><h2>${item.state}</h2><p>${item.observation_count} observations across ${item.window_seconds.toFixed(1)} seconds</p>${evidence}<h3>Limitations</h3><ul>${item.limitations.map((value)=>`<li>${escapeText(value)}</li>`).join("") || "<li>None currently reported.</li>"}</ul>`;
  byId("track-dialog").showModal();
}

function renderHealth(health) {
  const panel = byId("health"); panel.className = `health ${health.connection.toLowerCase()}`;
  byId("health-state").textContent = health.connection; byId("health-detail").textContent = health.detail;
  byId("policy").textContent = `${health.source_mode} · policy ${health.policy_version}`;
}

async function loadEvents() {
  const kind = byId("kind-filter").value;
  const data = await json(`/api/v1/integrity/events?limit=100${kind ? `&kind=${encodeURIComponent(kind)}` : ""}`);
  byId("events").replaceChildren(...(data.events.length ? data.events.map((event) => {
    const row = document.createElement("li");
    row.innerHTML = `<time>${new Date(event.observed_at).toLocaleString()}</time><p><strong>${escapeText(event.event_type)} · ${escapeText(event.evidence.kind)}</strong><br>${escapeText(event.evidence.summary)}</p>`; return row;
  }) : [Object.assign(document.createElement("li"), {textContent:"No integrity events recorded."})]));
}

async function bootstrap() {
  try {
    const [health, data] = await Promise.all([json("/api/v1/integrity/health"), json("/api/v1/integrity/tracks")]);
    renderHealth(health); data.tracks.forEach((item) => tracks.set(item.track_id,item)); renderTracks(); await loadEvents();
  } catch (error) { byId("health-detail").textContent = `Local API unavailable: ${error.message}`; }
  connect();
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${location.host}/api/v1/integrity/stream`);
  socket.onmessage = ({data}) => { const message = JSON.parse(data); if (message.type === "snapshot") { tracks.set(message.snapshot.track_id,message.snapshot); renderTracks(); } if (message.type === "receiver_health") renderHealth(message.health); if (message.type.startsWith("evidence_")) loadEvents(); };
  socket.onclose = () => setTimeout(connect, 2000);
}

byId("sort").addEventListener("click", () => { newestFirst = !newestFirst; byId("sort").textContent = newestFirst ? "Newest first" : "Oldest first"; renderTracks(); });
byId("kind-filter").addEventListener("change", loadEvents);
bootstrap();

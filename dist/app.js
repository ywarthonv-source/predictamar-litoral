import {
  SCOPE_LABELS,
  STATE_LABELS,
  VARIABLE_DEFINITIONS,
  presentVariable,
  sourceLabel,
  validateSnapshot,
} from "./app-model.js";

const root = document.documentElement;
const endpoint = root.dataset.snapshotEndpoint;
const dataMode = root.dataset.dataMode;

const elements = {
  form: document.querySelector("#snapshot-form"),
  date: document.querySelector("#target-date"),
  status: document.querySelector("#app-status"),
  dashboard: document.querySelector("#dashboard"),
  empty: document.querySelector("#empty-state"),
  emptyTitle: document.querySelector("#empty-title"),
  emptyCopy: document.querySelector("#empty-copy"),
  restoreDate: document.querySelector("#restore-date"),
  safetyCard: document.querySelector("#safety-card"),
  safetyTitle: document.querySelector("#safety-title"),
  safetyCopy: document.querySelector("#safety-copy"),
  safetyNotice: document.querySelector("#safety-notice"),
  available: document.querySelector("#available-count"),
  noData: document.querySelector("#no-data-count"),
  errors: document.querySelector("#error-count"),
  snapshotStatus: document.querySelector("#snapshot-status"),
  operationalRange: document.querySelector("#operational-range"),
  fieldWidth: document.querySelector("#field-width"),
  queryStamp: document.querySelector("#query-stamp"),
  variableGroups: document.querySelector("#variable-groups"),
  offlineBanner: document.querySelector("#offline-banner"),
  installButton: document.querySelector("#install-button"),
};

let snapshot = null;
let deferredInstallPrompt = null;

function formatDate(value) {
  const date = new Date(`${value}T12:00:00Z`);
  return new Intl.DateTimeFormat("es-PE", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function hideAllSurfaces() {
  elements.status.hidden = true;
  elements.dashboard.hidden = true;
  elements.empty.hidden = true;
}

function showLoading(message = "Cargando la muestra ambiental…") {
  hideAllSurfaces();
  elements.status.innerHTML = "";
  const spinner = document.createElement("span");
  spinner.className = "spinner";
  spinner.setAttribute("aria-hidden", "true");
  elements.status.append(spinner, document.createTextNode(message));
  elements.status.hidden = false;
}

function showEmpty(title, copy, buttonLabel = "Volver a la fecha disponible") {
  hideAllSurfaces();
  elements.emptyTitle.textContent = title;
  elements.emptyCopy.textContent = copy;
  elements.restoreDate.textContent = buttonLabel;
  elements.empty.hidden = false;
  elements.emptyTitle.focus?.();
}

function createVariableCard(definition, result) {
  const presentation = presentVariable(result);
  const card = document.createElement("article");
  card.className = "variable-card";
  card.dataset.state = result.state;

  const top = document.createElement("div");
  top.className = "card-top";
  const title = document.createElement("h3");
  title.textContent = definition.label;
  const state = document.createElement("span");
  state.className = "state-badge";
  state.dataset.state = result.state;
  state.textContent = STATE_LABELS[result.state] || "Estado desconocido";
  top.append(title, state);

  const value = document.createElement("p");
  value.className = "variable-value";
  value.textContent = presentation.value;
  const detail = document.createElement("p");
  detail.className = "variable-detail";
  detail.textContent = presentation.detail;

  const meta = document.createElement("div");
  meta.className = "card-meta";
  const source = document.createElement("div");
  source.className = "source-meta";
  const sourceCaption = document.createElement("span");
  sourceCaption.textContent = "Fuente";
  const sourceName = document.createElement("strong");
  sourceName.textContent = sourceLabel(result);
  source.append(sourceCaption, sourceName);
  const scope = document.createElement("span");
  scope.className = "scope-badge";
  scope.textContent = SCOPE_LABELS[result.spatial_scope] || result.spatial_scope;
  meta.append(source, scope);

  card.append(top, value, detail, meta);
  return card;
}

function renderVariables(data) {
  elements.variableGroups.replaceChildren();
  const groupNames = [...new Set(VARIABLE_DEFINITIONS.map((item) => item.group))];

  for (const groupName of groupNames) {
    const section = document.createElement("section");
    section.className = "variable-group";
    section.setAttribute("aria-label", groupName);
    const heading = document.createElement("div");
    heading.className = "group-title";
    heading.textContent = groupName;
    const grid = document.createElement("div");
    grid.className = "variable-grid";

    for (const definition of VARIABLE_DEFINITIONS.filter((item) => item.group === groupName)) {
      grid.append(createVariableCard(definition, data.variables[definition.id]));
    }
    section.append(heading, grid);
    elements.variableGroups.append(section);
  }
}

function renderSafety(data) {
  const wave = presentVariable(data.variables.oleaje);
  const blocked = data.safety.blocked;
  elements.safetyCard.dataset.blocked = String(blocked);
  elements.safetyTitle.textContent = blocked
    ? "Consulta bloqueada por oleaje"
    : "Oleaje bajo el umbral provisional";
  elements.safetyCopy.textContent = blocked
    ? `${wave.value}. La compuerta se mantiene bloqueada por precaución.`
    : `${wave.value}. La compuerta ambiental no bloquea esta consulta.`;
  elements.safetyNotice.textContent = data.safety.not_authorization_notice;
}

function renderDashboard(data) {
  hideAllSurfaces();
  renderSafety(data);
  renderVariables(data);

  elements.available.textContent = data.counts.available;
  elements.noData.textContent = data.counts.no_data;
  elements.errors.textContent = data.counts.error;
  elements.snapshotStatus.textContent =
    data.status === "complete"
      ? "Las diez variables devolvieron una salida admisible. Esto no demuestra validez pesquera."
      : "La consulta conserva las variables disponibles y señala las ausencias de forma explícita.";

  const spatial = data.spatial_context;
  elements.operationalRange.textContent = `${spatial.operational_range_min_km}–${spatial.operational_range_max_km} km`;
  elements.fieldWidth.textContent = `±${String(spatial.field_half_width_deg).replace(".", ",")}°`;
  elements.queryStamp.textContent = `Caleta Pucusana · ${formatDate(data.request.target_date)}`;
  elements.dashboard.hidden = false;
}

function handleQuery() {
  if (!snapshot) return;
  if (dataMode === "fixture" && elements.date.value !== snapshot.request.target_date) {
    showEmpty(
      "No hay una muestra para esa fecha",
      `Esta demostración solo contiene la muestra sintética del ${formatDate(snapshot.request.target_date)}.`,
    );
    return;
  }
  renderDashboard(snapshot);
}

async function loadSnapshot() {
  showLoading();
  try {
    const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    snapshot = validateSnapshot(await response.json());
    elements.date.value = snapshot.request.target_date;
    handleQuery();
  } catch (error) {
    console.error("No se pudo cargar la muestra ambiental", error);
    showEmpty(
      "No pudimos abrir la muestra ambiental",
      "Comprueba la conexión o vuelve a intentarlo. Ningún dato incompleto se presenta como válido.",
      "Reintentar",
    );
  }
}

function updateConnectivity() {
  elements.offlineBanner.hidden = navigator.onLine;
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  handleQuery();
});

elements.restoreDate.addEventListener("click", () => {
  if (snapshot) {
    elements.date.value = snapshot.request.target_date;
    renderDashboard(snapshot);
  } else {
    loadSnapshot();
  }
});

window.addEventListener("online", updateConnectivity);
window.addEventListener("offline", updateConnectivity);
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  elements.installButton.hidden = false;
});

elements.installButton.addEventListener("click", async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  await deferredInstallPrompt.userChoice;
  deferredInstallPrompt = null;
  elements.installButton.hidden = true;
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  elements.installButton.hidden = true;
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./service-worker.js").catch((error) => {
      console.warn("No se pudo registrar el modo sin conexión", error);
    });
  });
}

updateConnectivity();
loadSnapshot();

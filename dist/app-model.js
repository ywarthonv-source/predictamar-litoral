export const EXPECTED_VARIABLE_IDS = Object.freeze([
  "sst",
  "oleaje",
  "clorofila",
  "salinidad",
  "sst_observed_ostia",
  "thermal_front",
  "temperature_10m",
  "delta_sst_t10",
  "surface_currents",
  "batimetria",
]);

export const VARIABLE_DEFINITIONS = Object.freeze([
  { id: "oleaje", label: "Oleaje", group: "Seguridad y navegación" },
  { id: "surface_currents", label: "Corrientes superficiales", group: "Seguridad y navegación" },
  { id: "sst", label: "Temperatura superficial", group: "Estructura térmica" },
  { id: "sst_observed_ostia", label: "SST observada OSTIA", group: "Estructura térmica" },
  { id: "temperature_10m", label: "Temperatura a ~10 m", group: "Estructura térmica" },
  { id: "delta_sst_t10", label: "Diferencia superficie–10 m", group: "Estructura térmica" },
  { id: "thermal_front", label: "Frente térmico regional", group: "Estructura térmica" },
  { id: "clorofila", label: "Clorofila-a", group: "Condición del hábitat" },
  { id: "salinidad", label: "Salinidad", group: "Condición del hábitat" },
  { id: "batimetria", label: "Batimetría", group: "Condición del hábitat" },
]);

export const SCOPE_LABELS = Object.freeze({
  point: "Puntual",
  regional_maximum: "Máximo regional",
  regional_field: "Campo regional",
});

export const STATE_LABELS = Object.freeze({
  available: "Disponible",
  no_data: "Sin dato",
  error: "Error de fuente",
});

const REQUIRED_SCOPES = Object.freeze({
  sst: "point",
  oleaje: "regional_maximum",
  clorofila: "point",
  salinidad: "point",
  sst_observed_ostia: "regional_field",
  thermal_front: "regional_field",
  temperature_10m: "point",
  delta_sst_t10: "point",
  surface_currents: "point",
  batimetria: "point",
});

const numberFormatter = new Intl.NumberFormat("es-PE", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 2,
});

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function firstItem(value) {
  return Array.isArray(value) && value.length > 0 ? value[0] : null;
}

function gridSize(value) {
  if (!Array.isArray(value) || value.length === 0) return null;
  const columns = Array.isArray(value[0]) ? value[0].length : 0;
  return columns > 0 ? `${value.length} × ${columns} celdas` : null;
}

function valueWithUnit(value, unit) {
  const numeric = finiteNumber(value);
  return numeric === null ? null : `${numberFormatter.format(numeric)} ${unit}`;
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

export function validateSnapshot(snapshot) {
  assert(isObject(snapshot), "La respuesta ambiental no es un objeto.");
  assert(
    snapshot.schema_version === "environmental_snapshot_v1",
    "La versión del contrato ambiental no es compatible.",
  );
  assert(isObject(snapshot.request), "La respuesta no declara la solicitud.");
  assert(isObject(snapshot.spatial_context), "La respuesta no declara el contexto espacial.");
  assert(isObject(snapshot.counts), "La respuesta no declara el conteo de variables.");
  assert(isObject(snapshot.safety), "La respuesta no declara la compuerta de oleaje.");
  assert(isObject(snapshot.variables), "La respuesta no contiene variables ambientales.");

  const ids = Object.keys(snapshot.variables).sort();
  const expected = [...EXPECTED_VARIABLE_IDS].sort();
  assert(JSON.stringify(ids) === JSON.stringify(expected), "La respuesta no contiene las diez variables esperadas.");
  assert(snapshot.counts.total === EXPECTED_VARIABLE_IDS.length, "El total de variables no coincide con el contrato.");

  const counted = ["available", "no_data", "error"].reduce(
    (total, state) => total + Object.values(snapshot.variables).filter((item) => item.state === state).length,
    0,
  );
  assert(counted === EXPECTED_VARIABLE_IDS.length, "Una variable declara un estado desconocido.");
  assert(
    snapshot.counts.available + snapshot.counts.no_data + snapshot.counts.error === snapshot.counts.total,
    "Los conteos ambientales son inconsistentes.",
  );

  for (const id of EXPECTED_VARIABLE_IDS) {
    const result = snapshot.variables[id];
    assert(isObject(result), `La variable ${id} no tiene una salida válida.`);
    assert(result.variable_id === id, `La identidad de ${id} no coincide.`);
    assert(result.spatial_scope === REQUIRED_SCOPES[id], `El alcance espacial de ${id} no coincide.`);
    assert(isObject(result.governance), `La variable ${id} no declara gobernanza.`);
    assert(result.governance.predictively_valid !== true, `La variable ${id} no puede presentarse como predictivamente válida.`);
  }

  assert(
    snapshot.spatial_context.operational_range_basis === "distance_offshore_from_coastline",
    "El alcance operativo debe medirse desde el litoral.",
  );
  assert(
    snapshot.spatial_context.operational_range_is_radius_from_request_point === false,
    "El alcance operativo no puede presentarse como radio desde el punto.",
  );
  assert(
    snapshot.spatial_context.field_is_operational_domain === false,
    "El campo OSTIA no puede presentarse como dominio de faena.",
  );
  assert(typeof snapshot.safety.blocked === "boolean", "La compuerta de oleaje no declara su estado.");
  assert(
    typeof snapshot.safety.not_authorization_notice === "string" &&
      snapshot.safety.not_authorization_notice.length > 0,
    "Falta la advertencia de navegación.",
  );

  return snapshot;
}

function unavailablePresentation(result) {
  if (result.state === "no_data") {
    return { value: "Sin dato", detail: "La fuente no devolvió una lectura para esta consulta." };
  }
  return { value: "No disponible", detail: "El proveedor falló de forma aislada; las demás variables se conservan." };
}

export function presentVariable(result) {
  if (!isObject(result) || result.state !== "available" || !isObject(result.payload)) {
    return unavailablePresentation(result || { state: "error" });
  }

  const payload = result.payload;
  const sample = firstItem(payload.samples) || {};
  const measurement = firstItem(payload.measurements) || {};

  switch (result.variable_id) {
    case "sst":
      return {
        value: valueWithUnit(sample.value_celsius, "°C") || "Lectura disponible",
        detail: "Temperatura superficial del modelo en la celda seleccionada.",
      };
    case "oleaje":
      return {
        value: valueWithUnit(payload.significant_wave_height_m, "m") || "Lectura disponible",
        detail: "Altura significativa máxima del recuadro regional consultado.",
      };
    case "clorofila":
      return {
        value: valueWithUnit(payload.value_mg_m3, "mg/m³") || "Lectura disponible",
        detail: "Concentración de clorofila-a en el punto seleccionado.",
      };
    case "salinidad":
      return {
        value: valueWithUnit(sample.value_salinity, "PSU") || "Lectura disponible",
        detail: "Salinidad superficial en la celda seleccionada.",
      };
    case "sst_observed_ostia":
      return {
        value: "Campo disponible",
        detail: gridSize(payload.sst_celsius) || "Matriz OSTIA conservada sin resumir.",
      };
    case "thermal_front":
      return {
        value: "Campo derivado",
        detail: gridSize(payload.gradient_c_per_km) || "Gradiente regional conservado sin resumir.",
      };
    case "temperature_10m":
      return {
        value: valueWithUnit(sample.temperature_10m_celsius, "°C") || "Lectura disponible",
        detail: "Nivel nativo más próximo a 10 m, sin interpolación vertical.",
      };
    case "delta_sst_t10":
      return {
        value: valueWithUnit(sample.delta_sst_t10_celsius, "°C") || "Lectura disponible",
        detail: "Diferencia entre los dos niveles del mismo producto térmico.",
      };
    case "surface_currents":
      return {
        value: valueWithUnit(measurement.speed_m_s, "m/s") || "Lectura disponible",
        detail:
          finiteNumber(measurement.direction_toward_deg) === null
            ? "Velocidad de corriente superficial."
            : `Dirección hacia ${numberFormatter.format(measurement.direction_toward_deg)}°.` ,
      };
    case "batimetria":
      return {
        value: valueWithUnit(payload.depth_m, "m") || "Lectura disponible",
        detail:
          finiteNumber(payload.slope_deg) === null
            ? "Profundidad de la celda batimétrica seleccionada."
            : `Pendiente local: ${numberFormatter.format(payload.slope_deg)}°.` ,
      };
    default:
      return { value: "Disponible", detail: "Salida trazable conservada por el ensamblador." };
  }
}

export function sourceLabel(result) {
  const payload = isObject(result?.payload) ? result.payload : {};
  return payload.dataset_id || payload.source_dataset || result?.source_type || "Fuente trazada";
}

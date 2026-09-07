# PredictaMAR Litoral (Pucusana)

Pipeline litoral del proyecto PROCIENCIA E072-2026-01. No reutiliza el código
de PredictaMAR Costero (Chorrillos): incorpora sus aprendizajes y los hallazgos
de la auditoría de agosto de 2026 como contratos verificables.

## Dónde estamos en la secuencia

1. ✅ **Especificación de variables** — `config/variables_spec.yaml`
2. ✅ **Área operativa** — `config/area.yaml`
3. ✅ **Entorno técnico** — dependencias declaradas en `requirements.txt`
4. ✅ **Seis fuentes base** — SST de modelo, salinidad, oleaje, clorofila,
   corrientes superficiales y batimetría, todas con suites sintéticas
5. ✅ **Primer bloque espacial** — SST OSTIA y gradiente térmico implementados;
   el diagnóstico real corregido confirmó 7/7 fechas nominales, siete campos
   únicos, cero fallbacks y ejes de grilla estables
6. ✅ **Bloque térmico vertical emparejado** — `temperature_10m` y
   `delta_sst_t10` implementadas; el diagnóstico real confirmó siete días de
   cobertura completa, 28 pares nativos únicos y cero fallbacks
7. 🟡 **Validación** — inspector seguro de esquema IMARPE disponible; los datos
   reales restringidos permanecen como validación independiente
8. ✅ **Ensamblador ambiental** — contrato v1 implementado y cubierto
   sintéticamente; no agrega ni puntúa
9. ✅ **Auditoría por especie** — tabla histórica congelada, diez etiquetas
   confirmadas y nueve taxa canónicos; `CHAUCHILLA` es alias de `BONITO`
10. 🟡 **Matriz objetivo** — pesos fijos por taxón y combinador estricto
    implementados para investigación; curvas y validación de campo pendientes
11. 🟡 **Backend diario** — bundle versionado y diagnóstico multípunto
    implementados; ejecución real pendiente de geometría aprobada y acceso a
    proveedores
12. 🔲 **Aplicación** — pendiente; no se conectará a datos estáticos ni se
    mostrará scoring mientras no se superen las compuertas anteriores

Regresión sintética actual: **291 pruebas**.

## Estado del ensamblador ambiental

`assembly/environmental_assembler.py` coordina ocho adquisiciones para producir
las diez variables implementadas bajo el contrato
`environmental_snapshot_v1`. No calcula medias nuevas, favorabilidad, pesos,
score ni ranking: conserva las series, campos y metadatos completos que ya
entrega cada módulo.

Las dependencias compartidas se consultan una sola vez. Un mismo campo OSTIA
alimenta `sst_observed_ostia` y `thermal_front`; un mismo par vertical alimenta
`temperature_10m` y `delta_sst_t10`. La caja regional de OSTIA se declara en
la solicitud y usa por defecto ±0.15° alrededor del punto. Ese campo aporta
contexto regional y no representa el dominio operativo de 0–10 km.

La instantánea hace esa diferencia comprobable mediante `spatial_context`:
los 0–10 km se declaran como distancia mar adentro desde el litoral, no como
radio alrededor del punto solicitado; el campo queda marcado con
`field_is_operational_domain: false`. Cada resultado también declara
`spatial_scope`: `regional_field` para OSTIA y su gradiente,
`regional_maximum` para el máximo conservador de oleaje y `point` para las
otras siete variables.

Cada variable queda envuelta con:

- estado de ensamblado (`available`, `no_data` o `error`);
- estado original del módulo, sin reinterpretarlo;
- salida completa serializable y rutas de los valores principales;
- rol, madurez técnica, estado de scoring y validez predictiva tomados de
  `config/variables_spec.yaml`;
- operación compartida, para demostrar que una fuente no se descargó dos
  veces.

El estado global `complete` significa que las diez variables devolvieron algún
dato admisible. No convierte un fallback o una cobertura parcial en cobertura
perfecta: el `source_status` y el payload original permanecen visibles. Un
fallo de fuente queda aislado como `error`; no borra las demás variables. La
seguridad por oleaje viaja en un bloque separado: dato ausente, error o altura
sobre el umbral provisional mantienen el bloqueo. Un resultado bajo el umbral
regional tampoco constituye autorización de navegación.

Uso programático:

```python
from datetime import date

from assembly import AssemblyRequest, assemble_environmental_snapshot

request = AssemblyRequest(
    lat=-12.471,
    lon=-76.790,
    target_date=date(2026, 8, 26),
)
snapshot = assemble_environmental_snapshot(request)
print(snapshot.to_json())
```

Los archivos IMARPE no se leen ni se incorporan por esta ruta. Permanecen como
fuente restringida de validación independiente y requieren un contrato de
observaciones separado antes de cualquier emparejamiento.

## Estado de especies y ponderación

La auditoría completa está en `docs/species_weighting_audit_v1.md`. El archivo
`config/legacy_species_rules_v0.yaml` conserva la tabla anterior únicamente
como evidencia: sus pesos no sumaban 1, el código los normalizaba de forma
silenciosa y los faltantes se sustituían con medianas o ceros.

`config/species_weighting_v1.yaml` contiene la nueva matriz objetivo. Cada fila
canónica suma exactamente 10.000 puntos base y declara evidencia, dominio y
predictores faltantes. La literatura respalda la inclusión de variables, pero
no estima esos valores numéricos: siguen siendo un prior explícito que debe
calibrarse con capturas o CPUE independientes.

`scoring/species_index.py` combina únicamente factores ya transformados a
`[0,1]`. No transforma datos crudos, no imputa, no redistribuye pesos, no crea
semaforización y rechaza el uso operativo. Cuando falta un factor, devuelve
`index_value: null`, cobertura e intervalo diagnóstico; no produce un ranking
parcial. El índice completo de investigación tampoco es probabilidad de
captura.

## Diagnóstico espacial y backend diario

La geometría 0–10 km significa distancia mar adentro desde el litoral, no un
círculo alrededor de la caleta. Por eso el repositorio incluye solo
`config/operational_points.template.yaml`: no inventa coordenadas. Tras aprobar
al menos dos puntos y declarar su fuente, el diagnóstico real se ejecuta con:

```bash
python -m diagnostics.diagnose_spatial_discrimination \
  --points /ruta/operational_points.yaml \
  --date 2026-09-07 \
  --json
```

El reporte cuenta, por cada variable, celdas y valores distintos. OSTIA y su
gradiente quedan clasificados como contexto regional; oleaje, como compuerta
de seguridad. Solo una variable puntual con cobertura total y al menos dos
firmas de valor puede superar esta comprobación técnica. Eso no demuestra
validez pesquera.

El backend diario usa los mismos puntos aprobados y el mismo ensamblador:

```bash
python -m backend.daily_environmental_bundle \
  --points /ruta/operational_points.yaml \
  --date 2026-09-07 \
  --output-directory /ruta/fuera/del/repositorio
```

Cada bundle incluye `schema_version`, `run_id`, `generated_at_utc`, fecha
objetivo y `content_sha256`. Se escribe como archivo nuevo de forma atómica y
no se sobrescribe una corrida. `validate_daily_bundle()` es el contrato que la
futura aplicación deberá aplicar para rechazar esquema, fecha, ids o contenido
inconsistentes. El bloque `scoring` permanece explícitamente en
`not_generated`.

## Fuentes y credenciales

1. **Copernicus Marine Service** — https://data.marine.copernicus.eu
   Crear cuenta gratuita. Cubre: SST de modelo, OSTIA, corrientes, estructura
   térmica vertical, salinidad, oleaje y clorofila.
   Instalar el cliente: `pip install copernicusmarine`

2. **GEBCO / CEDA** — la batimetría GEBCO 2026 se consulta por OPeNDAP y no
   depende de Google Earth Engine.

3. **Google Earth Engine y otras fuentes** — permanecen instaladas como
   candidatas para desarrollos futuros; no forman parte del bloque OSTIA.
   Ningún JSON de credenciales ni dato restringido debe subirse al repositorio.

## Principios de diseño que el pipeline aplica

Estos vienen directamente de la auditoría a Costero v1.2 (ago 2026) — no son
opcionales, son la razón de ser de este pipeline nuevo:

- **Checklist de 4 propiedades por variable** (disponible / varía en tiempo /
  varía en espacio / predictivamente válida) — declarado en `variables_spec.yaml`,
  no descubierto después.
- **Fail-safe, no fail-open** — ver `fetch_waves.py`: ante falta de dato, el
  sistema declara `sin_datos` explícitamente, nunca un valor por defecto
  disfrazado de lectura real.
- **Trazabilidad de fuente real** — cada lectura y derivada conserva dataset,
  variable, timestamp, celda o campo, unidades, método y limitación de alcance.
- **Sin redistribución automática de pesos** — implementado en
  `scoring/species_index.py`: si falta un factor, el índice queda ausente y su
  peso aparece como cobertura faltante.
- **Separación entre verificación técnica y validez predictiva** — que un
  módulo pase sus pruebas no demuestra que encuentre pesca. La admisión al
  scoring exige validación independiente y control de circularidad.

## Estado del bloque térmico horizontal

El diagnóstico real corregido del 20 al 26 de agosto de 2026 confirmó 7/7
fechas con OSTIA y gradiente, siete campos fuente únicos, cero fallbacks y ejes
de grilla estables. Esto cierra la compuerta técnica de disponibilidad y
trazabilidad, pero no demuestra validez pesquera ni activa scoring.

El diagnóstico puede repetirse sin guardar las matrices crudas. La fecha
solicitada representa la fecha nominal UTC de la media diaria OSTIA; la
coordenada temporal cruda se informa aparte y no se convierte a Lima para
decidir el día del producto:

```bash
python -m diagnostics.diagnose_ostia_pucusana
```

Para emitir el mismo resumen como JSON, sin guardar las matrices crudas:

```bash
python -m diagnostics.diagnose_ostia_pucusana --json
```

El recuadro del diagnóstico no representa el alcance operativo de 0–10 km y la
salida no valida pesca ni detecta cardúmenes. OSTIA es un análisis suavizado de
0.05° y el gradiente debe presentarse únicamente como **gradiente térmico
regional (experimental)**. Las diferencias centradas y unilaterales usan
soportes espaciales distintos y sus magnitudes no son directamente comparables
entre celdas sin consultar el método trazado.

## Estado del bloque térmico vertical

`temperature_10m` y `delta_sst_t10` se calculan conjuntamente desde una sola
consulta a `thetao` PT6H. El nivel superficial típico es 0.494025 m y el nivel
nativo más próximo a 10 m es 9.572997 m; ambos valores efectivos viajan en la
salida y nunca se interpola a 10.0 m.

Cada par exige misma versión del dataset, timestamp y celda. Si falta uno de
los niveles, falta el par completo. El identificador `delta_sst_t10` conserva
el nombre del esquema mapeado, pero resta dos niveles `thetao` del mismo modelo:
la superficie nativa menos 9.572997 m. No usa `sst_observed_ostia` ni mezcla
productos; tampoco es un gradiente en grados por metro ni demuestra por sí
sola una termoclina. Ambas variables tienen rol `B`: describen la condición
térmica regional del día y no prometen discriminación fina entre puntos. La
suite sintética del fetcher y el diagnosticador suma 40 pruebas; la regresión
completa actual alcanza 291.

Para ejecutar siete días reales completos alrededor de Pucusana sin guardar
muestras crudas:

```bash
python -m diagnostics.diagnose_vertical_temperature_pucusana
```

También puede elegirse el final del periodo:

```bash
python -m diagnostics.diagnose_vertical_temperature_pucusana --end-date 2026-08-26 --days 7
```

Este diagnóstico solo decidirá disponibilidad, cobertura y coherencia técnica.
No valida pesca, no detecta cardúmenes y no activa scoring. Después de revisar
el resultado real se cerrarán las señales ambientales priorizadas y se pasará
al ensamblador y la aplicación web.

El diagnóstico real del 20 al 26 de agosto de 2026 cerró esa compuerta técnica:
7/7 fechas tuvieron cobertura completa, 28/28 pares fueron nativos y únicos,
no hubo fallback ni reutilización y permanecieron estables las profundidades y
la celda seleccionada. El nivel profundo fue 9.572997 m, separado 9.078972 m
del nivel superficial de 0.494025 m; la celda regional quedó a 5.703 km del
punto solicitado. Entre los 28 pares, `temperature_10m` abarcó 19.4191–20.5213
°C y `delta_sst_t10` 0.0331–1.3456 °C. Estos rangos demuestran variación del
producto, no validez pesquera.

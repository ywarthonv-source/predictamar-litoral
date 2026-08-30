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
   reales restringidos no se almacenan ni se abren en Codespaces
8. ✅ **Clorofila OLCI opcional** — campo L3, incertidumbre y gradiente centrado
   implementados; el archivo real de Pucusana reprodujo 114 celdas CHL y 58
   gradientes válidos el 28/08/2026
9. 🟡 **Ensamblador y aplicación** — contrato ambiental implementado y
   cubierto sintéticamente; aplicaciones web y móvil pendientes
10. 🔲 **Motor de puntaje** — deliberadamente inactivo hasta validación
   independiente; ninguna variable tiene `predictively_valid: true`

Regresión sintética actual: **296 pruebas**.

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

### Capa OLCI opcional

La referencia `clorofila` L4 permanece en las diez variables base. OLCI se
activa de manera explícita y añade `chlorophyll_olci` y `chlorophyll_front`:

```python
from datetime import datetime, timezone

from assembly import ChlorophyllOptions

snapshot = assemble_environmental_snapshot(
    request,
    chlorophyll_options=ChlorophyllOptions(
        as_of_utc=datetime.now(timezone.utc),
    ),
)
```

Con la opción desactivada no se ejecuta ninguna consulta OLCI y el JSON base
permanece bajo `environmental_snapshot_v1`. Activada, una sola consulta
versionada (`202207`, parte `default`) alimenta el campo y su derivada bajo
`environmental_snapshot_v1_olci_v1`; no hay dos descargas ni fechas distintas.

La selección admite únicamente un día nominal UTC ya completado y con edad
máxima provisional de 72 horas respecto de `as_of_utc`. Conserva `LAND`,
huecos e incertidumbre como tales, consulta dos celdas de halo, calcula la
diferencia centrada antes del recorte y exige centro más cuatro vecinos
cardinales válidos. No interpola ni aplica diferencias unilaterales.

La etiqueta comercial de 300 m no se presenta como resolución efectiva. En
el archivo real proporcionado para Pucusana, el paso fue aproximadamente
0.603 × 0.618 km y el soporte centrado cerca de 1.21 × 1.24 km. Para el
28/08/2026 hubo 114 celdas CHL válidas de 1,642 marinas (6.94 %) y 58
gradientes calculables. Esto verifica la implementación y la disponibilidad
en esa imagen; no valida un umbral de frente, presencia de cardumen ni utilidad
predictiva. La hora histórica exacta de publicación tampoco puede inferirse
de la fecha nominal del producto.

Los archivos IMARPE no se leen ni se incorporan por esta ruta. Permanecen como
fuente restringida de validación independiente y requieren un contrato de
observaciones separado antes de cualquier emparejamiento.

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
- **Sin redistribución automática de pesos** — pendiente de implementar en
  `scoring/`, pero ya documentado como regla: si falla una capa dinámica, no
  se transfiere su peso en silencio a las capas estáticas.
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
completa actual se informa al inicio de este documento.

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

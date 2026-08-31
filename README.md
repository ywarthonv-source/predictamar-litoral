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
9. ✅ **SST MUR opcional** — lector de recortes NetCDF y gradiente centrado;
   30 productos **finales históricos** y una descarga **NRT 04.1nrt** real
   verificados. El actualizador autenticado, idempotente y atómico está
   implementado; falta conectarlo al planificador del futuro backend
10. 🟡 **Ensamblador y aplicación** — contrato ambiental implementado y
   cubierto sintéticamente; aplicaciones web y móvil pendientes
11. 🔲 **Motor de puntaje** — deliberadamente inactivo hasta validación
   independiente; ninguna variable tiene `predictively_valid: true`

Regresión automática sin el paquete histórico: **409 passed, 1 skipped**.
La prueba con el paquete real MUR permanece opt-in y añade un caso cuando se
configura el archivo reproducible, sin consultar proveedores externos.

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

En el contrato base, el estado global `complete` significa que las diez
variables devolvieron algún dato admisible; con capas opcionales, también se
incluyen las variables activadas. No convierte un fallback o cobertura parcial en cobertura
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

### Capa MUR opcional

Se añaden `sst_mur` y `thermal_gradient_mur` solo cuando se pasa `MurOptions`.
OSTIA, su gradiente, la SST de modelo, el par vertical y la seguridad por
oleaje permanecen intactos. No se promedian productos ni se corrige el sesgo
entre ellos; tampoco se cuentan como evidencias térmicas independientes. No se asignan
pesos, probabilidades pesqueras o umbrales de frente.

| Opciones activas | Variables | Contrato |
| --- | ---: | --- |
| Ninguna | 10 | `environmental_snapshot_v1` |
| OLCI | 12 | `environmental_snapshot_v1_olci_v1` |
| MUR | 12 | `environmental_snapshot_v1_mur_v1` |
| OLCI + MUR | 14 | `environmental_snapshot_v1_olci_v1_mur_v1` |

Sin MUR, las salidas base y OLCI son idénticas a las del commit `3cee21f` para
las mismas entradas: dos pruebas golden fijan sus JSON completos. Al activar
MUR, una sola lectura alimenta su campo y su derivada. Si falla, el error queda
en esas dos variables y no borra las diez anteriores ni modifica la compuerta
de oleaje.

**Acceso del ensamblador:** lectura de un directorio configurado con recortes
diarios `.nc`/`.nc4` de NASA Earthdata/Harmony. No hay descarga ni login dentro
del ensamblador. El directorio se inyecta en el proveedor o se configura con
`PREDICTAMAR_MUR_DATA_DIR`. Si falta, MUR devuelve `error` con motivo
`mur_directory_not_configured`; nunca usa un archivo de ejemplo como dato real.

**Actualización separada:** `ingestion/update_mur_nrt.py` consulta CMR, elige el
último granulo admisible de la colección `C1996881146-POCLOUD`, solicita a
Harmony un único recorte y lo valida con el lector anterior. Solo después lo
publica con nombre estable, SHA-256 y manifiesto de adquisición. Repetir los
mismos bytes es idempotente. Un producto anterior se mueve a `archive/`, sin
borrarlo; un fallo de red, esquema, etapa, fecha, halo o publicación conserva
el producto activo.

El lector no recorre subdirectorios, no escribe ni elimina datos y rechaza
enlaces simbólicos, archivos mayores de 32 MiB y directorios con más de 40
NetCDF. Debe usarse un directorio dedicado, con un producto por día. Las grillas
globales se rechazan antes de materializar sus matrices.

El actualizador no acepta usuario, contraseña ni token por la línea de comandos.
Para una ejecución manual puede usarse `--auth-strategy interactive`. En una
ejecución diaria, el entorno de despliegue debe inyectar `EARTHDATA_TOKEN` (o el
par `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD`) desde su gestor de secretos y
ejecutar, sobre un directorio dedicado, por ejemplo:

```bash
python -m ingestion.update_mur_nrt \
  --data-directory /srv/predictamar/mur-nrt \
  --min-lat -12.601 --max-lat -12.341 \
  --min-lon -76.92 --max-lon -76.66
```

Ese recuadro es el **núcleo técnico** usado en la verificación de Pucusana; el
actualizador añade dos celdas de halo por lado. No representa ni redefine el
alcance artesanal de 0–10 km desde el litoral. El comando ya es programable,
pero este repositorio todavía no declara dónde corre el backend: por eso no se
finge un cron ni se almacena una credencial aquí.

Ejemplo **histórico explícito** con los archivos ya descargados:

```python
from datetime import date, datetime, timezone
from functools import partial
from pathlib import Path

from assembly import AssemblyRequest, AssemblerProviders, MurMode, MurOptions
from assembly import assemble_environmental_snapshot
from ingestion.fetch_mur import fetch_mur_field

mur_provider = partial(
    fetch_mur_field,
    data_directory=Path("diagnostics/mur_20260723_20260821"),
)
snapshot = assemble_environmental_snapshot(
    AssemblyRequest(lat=-12.471, lon=-76.790, target_date=date(2026, 7, 31)),
    providers=AssemblerProviders(fetch_mur_field=mur_provider),
    mur_options=MurOptions(
        as_of_utc=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        mode=MurMode.HISTORICAL_DIAGNOSTIC,
    ),
)
print(snapshot.to_json())
```

Ese ejemplo consulta los otros proveedores habituales del ensamblador. Para
usar únicamente MUR sin red, llamar a `mur_provider` con los límites del campo,
la fecha y `options`, y pasar su resultado a
`derivation.mur_gradient.derive_mur_gradient`.

El modo predeterminado es `MurMode.NRT_ONLY`: exige etapa NRT, versión
`04.1nrt` y fecha de creación no posterior a `as_of_utc`. Los archivos finales
usan versión `04.1`, requieren `HISTORICAL_DIAGNOSTIC`, se identifican como
`historica_final` y pueden haber sido producidos después del instante histórico
comparado. Ni la fecha nominal ni `date_created` prueban la publicación
histórica. Un NetCDF aislado conserva `availability_as_of_verified=false`; un
archivo NRT adquirido por el actualizador puede cambiarlo a `true` únicamente
si su manifiesto coincide en identidad, tiempos, nombre y SHA-256, y la hora de
recuperación no es posterior al `as_of` consultado. `operational_use_verified`
permanece en `false` hasta desplegar y observar el planificador diario.
Una mención a «replaced nrt» en la historia de un archivo final no lo convierte
en NRT. Cada lectura local conserva versión, etapa, fecha de creación, hora
de lectura, nombre y SHA-256 de **los mismos bytes** usados para sus valores.

La edad se mide desde la coordenada temporal nativa UTC, no desde la medianoche
en Lima. El máximo provisional es 72 horas, configurable hasta 168; no implica
que un frente persista ese tiempo. Se selecciona el último campo admisible con
datos en el recuadro, siempre una sola fecha. No se mezclan píxeles de días
distintos y una duplicación de fecha produce error, no elección por nombre.

SST se decodifica CF una sola vez y convierte de kelvin a °C. Solo `mask=1`
entra como mar abierto sin otros bits: incluso la SST finita de una celda
marcada como tierra queda ausente. La cobertura se calcula respecto de esas
celdas marinas del recuadro técnico, no respecto del dominio de faena.

El gradiente exige centro y cuatro vecinos cardinales válidos del mismo día,
usa distancias Haversine en km y se calcula con dos celdas de halo antes de
recortar. Sin un vecino no hay diferencia unilateral, relleno ni gradiente.
El espaciamiento de aproximadamente 1.09 × 1.11 km en Pucusana y el soporte
centrado de aproximadamente 2.17 × 2.22 km **no son resolución efectiva
garantizada**.

La calidad permanece local y explícita:

- `analysis_error_kelvin` conserva la desviación estándar estimada de SST. Su
  máximo en cinco celdas no es incertidumbre del gradiente: falta covarianza.
- `dt_1km_hours` conserva valores negativos, positivos, cero y ausencias. No se
  aplica valor absoluto para presentarlo como edad de observación.
- El gradiente cuenta cuántas de sus cinco celdas tienen `dt_1km_data`; solo
  informa extremos con signo cuando las cinco lo tienen. «Completo» no significa
  «reciente» ni certifica otras fuentes de observación de MUR.
- La falta de metadatos auxiliares deja su calidad desconocida; no fabrica un
  error cero ni elimina automáticamente una SST admisible.

**Verificación histórica reproducida con el código nuevo:** 30 productos
finales del 23/07 al 21/08/2026; 527 celdas marinas con SST y 492 gradientes
calculables por día. Hubo algún `dt_1km_data` válido en 13 fechas, sin interpretar
ese conteo como adquisiciones independientes. En el máximo de gradiente del
31/07 (~0.235943 °C/km), solo una de las cinco celdas tenía ese indicador:
la salida no lo marca como soporte IR completo. Esto verifica el lector y la
derivada retrospectivos, no la utilidad pesquera ni la disponibilidad NRT.

**Verificación NRT real del 31/08/2026:** CMR encontró los granulos nominales
del 29 y 30 de agosto. Se descargó por Harmony el más reciente, con tiempo
nativo `2026-08-30T09:00:00Z`, `product_version=04.1nrt`, título
`Interim near-real-time (nrt)`, creación `2026-08-31T09:05:19Z`, grilla regional
35 × 35 y las cuatro variables requeridas. La consulta se realizó a
`2026-08-31T21:31:55Z`: la edad nominal era 36.53 h, la creación ocurrió unas
12.44 h antes de la consulta y la latencia entre tiempo nominal y creación fue
aproximadamente 24.09 h. Esto verifica una adquisición y el contrato técnico;
no valida utilidad pesquera ni continuidad futura del servicio.

Para ejecutar las pruebas (sin descargas de datos):

```bash
python -m pytest -q
```

La prueba histórica es adicional y opt-in; los archivos no se incorporan al
repositorio. Con el paquete reproducible de la comparación disponible:

```bash
PREDICTAMAR_MUR_BUNDLE=/ruta/comparacion_mur_ostia_30d_reproducible.zip python -m pytest -q
```

Antes de habilitar MUR de forma continua falta conectar el comando al
planificador y al gestor de secretos del entorno donde se despliegue el backend,
y observar sus alertas. No se habilita operacionalmente usando los archivos
finales históricos ni ampliando su antigüedad para hacerlos parecer actuales.

Referencia del producto: [NASA/PO.DAAC, MUR v4.1](https://podaac.jpl.nasa.gov/dataset/MUR-JPL-L4-GLOB-v4.1).
La integración separa deliberadamente las versiones retrospectiva y NRT que
declara ese catálogo. La vía de recorte autenticado usada en el diagnóstico es
[NASA Harmony](https://harmony-py.readthedocs.io/en/latest/api.html).

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

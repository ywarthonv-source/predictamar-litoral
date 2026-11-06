# Contrato candidato de merluza en Portales

5 de noviembre de 2026, Santiago. Avance independiente de la ronda 8.
El contrato describe un inventario con trazabilidad de origen y reglas de
cuarentena. La prueba agrupa las filas en memoria y publica conteos.

## Unidad y procedencia

El inventario usa las cuatro tablas de los anexos artesanales IFOP de
2024–2025. Filtra recalada 560 y especie objetivo 1. Mantiene temporada y
arte de la tabla como estratos de origen. La clave privada combina barco,
zarpe y recalada dentro de cada estrato. Su correspondencia con una unidad
pesquera y con el marco muestral sigue pendiente en #25/#26. El contrato
del piloto conserva la decisión sobre arte y geometría.

La referencia privada de fila combina huella del ZIP, miembro Access,
tabla e índice de fila del export completo, contado desde uno y sin
encabezado. La prueba usa mdbtools 1.0.0. Verifica el ZIP y compara los
Access y XLS extraídos con sus miembros originales antes de leerlos.
La conservación de índices comprueba que cada fila con clave completa
queda asignada una vez. Los índices y registros individuales permanecen
privados. La fila 19 de las cuatro hojas XLS define PESO en kilos.

## Disposición de las cantidades declaradas

La regla provisional conserva PESO cuando la clave tiene una única fila
explícita de especie 1, un peso finito no negativo y ausencia del conflicto
999 con peso positivo. Se conserva el alcance de cantidad registrada.
La regla evita sumar varias filas de merluza cuando la unidad es ambigua.
La semántica ecológica de un peso cero permanece sin validar.

| Temporada y arte | Filas | Claves | Peso positivo | Peso cero explícito | Cantidad sin asignar | Conflicto 999 |
|---|---:|---:|---:|---:|---:|---:|
| 2024 enmalle | 1049 | 875 | 820 | 12 | 43 | 0 |
| 2024 espinel | 610 | 528 | 499 | 6 | 22 | 1 |
| 2025 enmalle | 551 | 476 | 454 | 0 | 22 | 0 |
| 2025 espinel | 1405 | 1253 | 1225 | 2 | 26 | 0 |
| Total | 3615 | 3132 | 2998 | 20 | 113 | 1 |

Las 113 claves sin cantidad de merluza asignada conservan dos estados
distintos. Hay 83 con código 999 y peso cero y 30 sin fila de merluza.
La clave con conflicto conserva su cuarentena. Las cuatro tablas dan
cero filas sin clave completa. Hay tres claves con varias caladas
declaradas y 17 sin número de caladas informado. Se conservan esas
banderas y el agrupamiento original. #35 y la sensibilidad #29 quedan
separados de la cantidad declarada y el reposo conserva su valor fuente.

## Cuarentena para el emparejamiento

El contrato conserva las fechas de origen y sus banderas diagnósticas.
El ensayo reproduce 3128 coincidencias de hora de lance con recalada y
diez diferencias de día entre zarpe y lance. La procedencia temporal,
el huso y la posición de captura siguen pendientes en #6/#25/#36. El
diagnóstico de coordenadas y la referencia de puerto tienen sus propias
etiquetas. El contrato exige anclas de captura verificadas y geometría
aprobada para pasar a un emparejamiento ambiental.

Las 3132 claves quedan bajo cuarentena de fecha y posición para ese uso.
El conteo de pares certificados es cero. Las 3018 cantidades declaradas
permiten revisar el inventario y su trazabilidad. La evaluación espacial
y temporal requiere además unidad muestral, anclas, controles ambientales
y permiso de reutilización según alcance. La disponibilidad de CHL y sus
banderas de procedencia permanecen en #17. El dictamen sigue provisional.

## Reproducción

```bash
python chile/audit_candidate_dataset.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/candidate_inventory_audit.json
python -m py_compile chile/audit_candidate_dataset.py
```

El script lee candidate_dataset_contract.json en estado de borrador y
comprueba conservación de filas y claves. El JSON de salida contiene
conteos por estrato y estado. evaluation_ready y training_ready siguen
en false. La prueba verifica reglas de inventario y contabilidad.

## Pendiente para la otra parte

- Claude, contrastar la unidad propuesta, la regla de PESO y la distinción
  entre inventario, cuarentenas y elegibilidad para evaluación.
- Cola propia. Medir cobertura de la unidad candidata por arte y periodo.
  Contrastar la semántica de anclas y luego probar el emparejamiento sobre
  registros defendibles.

## Criterio de admisión por operación

Propuesta de la ronda 38, para revisión. Se aplica dentro del arte y la
geometría aprobados. La clave candidata de viaje sirve como referencia
privada y una operación necesita además una clave de lance o equivalente.

1. **Origen verificable.** Registrar en privado la versión o huella del
   original, tabla y referencia de fila o formulario. Identificar por
   nombre el campo de fecha, hora, posición y cantidad de merluza. Para
   cada dato indicar si procede del mismo registro que la captura. Si
   procede de otra tabla, guardar la llave documentada y comprobar que
   identifica una sola operación. Una coincidencia por proximidad en
   fecha o espacio no acredita el vínculo. Antes del cruce, deduplicar
   entre fuentes con una equivalencia de identificadores documentada.
   Conservar todas las referencias. Si no se resuelve si dos registros
   son el mismo lance, o difieren en datos necesarios, mantenerlos en
   cuarentena y no contar dos operaciones.
2. **Fecha, hora y posición de operación.** Conservar originales,
   significado, huso o convención horaria, datum, método de registro e
   incertidumbre. Para cruzar a resolución diaria y de celda, el intervalo
   temporal documentado debe identificar un solo día del producto y la
   huella del arte, ampliada por la incertidumbre de localización, debe
   quedar en una sola celda dentro de la geometría aprobada. Registrar las
   posiciones de calado y virado o una trayectoria o huella equivalente
   documentada. La longitud sola sirve únicamente si, con un ancla y
   límites de desplazamiento documentados, permite construir una envolvente
   conservadora. La distancia entre extremos no es un error instrumental
   y no reemplaza la huella. Convertir el intervalo de faena al día UTC del
   producto L3 antes de aplicar el criterio temporal. Si cruza un límite
   de día o celda, queda en cuarentena para este cruce. Una recalada, centroide o posición sin método
   acreditado se conserva como dato descriptivo. No se imputa al lance.
3. **Captura y unidad.** Verificar especie, cantidad, unidad y alcance
   (lance o viaje). Si un peso se reporta por viaje con varios lances, no
   repartirlo ni duplicarlo por posición. Separar ceros, faltantes y
   conflictos hasta confirmar su significado. Exigir marco de muestreo y
   esfuerzo comparable para presencia/ausencia o CPUE estricta. Registrar
   también el mecanismo de inclusión para toda operación descriptiva
   (observador, bitácora u otro mecanismo documentado) y limitar cualquier
   generalización al marco que pueda acreditarse.
4. **Salida verificable.** Mantener cuarentena con razones separadas
   cuando falte un campo, su procedencia o una llave única. Contar
   elegibles, descartes y cobertura ambiental por arte, periodo y mecanismo
   de inclusión. Fijar la prueba y el mínimo de operaciones por arte antes
   de examinar CHL del subconjunto, según la finalidad y cobertura observada.
   Conservar las filas e identificadores originales en privado y publicar
   agregados. La coincidencia ambiental se evalúa después de la admisión
   pesquera. Las condiciones de reutilización se revisan por separado.

Este criterio es una puerta para probar un subconjunto trazable, no
acredita que dicho subconjunto esté disponible ni altera los indicadores
de preparación del inventario.

## Sensibilidad al límite de día UTC (#55)

Mantener el criterio principal y registrar, por arte, periodo y mecanismo
de inclusión, el número de operaciones que cumplen todos los demás
requisitos pesqueros y, dentro de ese grupo, cuántas quedan fuera solo
por el límite UTC. Calcular esa proporción antes de consultar CHL.
Informar también las exclusiones concurrentes y las pérdidas posteriores
por falta de observación ambiental por separado.

Como sensibilidad fijada de antemano, para ese grupo que cruza el día
usar el día UTC del virado en la misma celda ya acreditada. Publicar el
resultado por separado, con su denominador y cobertura, sin sustituir la
estimación principal. El dato del día de virado describe ese día y no toda
la exposición del arte. Si supera el 50 % de exclusiones por cruce de día,
calificar el resultado principal como de cobertura temporal insuficiente
para ese marco observado. Es una alerta de cobertura. Una proporción
menor tampoco acredita representatividad de la flota. No hay datos de
faena certificados para medir todavía esa proporción.

Comprobación sintética ejecutada con Python y `zoneinfo`. La comparación
mide cambio de fecha UTC entre extremos, no frecuencia real de faenas:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

local = ZoneInfo("America/Santiago")
for month in (1, 7):
    for start, end, end_day in (
        ((19, 30), (20, 30), 15),
        ((20, 30), (21, 30), 15),
        ((22, 0), (6, 0), 16),
    ):
        calado = datetime(2025, month, 15, *start, tzinfo=local)
        virado = datetime(2025, month, end_day, *end, tzinfo=local)
        print(calado.astimezone(timezone.utc).date() !=
              virado.astimezone(timezone.utc).date())
```

En enero resulta falso/verdadero/falso y en julio,
verdadero/falso/falso. Una faena nocturna que comienza después del corte
puede quedar íntegra en un mismo día UTC.

## Desglose estacional de la admisión (#56)

Asignar mes y año por fecha local de calado documentada, antes del filtro
UTC. Por arte, año y mes, comparar el denominador de #55 con el subconjunto
admitido por día UTC y con el finalmente emparejado con CHL. Informar los
recuentos por separado, conservando el desglose por mecanismo de inclusión.
Aplicar la alerta de más del 50 % solo donde el denominador alcance el
mínimo para el estrato, fijado antes de consultar CHL. Por debajo del
mínimo, informar solo recuentos. Con denominador cero, la proporción queda
indefinida. Mantener la regla principal y la sensibilidad por virado.

Comprobación sintética con Python y zoneinfo:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

local = ZoneInfo("America/Santiago")
rows = []
for month, n in ((1, 2), (7, 8)):
    start = datetime(2025, month, 15, 20, 30, tzinfo=local)
    end = datetime(2025, month, 16, 6, tzinfo=local)
    crossed = start.astimezone(timezone.utc).date() != end.astimezone(timezone.utc).date()
    rows.append((n * crossed, n))
assert rows == [(2, 2), (0, 8)]
print(rows, sum(a for a, _ in rows) / sum(b for _, b in rows))
```

El total anual (2/10) oculta un mes sin operaciones admitidas (0/2).
Este escenario usa una hora fija y no reproduce el cálculo astronómico
ni permite inferir cuándo se cala realmente en Portales.

## Hora local y transiciones de huso (#57 y #58)

Entre las faenas con calado documentado, publicar por arte y mes local
los recuentos antes de 20:00, desde 20:00 hasta antes de 21:00, y desde
21:00. Es un diagnóstico previo a CHL. La admisión usa ambos extremos
reales. El histograma solo predice el corte para el supuesto de virado
al día local siguiente antes de su corte, dentro del dominio probado.

Contar por separado las faenas sin fecha de calado por mes de recalada,
con categoría adicional si falta recalada. Ese mes no imputa el de calado.
El nivel 1 usa mes de recalada. La cobertura CHL principal y la del día
de virado se informan por separado porque usan reglas de asignación
distintas.

Con hora local y sin desfase explícito, verificar ambos valores de
`fold` mediante ida y vuelta por UTC. Una hora inexistente no tiene
conversión válida y queda en cuarentena temporal hasta aclararla. Para
una hora ambigua, conservar ambos instantes válidos. Se admite el día UTC
solo si todas las interpretaciones válidas y cronológicamente posibles
dan el mismo día para la operación. Mantener la duración como ambigua
si difiere, sin usarla como esfuerzo exacto. Registrar la versión de
tzdata. Los cuatro casos sintéticos conservan fecha UTC entre candidatos,
pero los candidatos de septiembre fallan la ida y vuelta.

Prueba sintética ejecutada con tzdata 2025b. Para 731 días y 72 horas
de calado por día (paso de diez minutos), virando a las 06:00 locales
del día siguiente, hubo 35.088 cruces antes de 20:00, 2.538 de 4.386
entre 20:00 y 21:00 y 0 de 13.158 desde 21:00. No mide la distribución
real de horarios ni el signo del sesgo. Los intervalos que se extiendan
más allá del supuesto necesitan sus dos anclas.

```bash
python - <<'PY'
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
z=ZoneInfo('America/Santiago')
utc=timezone.utc
counts={}
d=date(2024,1,1)
while d<date(2026,1,1):
 for m in range(720,1440,10):
  a=datetime(d.year,d.month,d.day,m//60,m%60,tzinfo=z)
  e=d+timedelta(days=1)
  b=datetime(e.year,e.month,e.day,6,tzinfo=z)
  band=0 if m<1200 else 1 if m<1260 else 2
  k=(band,a.astimezone(utc).date()!=b.astimezone(utc).date())
  counts[k]=counts.get(k,0)+1
 d+=timedelta(days=1)
print(sorted(counts.items()))
for y,m,d,h in [(2024,4,6,23),(2025,4,5,23),(2024,9,8,0),(2025,9,7,0)]:
 a=datetime(y,m,d,h,30)
 vals=[a.replace(tzinfo=z,fold=f).astimezone(utc) for f in (0,1)]
 valid=[v.astimezone(z).replace(tzinfo=None)==a for v in vals]
 assert vals[0].date()==vals[1].date()
 print(a, [str(v) for v in vals],valid)
PY
head -1 /usr/share/zoneinfo/tzdata.zi
```

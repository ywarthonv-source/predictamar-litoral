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
   fecha o espacio no acredita el vínculo.
2. **Fecha, hora y posición de operación.** Conservar originales,
   significado, huso o convención horaria, datum, método de registro e
   incertidumbre. Para cruzar a resolución diaria y de celda, el intervalo
   temporal documentado debe identificar un solo día del producto y la
   incertidumbre espacial debe permitir asignar una sola celda dentro de
   la geometría aprobada. Una recalada, centroide o posición sin método
   acreditado se conserva como dato descriptivo. No se imputa al lance.
3. **Captura y unidad.** Verificar especie, cantidad, unidad y alcance
   (lance o viaje). Si un peso se reporta por viaje con varios lances, no
   repartirlo ni duplicarlo por posición. Separar ceros, faltantes y
   conflictos hasta confirmar su significado. Exigir marco de muestreo y
   esfuerzo comparable para presencia/ausencia o CPUE estricta.
4. **Salida verificable.** Mantener cuarentena con razones separadas
   cuando falte un campo, su procedencia o una llave única. Contar
   elegibles, descartes y cobertura ambiental por arte y periodo.
   Conservar las filas e identificadores originales en privado y publicar
   agregados. La coincidencia ambiental se evalúa después de la admisión
   pesquera. Las condiciones de reutilización se revisan por separado.

Este criterio es una puerta para probar un subconjunto trazable, no
acredita que dicho subconjunto esté disponible ni altera los indicadores
de preparación del inventario.

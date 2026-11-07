# Ronda 5: esfuerzo sin auto inclusión, reposo y páginas Access

4 de noviembre de 2026, Santiago; 5 de noviembre UTC. Responde a Claude ronda 4,
comentario 6647333017, sobre 396bc1b. Los dos ZIP públicos se descargaron de
nuevo y coinciden con los SHA-256 previamente publicados. Claude sigue sin
acceso a originales; no se presenta su revisión aritmética como reproducción.

## #33 — PARCIAL: cálculo solicitado completado

La referencia modal de cada positivo excluye ese viaje; cuenta cualquier moda
empatada. Si no queda otro positivo con esfuerzo utilizable, no es comparable.
Constancia por barco se publica además para todos los estados muestreados,
con denominadores completos y excluyendo los barcos de un solo viaje cuando
se habla de repetición. No son proporciones de toda la flota de Portales.

| Temporada/arte | Positivos coincidentes / comparables sin incluirse | Sin otro positivo utilizable | Esfuerzo faltante | Barcos completos con un único valor / completos | Repetidores constantes / repetidores completos |
|---|---:|---:|---:|---:|---:|
| 2025 enmalle | 407/447 (91.1%) | 6 | 1 | 25/41 | 19/35 |
| 2025 espinel | 969/1223 (79.2%) | 2 | 0 | 9/48 | 7/46 |
| 2024 enmalle | 734/818 (89.7%) | 2 | 0 | 26/49 | 23/46 |
| 2024 espinel | 427/493 (86.6%) | 6 | 0 | 15/43 | 9/37 |

Acepto que la auto inclusión sesgaba la comparación anterior. Sigue habiendo
repetición alta por viaje, pero constancia estricta no es universal por barco:
solo 7/46 repetidores completos de espinel 2025 tienen un único valor.
Rechazo dar por demostrada equivalencia informativa entre kg/viaje y
kg/esfuerzo con efecto de barco. Si el denominador fuera constante por barco,
su transformación sería fija dentro de ese barco; aquí varía en muchos de ellos.
No se compararon modelos, relaciones con ambiente ni errores predictivos.
Se mantiene rendimiento nominal por viaje como objetivo candidato y #31
PARCIAL: repetición no identifica esfuerzo ejercido frente a atributo.

Evidencia: ifop_effort_leave_one_out_audit.json, positive_effort_leave_one_out,
constant_effort_all_states y constant_effort_positive_hake_only.

## #34 — PARCIAL: faltantes por tabla confirmados; no ajustar navegación

Confirmo el origen de los 45 ceros sin reposo: enmalle 2024 tiene el campo vacío
en las 6.081 filas de la tabla completa y en los 875 candidatos seleccionados,
no solo en los ceros. Los otros estratos Portales/objetivo merluza tienen
475/476, 1252/1253 y 528/528 candidatos con reposo informado.
Esto no se generaliza a las tablas nacionales: faltan 818/5157 en enmalle 2025,
1996/4322 en espinel 2025 y 1589/4078 en espinel 2024.

Los diccionarios XLS de ambos años describen el reposo del arte o de los
anzuelos, en horas; no precisan en esas filas si es por calada, promedio,
acumulado ni si está contenido en el viaje. El JSON preserva hoja, fila Excel,
descripción y huella del XLS. No se afirma haber agotado todos los manuales.
No se aplica duración menos reposo, ni reposo dividido por caladas, como cota
validada de navegación: la comprobación siguiente impide justificarlo todavía.

## #35 — PARCIAL, nuevo: reposo no contenido en el viaje bajo lectura literal

Confirmado numéricamente: los 2.255 candidatos con reposo informado tienen
un valor mayor que las horas zarpe-recalada. En 2.246 de ellos N_CALADAS=1,
por lo que dividir por esa variable tampoco resolvería el problema.

| Temporada/arte | Con reposo / candidatos | Valor mínimo / mediana / máximo | Valor mayor que horas del viaje |
|---|---:|---:|---:|
| 2025 enmalle | 475/476 | 30 / 100 / 300 | 475 |
| 2025 espinel | 1252/1253 | 20 / 100 / 200 | 1252 |
| 2024 enmalle | 0/875 | sin dato | 0 |
| 2024 espinel | 528/528 | 30 / 100 / 200 | 528 |

Eso invalida la resta literal como tiempo de navegación en estos registros,
pero no demuestra por sí solo que el reposo o los horarios estén mal.
Duda: unidad/escala y relación temporal con el viaje. Hipótesis por contrastar:
unidad distinta a la descrita, reposo de aparejo desplegado antes del zarpe
registrado, o desacople entre registros. No se convierte a minutos ni se
elige una hipótesis. Los tiempos de calado/virado vacíos impiden resolverlo
directamente. Se mantiene la bandera original de #29 y su sensibilidad 9/12/15,
sin afirmar que la propuesta ajustada resuelva las 16 claves entre 9 y 12 nudos.

Los rangos se contrastaron también con mdb-json: 550/1404/610 filas seleccionadas
con reposo en esas tres tablas, rangos idénticos. Este segundo formato comparte
el backend mdbtools: no es un lector independiente. El script versionado usa
exportación CSV fresca y comprueba consistencia dentro de cada clave candidata.

## #26 — PARCIAL: la prueba de borrados residentes no explica 12.847

Se recorrieron las páginas ACE5 de 4.096 bytes cuyos encabezados indican
pertenencia a cada tabla. Se leyeron directamente contador y offsets, contando
todos los patrones altos sin recuperar contenido borrado. La fuente primaria
mdbtools v1.0.0, data.c L337-347, usa 0x4000 como borrado y 0x8000 como lookup.
access-parser 0.0.6 se empleó para catálogo/TDEF, no para interpretar esas banderas.

| Temporada/arte | Páginas de datos | Metadatos TDEF y mdb-count | Filas exportadas | Slots totales | Slots con 0x4000 |
|---|---:|---:|---:|---:|---:|
| 2025 enmalle | 583 | 5157 | 5157 | 5157 | 0 |
| 2025 espinel | 532 | 4322 | 4322 | 4322 | 0 |
| 2024 enmalle | 685 | 6081 | 6081 | 6090 | 9 |
| 2024 espinel | 535 | 12847 | 4078 | 4086 | 8 |

En espinel 2024, 4078+8=4086: quedan 8761 sin explicar frente a 12847.
Los ocho patrones altos son 0xd000, no se adivina el significado del bit 0x1000.
El control enmalle 2024 además muestra que sumar slots marcados no tiene por
qué recuperar el contador TDEF: 6081+9 no es 6081.
Rechazo la explicación específica de que los slots borrados residentes sumen
la discrepancia. Sigue siendo posible un contador obsoleto por historia no
preservada, pero no queda demostrado. No se certifica completitud histórica
ni se afirma haber recuperado las filas faltantes. Nada se corrige por inferencia.

Evidencia: ifop_page_offsets_audit.json y audit_ifop_page_offsets.py.
Fuente de semántica y huella del archivo C descargado registradas en el JSON.

## #30 — PARCIAL: escenario de precisión, no AUC observado

Reproduje los intervalos hipotéticos de Claude con la aproximación de
Hanley-McNeil (1982), ecuación 1 y Q1=A/(2-A), Q2=2*A²/(1+A):
SE²=[A(1-A)+(nPos-1)(Q1-A²)+(nNeg-1)(Q2-A²)]/(nPos*nNeg).
La fuente primaria es https://jhanley.biostat.mcgill.ca/software/Hanley_McNeil_Radiology_82.pdf .
Los cuatro pares de intervalos coinciden redondeados con Claude y están en
el JSON. Son planificación condicionada a negativos hipotéticamente válidos
e independencia; no son intervalos estimados de ningún modelo ni garantía
matemática de cuánto se ensancharían al agrupar. No hubo entrenamiento.
Los barcos con alguno de los 17/25/45/16 ceros declarados son 13/19/27/10,
no el rango 8–17 indicado en el comentario. Tampoco son tamaños efectivos
independientes certificados. Mantengo presencia ecológica sin evaluar.

## #32 — CERRADO el tratamiento, con aceptación mutua

Confirmo la lectura conjunta aceptada por Claude en 6647333017: cambios de
claves muestreadas, estratificación por arte, agrupación por barco/viaje y
bloques temporales dentro de año como complemento. Los cambios aritméticos
son (476/875-1)*100=-45.6% y (1253/528-1)*100=137.3%.
Dos años no sustentan generalización interanual robusta; cerrar el tratamiento
documental no elimina esa limitación ni valida independencia de viajes.

## Dictamen propuesto: aceptación parcial y condiciones

Acepto explorar rendimiento nominal registrado por viaje muestreado y arte,
con control por barco, sin denominarlo biomasa ni CPUE estricta. No acepto
todavía un dictamen conjunto final ni que la bandera de reposo esté validada.
Matizo la exclusión de ASIPA: los problemas demostrados limitan presencia/CPUE
en el extracto y objetivo actuales; no prueban inutilidad de cualquier producto
descriptivo derivado de toda ASIPA 1.5.

| Condición | Implicación para el conjunto evaluable |
|---|---|
| Unidad viaje/peso y completitud #25/#26 | Bloquea certificar unidad y denominador de la evaluación; pueden prepararse tablas exploratorias sin presentarlas como viajes certificados. |
| Origen espacial, geometría y arte del piloto #6/#29 | Bloquea atribuir resultados a zonas de faena aprobadas; banderas actuales son control de calidad exploratorio. No se amplía el polígono ni se elige arte. |
| Ambiente histórico #17 | Bloquea evaluar el aporte ambiental mientras no haya emparejamiento verificable; no impide describir capturas registradas. |
| Esfuerzo y reposo #31/#33/#34/#35 | Bloquea CPUE estricta y cota de navegación ajustada; rendimiento nominal sin ese denominador sigue siendo alternativa condicionada. |
| Muestreo y ceros #30 | Bloquea presencia ecológica validada y extrapolación a salidas no observadas. |
| Condiciones de uso #19 | Siguen sin verificarse para estos ZIP; no se autoriza redistribución de originales ni uso comercial por haberlos descargado. |

Ninguna condición se declara resuelta por haber sido aceptada como limitación.
#7/#9/#24 continúan CERRADOS en tratamiento; #6/#17/#19/#25/#27/#28/#29/#30/#31
siguen pendientes o PARCIALES según lo anterior. Los demás estados conservan
lo registrado, sin cierre unilateral. Sin recomendaciones, modelo ni fusión.

## Reproducción y validación técnica

```bash
python chile/audit_ifop_effort_leave_one_out.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/ifop_effort_leave_one_out_audit.json
PYTHONPATH=/ruta/dependencias/access_parser python chile/audit_ifop_page_offsets.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/ifop_page_offsets_audit.json
python -m py_compile chile/audit_ifop_effort_leave_one_out.py chile/audit_ifop_page_offsets.py
```

Requiere pandas/xlrd, mdbtools 1.0.0 y access-parser 0.0.6 con sus dependencias.
Ambos scripts ejecutados sobre las cuatro tablas de las dos bases nuevamente
descargadas; ZIP verificados por SHA-256. Compilación e invariantes de denominadores/offsets
correctas. Resultados agregados, sin identificadores ni originales. Las salidas
mantienen training_ready=false y los ceros no se convierten en ausencias.
Estas comprobaciones técnicas no son validación pesquera.

## Pendiente para la otra parte

Claude: reproducir #26, contrastar #33/#34 y el nuevo #35, revisar la lectura
conjunta de #32 y los límites del dictamen. Sigue pendiente su acceso a originales.
Cola propia priorizada: (1) comprobar servicio histórico ARCO/describe #17;
(2) origen/resolución espacial y cobertura de muestreo #6/#25;
(3) resolver semántica documental de reposo y unidad de viaje, sin convertir
unidades ni tiempos por conjetura. No se duplica la gestión institucional 2026-122.

# PredictaMAR Chile: resultados de la primera auditoría
Fecha: 4 de noviembre de 2026. Sitio: Caleta Portales, Valparaíso.

**Actualización tras revisión independiente:** los conteos de la tabla local se mantienen, pero son filas Event del bloque de captura, no operaciones independientes. Los conteos nacionales/regionales/radios originales no están deduplicados entre bloques. Ver [respuesta y evidencia adicional](RESPUESTA_AUDITORIA.md).

**Resultado:** se confirmó la pertinencia de investigar merluza común y reineta y se obtuvo una base real de datos biológicos y ambientales. La merluza tiene mejor soporte local para empezar. Todavía no hay un modelo validado ni coordenadas recomendadas de pesca.

## 1. Pesquerías y punto de referencia
La consulta oficial de Subpesca devuelve **Portales, código 214**, en **−33.0311458823, −71.5900592190** (WGS84). Su ficha es de 2019: no se presenta su número de embarcaciones como censo actual. [Servicio cartográfico](https://geoportal.subpesca.cl/server/rest/services/IDE_PUBLICO/SRMPUB_CALETAS_PESQUERAS/MapServer/0).

La vinculación con ambas especies no se infiere de su venta en el mercado: se verificó en registros biológicos cuya localidad es PORTALES. El informe IFOP de seguimiento de 2025, publicado en 2026, incluye Portales/El Membrillo en el estrato Valparaíso de estas pesquerías. Los resultados agregados de ese estrato no se atribuyen exclusivamente a Portales. [Informe de seguimiento](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-581228_Seccion_II_Pesqueria_centro_sur.pdf).

## 2. Datos ASIPA: lo que realmente hay
Se descargó y examinó el archivo completo **ASIPA demersales 1.5**: 575.030 filas Event, 3.751.572 Occurrence y 3.258.055 ExtendedMeasurementOrFact. Los conteos se calcularon sobre los archivos, no se copiaron de la descripción del portal. [Fuente y licencia](https://gbif-chile.mma.gob.cl/ipt/resource?r=asipa_demersales&v=1.5).

| Soporte asociado a localidad PORTALES | Merluza común | Reineta |
|---|---:|---:|
| Eventos con presencia declarada | 16.038 | 236 |
| Filas Occurrence originales | 22.524 | 467 |
| Fechas distintas | 1.946 | 93 |
| Pares de coordenadas distintos | 646 | 142 |
| Último registro | 30/12/2022 | 02/11/2022 |
| Eventos de encuesta de enmalle | 9.552 | 5 |
| Eventos de encuesta de espinel | 6.486 | 231 |

Hay cantidades repetidas por evento: al distinguir evento, especie, cantidad, unidad y estado, esas filas se reducen a los mismos 16.038 y 236 eventos. **No se sumaron esas cantidades repetidas dentro del mismo evento. Esto no resuelve duplicados entre programas ni identifica viajes.** Tampoco se asume que dos eventos sean viajes independientes.

En el subconjunto filtrado por el texto PORTALES (bloque 14-01) todas las filas objetivo declaran presencia; no se construye un clasificador presencia/ausencia usando únicamente ese subconjunto. En el conjunto nacional hay **12.310 eventos de merluza y 1.087 de reineta con estados contradictorios** entre sus filas del mismo Event. Esta medida no detectaba los conflictos entre Event de bloques diferentes; se incorporó una conciliación adicional sin reinterpretar estados. Deben ponerse en cuarentena y resolverse por origen, no por voto mayoritario. No se convierten en ausencias las especies no registradas.

La extensión de mediciones contiene biometría; no ofrece por sí sola el esfuerzo completo de cada operación. `sampleSizeValue` incluye altura de red, no una definición suficiente de esfuerzo. Los campos de profundidad de los eventos objetivo de Portales están vacíos, aunque hay valores en campos de elevación. No se cambió su significado automáticamente ni se calculó CPUE.

La licencia visible de esta versión es **CC-BY-NC 4.0**. El permiso de reutilización comercial está pendiente de aclarar. Los datos originales no se publicaron en el repositorio.

## 3. Cruceros IFOP de merluza 2024 y 2025
Se descargaron los anexos oficiales, se abrieron sus bases Access y se exportaron sus tablas de forma reproducible.

| Contenido examinado | Crucero 2024 | Crucero 2025 |
|---|---:|---:|
| Filas acústicas con posición y NASC | 1.349 | 1.340 |
| Lances de identificación | 97 | 93 |
| Lances en recuadro de diagnóstico 32–34°S, 71,3–73°W | 16 | 16 |
| Registros verticales oceanográficos | 14.786 | 16.390 |
| Estaciones oceanográficas | 67 | 65 |

Los intervalos acústicos están etiquetados `mergayi`, pero carecen de fecha/hora en la tabla y no contienen NASC cero explícito. No se infieren ausencias a partir de intervalos omitidos ni se emparejan con el ambiente de un día inventado. Los lances son de arrastre científico; no validan directamente recomendaciones para redes artesanales.

**Problemas detectados:**
- OCEAN 2025 tiene las columnas de latitud y longitud invertidas respecto del dominio chileno. Se conservó el original. Para contar soporte regional se documentó un intercambio diagnóstico, todavía no una corrección operativa aprobada.
- En OCEAN 2024 las 14.786 lecturas de clorofila son cero: se consideran sospechosas hasta aclarar si son valores de relleno.
- La bitácora 2024 tiene 31 fechas vacías y seis fechas cuyo año no es 2024. No se corrigieron copiando fechas vecinas. Solo 60 lances tienen fecha del año esperado.
- En 2025 hay una duración superior a una hora que requiere contrastar horarios y unidades antes de estandarizar captura.

Las dos campañas contienen 32 lances en el recuadro regional y todos tienen merluza positiva. Esto restringe el contraste local de presencia y exige revisar abundancia, profundidad y diseño de muestreo; no basta para afirmar capacidad de encontrar pesca.

Fuentes: [anexo 2024](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2025/P-682119_anexos.zip), [anexo 2025](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-682128_anexos.zip), [informe 2025](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-682128.pdf).

## 4. Copernicus: descarga real y límites
Se ejecutó [el diagnóstico en GitHub](https://github.com/ywarthonv-source/predictamar-litoral/actions/runs/41908575663), usando las credenciales ya guardadas allí. No se transfirieron contraseñas al entorno local. La primera ejecución falló por límites de coordenadas; se corrigió la selección y la segunda descargó datos.

Periodo solicitado: **1–30 de octubre de 2026**. Recuadro técnico: 32,8–33,3°S y 71,6–72,1°W. No representa un área de faena aprobada.

| Producto descargado | Fechas obtenidas / 30 | Grilla horizontal del subconjunto |
|---|---:|---:|
| Temperatura de modelo | 30 | 6 × 6 |
| Salinidad de modelo | 30 | 6 × 6 |
| Corrientes de modelo | 30 | 6 × 6 |
| Oxígeno de modelo | 30 | 2 × 2 |
| SST OSTIA | 30 | 10 × 10 |
| Clorofila L3 | 15 | 12 × 12 |
| Clorofila L4 | 10 | 12 × 12 |

La clorofila L3 obtenida cubre 15–29 de octubre y L4 cubre 20–29. No se presentaron como series completas ni se rellenaron días faltantes. L3 tiene 63,75% de valores finitos en todo el recuadro y fechas disponibles; L4 88,89%. Esos porcentajes incluyen celdas terrestres y no equivalen a porcentaje de mar sin nubes. La falta de fechas puede deberse a disponibilidad del producto y se distingue de los huecos espaciales.

OSTIA es un análisis L4 y la clorofila L4 es interpolada por el proveedor: continuidad no significa observación directa bajo las nubes. Temperatura, salinidad, corrientes y oxígeno de modelo permiten estudiar la columna de agua sin depender de una imagen óptica despejada ese día, pero mantienen errores y resolución limitada. El oxígeno solo aporta cuatro celdas en este recuadro: es contexto regional, no localización fina de cardúmenes. Se conservaron profundidades nativas, unidades, coordenadas y huellas de los NetCDF.

## 5. Decisión y trabajo que queda
**Prioridad técnica: merluza común primero; reineta en paralelo como segunda pesquería.** La decisión se apoya en la cantidad y estructura de los datos locales, no en una eficacia predictiva ya demostrada.

Antes del primer experimento de modelación hay que resolver conflictos de estados, duplicación entre programas, fechas, posición de captura frente a puerto y definición de esfuerzo. Después, comparar predictores ambientales de profundidad adecuada contra referencias de profundidad/costa/época, separando campañas, tiempo y unidades de muestreo. Evaluar el valor adicional dentro del rango real de la flota, sin mezclar arrastre científico y enmalle/espinel como si fueran el mismo proceso.

La revisión independiente de Claude ya fue recibida y sus observaciones críticas contrastadas. Quedan pendientes la geometría/arte actuales del piloto, aclaraciones de datos y permisos, y la revisión de las correcciones. Ningún resultado de esta auditoría habilita recomendaciones operativas ni transfiere la calibración peruana.

## Reproducibilidad
`audit_summary.json`, `cruise_audit.json`, `environmental_summary.json` y `download_manifest.json` contienen los resultados verificables. Los scripts están en `chile/`. Se ejecutó la auditoría completa de ASIPA y de ambas bases Access; las seis comprobaciones iniciales offline protegen taxonomía, unidades de distancia, coordenadas DDMM y tratamiento de faltantes. El workflow conserva como fallo de cobertura las dos series de clorofila incompletas; no se cambia ese resultado a éxito artificialmente.


## Hallazgos adicionales tras la revisión
El emparejamiento exploratorio por `eventDate` (MM/DD/YYYY HH:MM:SS) y coordenadas numéricas exactas encuentra 15.764 claves compartidas entre PORTALES/14-01 y 560.0/15-01; 519 de ellas tienen varios eventos de captura. Son enlaces candidatos, no operaciones certificadas. Hay 8.772 claves con kilos positivos de merluza en captura y solo *absent* en biología. El significado de *absent* sigue sin confirmar y no se utiliza como cero.

Se detectaron 196.791 discrepancias entre fechas parseables en 15-01 y siete `eventDate` no parseables. Se conservan ambos campos; no se declara cuál es la fecha de pesca. La conciliación completa está en `review_reconciliation.json`.

Clorofila: las 15 fechas L3 incluyen cuatro con 0, 2, 5 o 20 celdas finitas. Solo 10 fechas superan el 80% de un soporte proxy de 128 celdas; ese umbral es exploratorio. El 71,71875% se calcula sobre ese proxy, no sobre una máscara marina independiente. L4 coincide con L3 donde ambas existen y aporta 312 celdas adicionales en las 10 fechas comunes: se marcan como L4 disponible sin L3, no como observación óptica certificada.

El diagnóstico 2026 no es un conjunto ambiental emparejado con capturas históricas. Para ese experimento hacen falta productos históricos del mismo periodo y profundidad, y fechas pesqueras con semántica resuelta.


## Revisión de Claude en el PR y ronda 2
La primera respuesta de Claude en el PR reprodujo los vínculos, conflictos y discrepancias principales, y aceptó varios tratamientos. El ciclo sigue abierto: `independent_review_completed=false` corrige #23. Véase [RONDA_2.md](RONDA_2.md).

La comprobación adicional de campos originales distingue altura de red (9.589 filas) de tamaño de malla (6 filas) en `sampleSize`; no se considera esfuerzo. Los nombres de dataset documentan enmalle/espinel sin certificar el arte por viaje. Septiembre tiene 71 eventos; el diseño temporal deberá considerar el régimen regulatorio por año, sin interpretar menor muestreo como menor abundancia.

El STAC público permite identificar versiones MY diarias 202603 que cubren temporalmente 2010–2022; eso no certifica cobertura local ni explica los días ausentes del diagnóstico NRT. IFOP publica indicadores de esfuerzo/rendimiento para Valparaíso, pero no se ha confirmado acceso, cobertura de ceros ni permiso de los microdatos necesarios. Se valida una consulta única de Randy a integración/fuente e IFOP, detallada en la ronda 2. No hay conjunto listo para evaluar presencia/ausencia o CPUE con el extracto actual, ni dictamen conjunto final.


## Bases artesanales públicas encontradas: ronda 3
Se descargaron los ZIP de Sección I, temporadas 2024 y 2025, publicados en el catálogo IFOP. Contienen bases Access artesanales de enmalle/espinel, tablas maestras y diccionario XLS. Se verificó Portales=560, merluza=1 y código 999=viaje sin captura. La falta de esfuerzo/ceros de ASIPA no debe generalizarse a estos nuevos archivos. La solicitud institucional sigue siendo útil para condiciones y aclaraciones; ya no es la única vía de acceso a datos individuales.

Para Portales y objetivo merluza hay 476/1.253 claves candidatas de viaje en enmalle/espinel 2025 y 875/528 en 2024. Existen cantidades positivas, ceros explícitos de merluza y registros código 999 con peso cero, junto con longitud de red o anzuelos. No se infieren ceros por ausencia de fila de especie ni se certifica la clave candidata. Véanse [RONDA_3.md](RONDA_3.md), [auditoría agregada](ifop_public_artisanal_audit.json) y [manifiesto](ifop_public_annex_manifest.json).

Persisten problemas: contador Access discrepante en espinel 2024, un código 999 con peso positivo, descripciones invertidas de inicio/fin de calado y posiciones que requieren contraste geográfico. No hay conjunto listo para entrenamiento ni permiso comercial confirmado; no se calculó CPUE ni se entrenó un modelo. Los originales e identificadores individuales permanecen fuera del repositorio.


## Revisión exploratoria de posiciones y viajes
La comparación con Natural Earth land 5.1.1 (escala 1:10 millones) señala ocho filas a más de 5 km tierra adentro bajo esa referencia generalizada. Son banderas de revisión, sin excluir ni certificar posiciones; el entorno costero requiere una referencia más detallada. Las distancias se calcularon contra la frontera real de los polígonos unidos, sin usar bordes del recuadro como costa.

En las cuatro tablas no se detectaron zarpe/recalada/lance temporalmente incompatibles bajo el parseo explícito. Sin embargo, tres claves candidatas declaran varias caladas y solo un número de lance: queda pendiente resolver si las filas resumen viajes y cómo se define el esfuerzo. Véanse [GEOGRAFIA_Y_VIAJES.md](GEOGRAFIA_Y_VIAJES.md) y [auditoría agregada](ifop_geography_audit.json). No se construyeron etiquetas de entrenamiento ni se modificaron los originales.


## Ronda 4: ceros declarados, esfuerzo y plausibilidad
La respuesta a Claude ronda 3 está en [RONDA_4.md](RONDA_4.md). Los 3.132 candidatos se separan en 2.998 con merluza positiva, 20 con merluza de peso cero, 83 con solo código 999 y peso cero, 30 sin fila de merluza y un conflicto 999/peso positivo. Los 103 candidatos de peso cero declaran esfuerzo y caladas positivos; esto aporta coherencia interna, sin validar ausencias ecológicas ni faena observada. Véase [CEROS_Y_FAENA.md](CEROS_Y_FAENA.md).

El control distancia/duración marca 18 claves candidatas a 12 nudos bajo un escenario exploratorio; no elimina ni repara posiciones. El caso de 332,860 km tiene duración declarada de 3,75 h en la misma clave. La coincidencia del esfuerzo con la moda de cada barco es frecuente también en positivos y no distingue aparejo estable de un atributo copiado. Resultados y supuestos en [auditoría de plausibilidad](ifop_trip_plausibility_audit.json) y [auditoría de faena declarada](ifop_zero_activity_audit.json).

Dictamen provisional: explorar rendimiento nominal registrado por viaje muestreado, separado por arte. Unidad, representatividad, esfuerzo, precisión espacial, permisos y ambiente histórico siguen condicionándolo. No hay CPUE estricta calculada, modelo entrenado, etiquetas ecológicas validadas ni acuerdo final. Próximos pasos: páginas borradas Access (#26), origen/resolución espacial y cobertura (#6/#25), servicio ambiental histórico (#17).

## Ronda 5: repetición de esfuerzo, reposo y metadatos Access
La respuesta a Claude ronda 4 y los cálculos nuevos están en [RONDA_5.md](RONDA_5.md). La coincidencia modal del esfuerzo dejando fuera el propio viaje es 407/447, 969/1.223, 734/818 y 427/493. Es repetición alta por viaje, sin constancia universal por barco ni demostración de equivalencia entre kg/viaje y CPUE.

Enmalle 2024 carece de reposo en toda su tabla. En las otras tres tablas seleccionadas, los 2.255 candidatos con reposo informado tienen valores mayores que la duración zarpe-recalada bajo la unidad literal del diccionario. No se resta reposo al viaje ni se convierte a minutos: puede haber una escala distinta o un reposo no contenido en ese viaje, todavía sin resolver (#35). Véase [auditoría de esfuerzo y reposo](ifop_effort_leave_one_out_audit.json).

La inspección de páginas Access de espinel 2024 cuenta 4.078 filas exportadas y ocho slots con bandera de borrado, frente a 12.847 en TDEF: la diferencia no se explica sumando esos slots. La completitud histórica sigue sin certificar; [evidencia](ifop_page_offsets_audit.json). #32 queda CERRADO solo en tratamiento tras aceptación mutua de los matices. Persisten las condiciones del conjunto exploratorio de rendimiento nominal, sin acuerdo final ni recomendaciones.



## Ronda 6: compatibilidad de reposo y ejes temporales ARCO
La [respuesta a Claude ronda 5](RONDA_6.md) completa las pruebas de reposo: interpretar los valores como minutos es compatible con duración de viaje en 475/475, 1.252/1.252 y 528/528 candidatos informados. La alternativa basada en el anterior viaje muestreado es compatible en 248/433, 682/1.204 y 264/484 casos comparables. Los intervalos muestreados suelen separar varios días; ninguna prueba identifica la unidad ni el mismo aparejo. No se convierten los originales. [Cálculos e hipótesis](ifop_soak_hypotheses_audit.json).

Se leyeron los chunks de coordenadas temporales ARCO de clorofila MY L3/L4 202603: ambos servicios tienen ejes diarios completos con 366 fechas en 2024 y 365 en 2025. No se ha verificado todavía el valor CHL histórico en la zona ni emparejado con pesca. La lectura NRT quedó acotada por presupuesto de solicitudes, sin concluir indisponibilidad. [Manifiesto y ejes](arco_time_axes_audit.json).

#30 y #34 quedan CERRADOS solo en tratamiento tras aceptación mutua, conservando las limitaciones de presencia y reposo en #35. Unidad/completitud, origen espacial, esfuerzo, ambiente emparejado y condiciones de uso siguen pendientes según objetivo. No hay dictamen conjunto final, modelo ni recomendaciones.



## Muestra histórica de valores CHL: avance independiente de ronda 6
Se descargaron seis chunks CHL de MY L3/L4 202603 para fechas fijadas antes de leer valores: 2015-01-15, 2024-01-15 y 2025-01-15. En la misma grilla de diagnóstico de 12×12 celdas, L3 aporta 2/36/70 valores finitos dentro de límites publicados y L4 128 en cada fecha. Se enmascararon rellenos y no se aplicaron flags auxiliares. Los denominadores son rectangulares, no una máscara marina.

L4 coincide exactamente con L3 en sus 2/36/70 celdas comunes y aporta 126/92/58 adicionales. Eso no acredita observación independiente, exactitud de la interpolación ni evidencia de peces. Hay acceso histórico real en tres días; falta emparejar con pesca, evaluar cobertura y calidad, y resolver fecha/posición/unidad. #17 permanece PARCIAL. Véanse [alcance y reproducción](MUESTRA_AMBIENTAL_HISTORICA.md) y [resultados/manifiesto](arco_historical_chl_probe.json). No hay modelo, recomendaciones ni cambio del polígono del piloto.



## Ronda 7: hipótesis de reloj y cobertura diaria histórica
La [respuesta a Claude ronda 6](RONDA_7.md) contrasta el formato de reloj de HORAS_REPOSO. En las tablas completas con datos, 2/4.339, 1/2.326 y 33/2.489 filas tienen sufijo ≥60. Localmente 2.254/2.255 valores admiten la lectura de reloj y caben en la duración; ello no acredita el formato, el predeterminado ni la semántica del campo. La sensibilidad D marca 9/17/7 claves a 12 nudos, sin corregir originales ni reemplazar banderas. [Evidencia](ifop_clock_soak_audit.json).

El censo CHL MY L3/L4 202603 sobre el recuadro técnico cubre 731 fechas de 2024–2025 con geoChunked. L3 tiene 92 días sin celdas finitas; L4 mantiene 128/144 celdas finitas. Las 16 restantes se publican como soporte faltante del producto, sin certificar tierra o una máscara marina independiente. Hay 31.000 pares celda-día L4 sin L3 simultánea, sin validación pesquera ni de procedencia óptica. [Censo y manifiesto](arco_coverage_2024_2025.json). #17 sigue PARCIAL: faltan emparejamiento y controles completos.

Dictamen conjunto provisional aceptado: viable de forma condicionada para explorar rendimiento nominal por viaje muestreado y arte. La unidad de viaje, completitud, posición, reposo, plausibilidad y permisos siguen condicionando la evaluación. No hay conjunto listo, acuerdo final, modelo ni recomendaciones.

## Ronda 8 · Fecha de lance y cobertura por celda
La [respuesta a Claude ronda 7](RONDA_8.md) verifica la coincidencia de FECHA_LANCE y recalada en 3.128/3.132 claves de Portales con dos lectores. Los 3.132 días de lance coinciden con recalada y 10 difieren del día de zarpe. #36 queda PARCIAL. La semántica de fecha y posición para un emparejamiento de pesca requiere confirmación de origen. El mismo [diagnóstico](ifop_alignment_inputs_audit.json) desglosa reposos ambiguos, entre ellos 9999 en 11 filas de espinel 2024, cuyo significado sigue abierto.

El [censo por celda](arco_cell_support.json) sitúa L3 entre 449 y 559 días finitos dentro del soporte fijo L4, con rachas máximas de 6 a 11 días por celda. GLOBE identifica diez celdas mixtas en ese soporte, incluida la huella de la referencia portuaria. El soporte 128 sigue siendo un conteo empírico de L4. #17 continúa PARCIAL y el dictamen conjunto provisional conserva las condiciones de fecha, posición, unidad y calidad.

## Contrato candidato · Avance independiente de ronda 8
La [prueba del contrato](CONTRATO_CANDIDATO.md) asigna 3.615 filas a 3.132 claves candidatas en cuatro estratos IFOP. Hay 2.998 cantidades positivas de merluza y 20 ceros explícitos con semántica pendiente. Otras 113 cantidades quedan sin asignar y un conflicto 999 permanece en cuarentena. Tres claves declaran varias caladas y 17 carecen de ese conteo.

El [inventario agregado](candidate_inventory_audit.json) verifica trazabilidad y separación de estados. Las 3.132 claves permanecen en cuarentena para emparejamiento ambiental por #6/#25/#36. Pares certificados: cero. El [contrato candidato](../candidate_dataset_contract.json) mantiene evaluation_ready y training_ready en false.

## Ronda 9 · Cobertura observada y anclas
La [respuesta a Claude](RONDA_9.md) reproduce cobertura por arte y mes. Septiembre carece de claves en los cuatro estratos. Espinel 2024 carece también de julio y agosto. Las 406 claves con otra especie positiva y las frecuencias de filas por clave describen el registro disponible. El marco muestral y la completitud de captura siguen abiertos.

Los histogramas de zarpe y recalada permiten separar la sensibilidad de día registrado del momento de pesca. Hay 3.122 claves con día común y diez con días distintos. La documentación GlobColour define el día del producto aproximadamente en UTC. El huso de IFOP y las anclas de captura siguen pendientes. [Agregados](candidate_coverage_audit.json).

#37 queda PARCIAL con el contraste por longitud y los requisitos de bandera costera en el contrato. Se cierra el desacuerdo escalado sobre E por aceptación mutua. HHMM, centésimas de hora y registros mixtos conservan el alcance de hipótesis. #35 sigue PARCIAL.

## Ronda 10 · Calendario y posiciones de inicio
La [respuesta a Claude](RONDA_10.md) documenta las 3.122 claves con día invariante bajo desplazamientos 0/+3/+4 y las diez claves que cruzan el día registrado. Las 3.132 recaladas candidatas se registran de martes a viernes y la unión de ambos artes tiene un máximo de 17 días por mes. El marco muestral sigue abierto.

Los pares de inicio de virado o calado están informados en las 3.615 filas. Coinciden con la posición genérica en 3.612. Las otras tres corresponden a claves de espinel 2025 y conservan una bandera de discrepancia. La posición efectiva de captura sigue sin certificar. [Agregados](candidate_calendar_position_audit.json).

Septiembre queda fuera del diseño de pesca dirigida por el D.Ex. 464/2016. La revisión sin filtro de objetivo arroja cero filas de Portales en ese mes. El hueco de espinel dirigido en julio y agosto de 2024 conserva causa abierta.

## Ronda 11 · Alcance de los registros por fecha y arte

La [respuesta a Claude](RONDA_11.md) confirma que las cuatro tablas completas tienen filas en septiembre y Portales tiene cero aun sin filtrar objetivo. La veda de merluza dirigida queda confirmada. La actividad de la flota y la causa de los huecos del registro siguen abiertas. En 18 feriados nacionales de martes a viernes fuera de septiembre hubo una recalada registrada. Esta prueba no identifica el calendario muestral ni un desfase de fecha.

Tres claves de espinel 2025 mantienen cuarentena adicional por conflicto de posición. Un par de inicio cae fuera del recuadro diagnóstico bajo DDMMSS. La maniobra registrada depende del arte. La clave con la única fila de especie vacía conserva la cantidad sin asignar. El [diagnóstico agregado](candidate_calendar_followup_audit.json) y el [contrato candidato](../candidate_dataset_contract.json) mantienen bloqueado el emparejamiento mientras falten procedencia y anclas verificables.

## Avance de ronda 11 · Cómo se obtuvieron las posiciones artesanales

La Sección I de IFOP documenta dos vías para las posiciones artesanales: encuestas con distancia y dirección desde una referencia en la costa, o GPS tomado directamente por observadores científicos embarcados. Las encuestas en puntos de desembarque fueron la vía predominante de recopilación de datos pesqueros artesanales del programa. Esa proporción general no identifica el origen de cada registro de Portales. [Informe de gestión 2024, pp. 11, 22 y 41](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2025/P-581216_Informe_Gestion.pdf#page=28) y [2025, pp. 12, 23 y 43](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-581228_Seccion_I.pdf#page=29).

Se inspeccionaron los encabezados completos que devuelve mdb-export para las cuatro tablas artesanales con la función `strata(raw_dir, full_tables=True)` de [audit_candidate_coverage.py](../audit_candidate_coverage.py). La función comprueba ambos ZIP y sus miembros antes de exportar. Los esquemas de enmalle y espinel, 2024 y 2025, carecen de una columna explícita de modalidad de observación o fuente de posición. Esto acota la búsqueda a una tabla de enlace, formulario original o documentación adicional. El contenido de los campos, incluida la coincidencia entre posición genérica e inicio, no asigna por sí mismo encuesta o GPS. #6 sigue PARCIAL.

El método general describe la recopilación de fechas de zarpe y recalada, pero las secciones citadas no especifican el reloj ni la regla que genera FECHA_LANCE en los anexos. La cobertura regional del programa no identifica el marco de viajes de Portales por arte y día. #36 y #39 siguen PARCIAL. El emparejamiento ambiental sigue condicionado a una referencia verificable por registro.

SHA-256 de los PDF revisados: 2024 `a9b3b7b5f1ec707ac6824ccde1766a0bc451d5b46fabb6db11931e72ad0c0a87`; 2025 `44b919f9df0c44173f1d33a3b2e9f27e62aaa288aae2d5b724ca342e0e796a65`. Se extrajo texto con `pdftotext -layout`.

## Avance de ronda 11 · Fechas y horas de maniobra en los anexos

**#36 PARCIAL.** En los cuatro estratos, las 3.615 filas candidatas carecen de fecha y hora en los cuatro campos de inicio y fin de calado y virado. El resultado se mantiene al incluir cualquier especie objetivo en Portales. Las mismas columnas sí contienen datos en las tablas completas.

| Año | Arte | Filas candidatas | Filas Portales sin filtro de objetivo | Filas Portales con algún campo de maniobra | Filas de todos los puertos con algún campo de maniobra |
|---|---|---:|---:|---:|---:|
| 2024 | Enmalle | 1.049 | 1.058 | 0 | 976 |
| 2024 | Espinel | 610 | 626 | 0 | 2.246 |
| 2025 | Enmalle | 551 | 559 | 0 | 811 |
| 2025 | Espinel | 1.405 | 1.411 | 0 | 1.843 |

Reproducción desde la raíz, con los ZIP y miembros Access verificados por [el lector existente](../audit_candidate_coverage.py):

```sh
PYTHONPATH=chile python - /ruta/privada/gestion_publica <<'PY'
from pathlib import Path
import sys
from audit_candidate_coverage import strata

for year, gear, _, source in strata(Path(sys.argv[1]), full_tables=True):
    port = source[source.PUERTO_RECALADA.eq('560')]
    candidates = port[port.ESPECIE_OBJETIVO.eq('1')]
    fields = [f'FECHA_HORA_{phase}_{operation}'
              for phase in ('INI', 'FIN') for operation in ('CALADO', 'VIRADO')]
    def populated(rows):
        return int(rows[fields].apply(lambda col: col.str.strip().ne('')).any(axis=1).sum())
    print(year, gear, len(candidates), len(port),
          populated(candidates), populated(port), populated(source))
PY
```

Los campos de maniobra no permiten recuperar una fecha independiente para el emparejamiento de Portales con el ambiente. El patrón no distingue por sí solo encuesta de observación GPS ni demuestra cómo se generó FECHA_LANCE. El siguiente contraste es buscar el formulario original o un enlace por viaje a un registro de operación independiente.

## Ronda 12 · Procedencia y calendario de los registros

**#6 y #36 PARCIAL.** Se cruzó el puerto, la presencia de alguna hora de maniobra, la presencia de alguna coordenada final de la fase del arte y la igualdad numérica de los pares completos. Se reexportaron las cuatro tablas Access completas desde los anexos verificados. El código separa pares no comparables. Comando desde la raíz: `python chile/audit_ifop_record_patterns.py /ruta/privada/gestion_publica`.

| Año | Arte | Filas con hora de maniobra | Con extremo final dentro de esas filas | Par genérico e inicial dentro de esas filas |
|---|---|---:|---:|---|
| 2024 | Enmalle | 976 | 976 | 976 iguales |
| 2025 | Enmalle | 811 | 811 | 811 iguales |
| 2024 | Espinel | 2.246 | 0 | 2.246 no comparables |
| 2025 | Espinel | 1.843 | 0 | 1.843 no comparables |

Las 3.654 filas de Portales sin filtro de objetivo carecen de horas de maniobra y extremos finales. Fuera de Portales, ninguna fila sin hora trae un extremo final. El cruce sí separa patrones de registro por arte, pero falta una etiqueta de origen para atribuirlos a encuesta o GPS. En enmalle, un extremo final puede coexistir con pares inicial y genérico iguales. En espinel, la ausencia de extremo final no discrimina las filas con y sin hora. El cambio limitado al componente de minutos o segundos queda como discrepancia no atribuida. Los demás casos tampoco tienen causa confirmada.

Volví a descargar el informe 2025 y confirmé el SHA-256 documentado arriba. La Sección I, pp. 12 y 23, identifica el Registro diario de actividad y distingue las vías de encuesta y GPS. Esas secciones no reproducen el formulario ni detallan si incluye las horas de calado y virado. La coincidencia por arte no permite asignar una incertidumbre en kilómetros. [Informe de gestión IFOP 2025](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-581228_Seccion_I.pdf#page=29).

**#39 PARCIAL.** De los 385 martes a viernes fuera de septiembre en 2024–2025, 18 son feriados nacionales del contraste previo y 367 son no feriados. La suma de días con registro del JSON previo es 304, incluido un feriado. Por tanto, la comparación descriptiva correcta es 303/367 en no feriados frente a 1/18 en feriados. Se retira la métrica de día hábil lunes–viernes como resumen porque incluye siete comparaciones en lunes, fuera del soporte observado. En 9 de los 11 casos cuyo día calendario siguiente es miércoles a viernes no feriado hay registros. Ese conteo contradice un desfase uniforme de +1 día combinado con ausencia total de pesca en feriados. Por sí solo no descarta un desfase sin ese supuesto ni identifica por qué faltan registros en las dos fechas restantes. No se usa el valor p binomial para inferir un calendario de muestreo. [Calendario por mes](candidate_calendar_position_audit.json) y [contraste por feriado](candidate_calendar_followup_audit.json).

**#25 CERRADO** el tratamiento de la clave con solo una fila sin especie, con aceptación de Claude. Semántica y completitud siguen PARCIAL. **#38 ACEPTADO** el conteo de septiembre en tablas completas. La causa del hueco de espinel dirigido de julio–agosto de 2024 sigue PARCIAL. El dictamen sobre emparejamiento ambiental permanece condicionado a una referencia verificable de posición y fecha.

## Ronda 13 · Completitud de los pares y origen del registro

**#6 y #36 PARCIAL.** El nuevo desglose separa pares completos, en blanco, parciales e inválidos antes de comparar. «Completo» aquí significa que ambas componentes se convierten a números. No acredita procedencia, precisión ni validez geográfica. Comando ejecutado sobre los cuatro miembros Access verificados por `strata`: `python chile/audit_ifop_record_patterns.py /ruta/privada/gestion_publica`.

```text
2025 enmalle 5157
portales  time   end    generic   initial   pair     
False     False  False  complete  complete  different       9
                                            equal        3778
          True   True   complete  complete  equal         811
True      False  False  complete  complete  equal         559
2025 espinel 4322
portales  time   end    generic   initial   pair          
False     False  False  blank     blank     not_comparable     161
                        complete  complete  different            2
                                            equal              905
          True   False  blank     blank     not_comparable       1
                        complete  blank     not_comparable    1840
                        partial   blank     not_comparable       2
True      False  False  complete  complete  different            3
                                            equal             1408
2024 enmalle 6081
portales  time   end    generic   initial   pair          
False     False  False  blank     blank     not_comparable       2
                                  complete  not_comparable       1
                        complete  blank     not_comparable       1
                                  complete  different            1
                                            equal             4041
                        partial   partial   not_comparable       1
          True   True   complete  complete  equal              976
True      False  False  complete  complete  equal             1058
2024 espinel 4078
portales  time   end    generic   initial   pair          
False     False  False  blank     blank     not_comparable       8
                        complete  blank     not_comparable       3
                                  complete  equal             1195
          True   False  complete  blank     not_comparable    2246
True      False  False  complete  complete  equal              626
```

En enmalle, hora de maniobra y al menos una coordenada final coinciden en ambos sentidos en cada año. En espinel con hora, el par inicial está en blanco en las 4.089 filas. El genérico está completo en 4.086, parcial en dos y en blanco en una. Por tanto, el genérico suele ser la única posición disponible en ese grupo. Esto distingue estructuras de registro, pero no identifica encuesta o GPS. Se documenta el alias del diccionario 2025 para la latitud de inicio de calado en el [contrato candidato](../candidate_dataset_contract.json).

Se inspeccionó el inventario de miembros de ambos ZIP de gestión mediante `zipfile.ZipFile.infolist()`: cuatro Access y un XLS por año. Los ZIP no contienen un archivo separado del formulario. La búsqueda en IFOP devolvió un formulario de otro programa, de pesquerías bentónicas, que no se emplea como sustituto. Sigue faltando un formulario demersal aplicable o un enlace verificable de procedencia por viaje. [Referencia del programa bentónico](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2018/P-581128.pdf).

**#39 CERRADO** el alcance descriptivo del calendario acordado con Claude. **PARCIAL** el marco muestral. El dictamen sobre emparejamiento ambiental no cambia.

## Ronda 14 · Sensibilidad al protocolo histórico y subreporte

**#40 PARCIAL.** El protocolo histórico de IFOP usa objetivo 1 **y** especie capturada 1, agrupa Portales con otros puertos en Valparaíso, estratifica por puerto y mes y presenta kg/viaje por arte y categorías de eslora. El inventario del piloto conserva filas de otras especies y estados de captura, por lo que el filtro de peso se evaluó como sensibilidad sobre las filas explícitas de merluza. Ninguna captura positiva queda fuera de los rangos históricos. Los 20 ceros explícitos quedan fuera, y ninguno adquiere un peso dentro de rango al sumar retenido y descarte. Los cuatro esquemas no contienen un campo de eslora. Por tanto, la estratificación histórica exigiría un enlace verificable a eslora. El precedente respalda explorar kg/viaje por arte, sujeto a validar la unidad y el marco muestral. No se aplica el filtro al inventario. [Protocolo de la comisión, Doc. 2](https://www.subpesca.cl/portal/615/articles-108809_documento.pdf#page=15).

| Año | Arte | Filas candidatas | Filas merluza explícita | Ceros fuera de rango | Filas de la razón diagnóstica | Razón diagnóstica |
|---|---|---:|---:|---:|---:|---:|
| 2024 | Enmalle | 1.049 | 832 | 12 | 820 | 105,952 g/m |
| 2025 | Enmalle | 551 | 454 | 0 | 453 | 124,303 g/m |
| 2024 | Espinel | 610 | 505 | 6 | 499 | 25,451 g/anzuelo |
| 2025 | Espinel | 1.405 | 1.227 | 2 | 1.225 | 30,880 g/anzuelo |

**#31/#33 PARCIAL.** Razón de sumas sobre filas explícitas con peso en rango, esfuerzo finito positivo y una sola fila de merluza por clave. Una fila positiva de enmalle 2025 quedó fuera de la razón. Comando ejecutado desde la raíz sobre los Access verificados: `python chile/audit_ifop_protocol_sensitivity.py /ruta/privada/gestion_publica`. Las cifras de espinel quedan cerca de 30 g/anzuelo en la Figura 7. Las de enmalle son inferiores a las curvas de la Figura 8. Las figuras no tienen el mismo dominio ni período que el cálculo local, y la coincidencia aproximada no identifica el campo ni valida el esfuerzo ejercido. Los g/m y g/anzuelo son unidades condicionales a la interpretación ensayada. [IT CCT-RDZCS 02/2025, figuras 7–8](https://www.subpesca.cl/portal/616/articles-128066_documento.pdf#page=9).

**#41 ACEPTADO** el hallazgo documental. La inspección visual de la página impresa 7 confirma Portales 1,4 en 2023 y 1,0 en 2024. La tabla termina en 2024. Es un ajuste agregado de la asesoría y no una regla de corrección por viaje. Los desembarques oficiales aportan contexto, con escala y procedencia propias. El valor de 2024 no prueba ausencia de sesgo en los viajes ni se extrapola a 2025. [Tabla del IT](https://www.subpesca.cl/portal/616/articles-128066_documento.pdf#page=9).

**#6/#36 PARCIAL.** El cruce de pares y horas solicitado en la ronda 12 ya está en la ronda 13. La fecha y posición de faena siguen pendientes para vincular los viajes con el ambiente. El resultado de esta sensibilidad no cambia el dictamen de viabilidad condicionada para el rendimiento nominal por viaje muestreado.

## Ronda 15 · Eslora, límites de coordenadas y figura de esfuerzo

**#40 PARCIAL.** En las cuatro hojas Bitácora Enmalle/Espinel, fila 2, el diccionario llama a COD_BARCO código IFOP de la embarcación. En las 3.615 filas candidatas todos los códigos tienen siete caracteres y ninguno es exclusivamente decimal. El formato no identifica un número RPA ni permite un cruce verificable con un padrón. La eslora sigue pendiente. Se corrigió la sensibilidad del protocolo para probar retenido más descarte tanto con PESO nulo como con cero. La reejecución confirma cero sustituciones dentro de rango y conserva las razones previas. [Protocolo histórico](https://www.subpesca.cl/portal/615/articles-108809_documento.pdf#page=15).

**#6/#36 PARCIAL.** El desglose de completitud y la equivalencia hora/extremo final en enmalle quedan CERRADOS por acuerdo. Comprobación independiente sobre todas las filas candidatas: los pares genérico e inicial son decodificables bajo la hipótesis DDMMSS suroeste y ninguno tiene componente cero. Fuera del recuadro diagnóstico 32–34° S, 71–73° O aparecen una fila de enmalle 2025 y una de espinel 2024 con cada par fuera, y una de espinel 2025 solo para el par inicial. Enmalle 2024 tiene cero. Son conteos por fila. El recuadro diagnóstico no sustituye la geometría aprobada, la máscara costera ni la validación de origen y fecha. Comando sobre Access y diccionarios verificados: `python chile/audit_ifop_candidate_links.py /ruta/privada/gestion_publica`.

**#31/#33 PARCIAL.** El acta 2022 sí menciona enmalle ajustado. En el IT 02/2025 la figura 8 distingue enmalle total y modificado y el texto vincula modificado a la exclusión de Curanipe. La figura 7 identifica espinel Valparaíso. Los rótulos de ambas y el párrafo comparativo no especifican ajuste estadístico ni estandarización. Lectura visual aproximada de figura 8, 2024 y primer semestre 2025 respectivamente: total ≈530 y ≈670 g/m (≈5,0 y ≈5,4 veces 106 y 124), modificado ≈360 y ≈460 g/m (≈3,4 y ≈3,7 veces). Los factores comparan dominios y ventanas distintos. No discriminan diferencias de unidades, denominador, agregado o diseño. [Acta 2022](https://www.subpesca.cl/portal/616/articles-116148_documento.pdf#page=4) y [figuras 7–8 del IT 02/2025](https://www.subpesca.cl/portal/616/articles-128066_documento.pdf#page=9).

**#41 ACEPTADO** en alcance agregado, pendiente de reproducción visual por Claude. El dictamen provisional permanece condicionado. Para evaluar un conjunto unido al ambiente hace falta una referencia comprobable de fecha y posición de faena vinculable al viaje y una definición del marco de muestreo.

## Ronda 16 · Tierra dentro del recuadro y comparación de dominios

**#6/#36 PARCIAL.** Cruce por cotas de los agregados publicados para el par genérico. Natural Earth 1:10 millones marca 28 filas en tierra (7 + 5 + 12 + 4), ocho a más de 5 km. La ronda 15 contabiliza dos filas fuera del recuadro para ese mismo par. Por inclusión, entre 26 y 28 de las filas marcadas en tierra, y entre seis y ocho de las marcadas a más de 5 km tierra adentro, están dentro del recuadro. Son cotas y no un cruce fila a fila. El par inicial requiere su propio contraste. El recuadro es un control de rango y no una máscara marina. El buen encaje bajo DDMMSS tampoco acota todos los formatos alternativos posibles. Procedencia de posición y fecha sigue abierta. [Agregados de costa](ifop_geography_audit.json).

**#31/#33 PARCIAL.** Verifiqué el texto del IT 02/2025: el espinel corresponde a Valparaíso y la comparación de 2025 se refiere al primer semestre. El enmalle modificado excluye Curanipe. Portales es un subconjunto y el cálculo local anterior usa todo el año exportado. La prueba queda definida para separar dominio y estimador: con los filtros de peso y esfuerzo de la ronda 14, comprobar primero el código de Curanipe en el catálogo del anexo, conservar el puerto en la clave al extender el dominio y calcular por período y dominio tanto 1000·Σpeso/Σmetros como la media de 1000·peso/metros. Reportar número de claves y percentiles 5, 50 y 95 de metros. Usar 2024 y el primer semestre registrado de 2025, con Portales, todos los puertos disponibles y sin Curanipe cuando el código esté verificado. Una coincidencia no identifica por sí sola el estimador ni la fuente del campo oficial. En esta revisión el entorno de ejecución no estuvo disponible y no se recalcularon microdatos. [Informe oficial, páginas PDF 9–10](https://www.subpesca.cl/portal/616/articles-128066_documento.pdf#page=9).

**#40 CERRADO** el tratamiento diagnóstico de peso nulo, aceptado por ambas partes. La eslora queda como limitación por falta de enlace verificado entre código IFOP y una fuente de eslora. **#41 ACEPTADO** en alcance agregado. La tabla se localiza en la página PDF 9 (impresa 7) y las figuras 7–8 en las páginas PDF 9–10 (impresas 7–8). La revisión visual independiente sigue pendiente.

## Ronda 17 · Cruce exacto con costa y contraste por dominio

**#6/#36 PARCIAL.** Se verificaron los Access contra sus ZIP y se usó Natural Earth 5.1.1 a escala 1:10 millones, con la misma huella y proyección del diagnóstico anterior. Cruce exacto para las 3.615 filas candidatas. En el recuadro hay 28 filas genéricas en tierra generalizada, ocho a más de 5 km, y 30 iniciales en tierra, diez a más de 5 km. Fuera del recuadro, hay dos genéricas fuera de tierra generalizada y tres iniciales, dos fuera de tierra y una fuera de la región de referencia. El resultado respalda mantener las banderas. La distancia del punto de referencia a la costa generalizada no establece el error máximo de esa costa y los conteos no prueban un error de digitación. No se alteraron coordenadas. Sigue pendiente comprobar la fecha y posición de faena.

| Año | Arte | Genérico en tierra dentro (a >5 km) | Inicial en tierra dentro (a >5 km) |
|---|---|---:|---:|
| 2024 | Enmalle | 12 (3) | 12 (3) |
| 2024 | Espinel | 4 (2) | 4 (2) |
| 2025 | Enmalle | 7 (2) | 7 (2) |
| 2025 | Espinel | 5 (1) | 7 (3) |

Reproducción: `python chile/audit_ifop_coast_overlap.py /ruta/privada/gestion_publica /ruta/ne_10m_land.zip`. [Referencia cartográfica](coast_reference_manifest.json).

**#31/#33 PARCIAL.** Se verificó Curanipe = 705 en Maestro Puertos de los dos anexos y se ejecutó la comparación por recalada: 2024 completo y enero–junio de 2025. Se conserva puerto en la clave y se aplican los filtros diagnósticos de la ronda 14. Las columnas de razón, media y mediana están en g/m bajo la interpretación condicional del campo. Los empates en P5 explican por qué su conteo puede superar 5 %.

| Período | Dominio | Claves | Razón de sumas | Media | Mediana | P5/P50/P95 metros | Claves ≤ P5 |
|---|---|---:|---:|---:|---:|---|---:|
| 2024 | Portales | 820 | 105,95 | 105,91 | 98,77 | 405/486/486 | 186 |
| 2024 | Todos | 3.808 | 508,81 | 572,53 | 270,00 | 405/840/1200 | 451 |
| 2024 | Sin Curanipe | 2.838 | 341,96 | 286,15 | 195,14 | 405/840/1200 | 449 |
| 2025 S1 | Portales | 270 | 114,96 | 114,91 | 107,00 | 405/486/486 | 31 |
| 2025 S1 | Todos | 1.572 | 541,43 | 491,70 | 357,14 | 405/1050/1950 | 99 |
| 2025 S1 | Sin Curanipe | 1.175 | 404,60 | 353,31 | 276,92 | 405/840/2080 | 99 |

El dominio explica una parte importante de la brecha respecto a Portales y quitar Curanipe reduce la razón de sumas en ambos años. La razón de sumas para todos y sin Curanipe queda más cerca de las lecturas visuales que la media en las cuatro comparaciones. La coincidencia es parcial y no identifica el estimador oficial ni acredita la medición del esfuerzo. Reproducción: `python chile/audit_ifop_effort_domains.py /ruta/privada/gestion_publica`. [IT 02/2025, PDF pp. 9–10](https://www.subpesca.cl/portal/616/articles-128066_documento.pdf#page=9).

**#40 CERRADO** para peso nulo y eslora como limitación documentada. **#41 ACEPTADO** el alcance agregado, pendiente la lectura visual independiente de la tabla en PDF p. 9. El diagnóstico mantiene viabilidad condicionada para rendimiento nominal por viaje muestreado. El conjunto unido al ambiente sigue sin ser evaluable con los datos verificados.

## Ronda 18 · Estabilidad de largo declarado y ventanas de enmalle

**#42 PARCIAL.** Frecuencias de LONGITUD_RED por clave elegible de enmalle Portales en el año completo. Se usa una fila de merluza por clave, peso positivo en rango y longitud positiva finita. No se publican identificadores. Longitud declarada (conteo):

- 2024: 284 (1), 324 (4), 405 (181), 445 (1), 446 (10), 486 (615), 527 (3), 567 (2), 608 (3).
- 2025: 405 (39), 445 (1), 446 (3), 486 (402), 527 (2), 567 (4), 608 (2).

| Año | Claves | Embarcaciones | Un viaje | Repetidoras constantes | Repetidoras variables | Claves fuera de las modas de su embarcación |
|---|---:|---:|---:|---:|---:|---:|
| 2024 | 820 | 48 | 2 | 23 | 23 | 84 |
| 2025 | 453 | 42 | 6 | 20 | 16 | 26 |

Hay una embarcación con empate modal en 2025. Se consideraron todas sus modas. La concentración en 486 se confirma (75,0 % y 88,7 % de las claves), pero 23 de 46 y 16 de 36 embarcaciones repetidoras cambian de valor. La concentración no prueba que sea un atributo fijo ni que el denominador carezca de información. El origen y la semántica del campo siguen abiertos.

**#31/#33 CORREGIDO** el enunciado comparativo anterior: la razón de sumas queda más cerca que la media en las cuatro comparaciones visuales (desvíos absolutos aproximados de 4,0 %, 5,0 %, 19,2 % y 12,0 %, frente a 8,0 %, 20,5 %, 26,6 % y 23,2 %). La semántica sigue **PARCIAL**. Con las ventanas de recalada, zarpe o lance, los tres cálculos de 2025 S1 arrojan los mismos conteos mensuales y las mismas razones a dos decimales: todos 541,43 y sin Curanipe 404,60. Esto no explica la brecha con la figura. [IT 02/2025, figura 8](https://www.subpesca.cl/portal/616/articles-128066_documento.pdf#page=10).

| Año | Dominio | Claves por mes de recalada, enero a junio |
|---|---|---|
| 2024 | Todos | 386 / 462 / 497 / 314 / 232 / 212 |
| 2025 | Todos | 365 / 249 / 199 / 334 / 242 / 183 |
| 2024 | Sin Curanipe | 338 / 402 / 384 / 180 / 146 / 153 |
| 2025 | Sin Curanipe | 293 / 195 / 153 / 251 / 168 / 115 |

En 2024 el zarpe mueve una clave de febrero a enero frente a recalada, sin cambiar los totales semestrales. Las diferencias de conteos entre años no demuestran faltantes en la publicación. Reproducción desde los Access y catálogos verificados: `python chile/audit_ifop_effort_stability.py /ruta/privada/gestion_publica`.

**#6/#36 ACEPTADO** el cruce exacto con costa generalizada. **PARCIAL** la procedencia de fecha y posición y su precisión. Una costa de mayor detalle serviría para evaluar discrepancia cartográfica, sin establecer por sí sola la exactitud de una posición de faena. **#41 ACEPTADO**, pendiente la revisión visual independiente. El conjunto unido al ambiente sigue sin ser evaluable con los datos verificados.

## Ronda 19 · Relación entre longitud declarada y número de paños

**#42 PARCIAL.** Incluir puerto en la clave mantiene 820 claves elegibles de Portales en 2024 y 453 en 2025. Entre embarcaciones repetidoras, 84 de 818 y 26 de 447 viajes quedan fuera de las modas de su embarcación. En 2025 se admiten ambas modas en el empate. La concentración del denominador se confirma. El porcentaje de variación del g/m atribuible a kg requeriría un cálculo específico.

**#43 PARCIAL.** Se contrastó la retícula de 40,5 m con tolerancia de ±0,5 m y se comparó también con el número de paños realmente informado en cada fila. Los diccionarios del anexo 2024 (filas 32 y 34) y 2025 (filas 31 y 33), hoja Bitácora Enmalle, definen LONGITUD_RED en metros y NUMERO_PANIOS como el número de paños. No explican cómo se obtienen esos campos.

| Año | Dominio | Claves | Largos distintos | Claves en retícula | Ajuste con número de paños informado |
|---|---|---:|---:|---:|---:|
| 2024 | Portales | 820 | 9 | 820 (100 %) | 817 |
| 2025 | Portales | 453 | 7 | 453 (100 %) | 453 |
| 2024 | Todos | 3.808 | 61 | 1.237 (32,5 %) | 1.084 |
| 2025 | Todos | 3.286 | 51 | 610 (18,6 %) | 531 |

Todos los casos elegibles tienen un número positivo de paños. La retícula se confirma en Portales. La relación con los paños observados tiene tres excepciones en 2024. En el agregado de puertos también son frecuentes cocientes longitud/paños de 42, 45, 48 y 65 m. Esto respalda una relación nominal local como hipótesis, sin establecer el proceso de digitación, el esfuerzo ejercido ni una regla general. Conservar ambos campos. La prueba no usa un modelo nulo de mediciones continuas.

Excepciones a la **retícula** en todos los puertos, largo en metros (conteo):

- 2024: 1 (1), 220 (1), 480 (1), 660 (5), 714 (12), 720 (1), 756 (81), 798 (42), 840 (611), 880 (1), 900 (7), 924 (2), 930 (2), 945 (2), 950 (1), 960 (21), 966 (1), 990 (33), 1000 (1), 1008 (6), 1023 (10), 1035 (8), 1050 (224), 1056 (162), 1060 (1), 1070 (3), 1080 (3), 1089 (1), 1095 (1), 1104 (51), 1125 (970), 1152 (56), 1154 (1), 1188 (1), 1200 (116), 1238 (1), 1560 (11), 1625 (2), 1635 (1), 1690 (2), 1755 (1), 1820 (33), 1885 (2), 1950 (33), 2015 (1), 2080 (26), 2145 (4), 2210 (1), 2275 (10), 2340 (3).
- 2025: 504 (2), 630 (1), 660 (4), 672 (12), 714 (1), 756 (19), 798 (78), 820 (2), 825 (4), 840 (676), 880 (1), 924 (26), 966 (10), 990 (34), 1008 (7), 1050 (167), 1056 (75), 1080 (3), 1100 (5), 1104 (18), 1123 (1), 1125 (832), 1152 (100), 1170 (1), 1200 (162), 1210 (1), 1560 (14), 1625 (17), 1690 (7), 1755 (32), 1820 (85), 1885 (2), 1950 (156), 1960 (1), 2015 (4), 2080 (62), 2082 (1), 2210 (2), 2275 (37), 2340 (8), 2600 (6).

**#31/#33 PARCIAL.** Queda corregido también el párrafo original de la ronda 17. La razón de sumas se acerca más que la media a las cuatro lecturas visuales. En 2025, al retirar febrero–marzo, todos los puertos pasan de 541,43 a 545,74 g/m (1.124 claves restantes) y sin Curanipe de 404,60 a 391,13 (827 claves). El cambio acerca ligeramente la primera serie y aleja la segunda de las lecturas aproximadas 670 y 460. La exclusión no explica la brecha. Enero–junio por mes: 569,70 / 471,02 / 606,42 / 524,87 / 517,69 / 580,87 (todos), y 401,66 / 412,82 / 455,30 / 415,10 / 374,82 / 335,78 (sin Curanipe). [Figura 8 del IT 02/2025](https://www.subpesca.cl/portal/616/articles-128066_documento.pdf#page=10).

Reproducción sobre ZIP, Access, catálogos y diccionarios verificados: `python chile/audit_ifop_net_quantization.py /ruta/privada/gestion_publica`.

**#6/#36 PARCIAL.** Fecha y posición verificables siguen siendo el requisito mínimo para evaluar el cruce ambiental. **#41 ACEPTADO** el alcance agregado, con revisión visual independiente pendiente. No cambia el dictamen de viabilidad condicionada para explorar kg por viaje muestreado por arte.

## Ronda 20 · Paños observados y fechas de maniobra

**#42 PARCIAL.** El efecto de añadir puerto a la clave queda CERRADO por acuerdo. En la muestra elegible de Portales, las varianzas muestrales de log(kg), log(metros) y log(g/m) son respectivamente 0,981491, 0,007055 y 0,963921 en 2024, y 0,819671, 0,003206 y 0,815883 en 2025. Las covarianzas log(kg)–log(metros) son 0,012313 y 0,003497. La identidad de la varianza de la diferencia cuadra. La dispersión observada de log(kg) es mayor que la de log(metros). Eso no atribuye una proporción causal de la variación ni certifica el esfuerzo.

**#43 PARCIAL.** Las tres discrepancias locales de 2024 son 405 m con 12 paños (dos claves) y 527 m con 11 paños (una). Ninguna corresponde a 405 m con nueve paños. El cruce aporta evidencia de una relación nominal local, con excepciones preservadas.

**#44 PARCIAL.** La divisibilidad por un módulo no identifica el número de paños. Contraste directo por año en todos los puertos con `abs(LONGITUD_RED − NUMERO_PANIOS × módulo) <= 0.5`:

| Año | Claves | 40,5 m | 42 m | 45 m | 48 m | 65 m |
|---|---:|---:|---:|---:|---:|---:|
| 2024 | 3.808 | 1.084 | 970 | 997 | 400 | 127 |
| 2025 | 3.286 | 531 | 995 | 833 | 353 | 434 |

Los cocientes metros/paños redondeados al entero más próximo usan el redondeo al par en empates (40,5 exacto aparece en 40). Frecuencias:

- 2024: 0 (1), 9 (1), 34 (2), 36 (2), 40 (1.046), 41 (40), 42 (971), 43 (1), 45 (997), 46 (16), 47 (7), 48 (403), 50 (8), 52 (1), 53 (2), 55 (177), 58 (1), 61 (1), 65 (128), 70 (2), 76 (1).
- 2025: 34 (3), 35 (1), 40 (524), 41 (11), 42 (995), 44 (1), 45 (834), 48 (353), 49 (1), 53 (1), 55 (125), 65 (435), 74 (1), 75 (1).

Hay varios cocientes nominales compatibles con los campos observados. Queda pendiente establecer su distribución por puerto y cómo se registran. No se adopta una regla universal ni se normaliza el esfuerzo usando un módulo inferido. Comando sobre ZIP y miembros verificados: `python chile/audit_ifop_net_quantization.py /ruta/privada/gestion_publica`.

**#31/#33 PARCIAL.** Cero filas elegibles de 2025 S1 pierden la clave al controlar duplicados con todo el año. Se acepta el límite algebraico para mezclas que preserven las razones mensuales. No cubre cambios de composición o rendimiento dentro de un mes. La figura 8 rotula g/m, sin identificar el campo de origen ni documentar el cálculo en su pie. [IT 02/2025, página PDF 10](https://www.subpesca.cl/portal/616/articles-128066_documento.pdf#page=10).

**#6/#36 PARCIAL.** Prueba independiente en tablas completas sobre filas con la fecha-hora inicial de la fase por arte (inicio de virado en enmalle y de calado en espinel), FECHA_LANCE y recalada interpretables:

| Año | Arte | Filas con las tres fechas | Lance y maniobra en el mismo día | Recalada y maniobra en el mismo día | Ambas en el mismo día de maniobra | Lance idéntico a recalada, incluida hora |
|---|---|---:|---:|---:|---:|---:|
| 2024 | Enmalle | 976 | 932 | 948 | 923 | 0 |
| 2025 | Enmalle | 811 | 787 | 769 | 767 | 0 |
| 2024 | Espinel | 2.246 | 2.246 | 342 | 342 | 0 |
| 2025 | Espinel | 1.843 | 1.839 | 282 | 282 | 0 |

Son filas, con posibles repeticiones por operación. Todos los campos iniciales no vacíos de la fase elegida pudieron compararse. En espinel, el lance registrado sigue el día de maniobra mucho más que la recalada en este subconjunto. No se traslada a Portales: allí las maniobras están vacías y lance coincide exactamente con recalada en 3.128 de 3.132 claves. El patrón refuerza la necesidad de una fecha independiente para Portales. Comando: `python chile/audit_ifop_maneuver_dates.py /ruta/privada/gestion_publica`.

**#41 ACEPTADO**, pendiente el contraste visual independiente. El conjunto ambiental de Portales permanece sin condición de evaluación.

## Ronda 21 · Paños históricos y longitud de relinga

**#45 RECHAZADO** como interpretación de la norma aplicable a 2024–2025. La Res. Ex. 2.432/2015, numeral 1 letra b, establecía 25 y 35 paños según eslora. La Res. Ex. 957/2023 reemplaza esa misma letra por 1.300 m de relinga superior para eslora menor de 12 m y 1.800 m para eslora igual o superior a 12 m. Por tanto, 25/35 son referencias históricas en este contraste. El recuento por paños es descriptivo y no certifica esfuerzo comparable entre artes, viajes o puertos. [Texto original, PDF p. 2](https://www.subpesca.cl/portal/615/articles-89686_documento.pdf#page=2) · [Modificación, PDF p. 2](https://www.subpesca.cl/portal/615/articles-117875_documento.pdf#page=2) · [Diario Oficial](https://www.diariooficial.interior.gob.cl/publicaciones/2023/04/26/43536/01/2305024.pdf).

**#46 PARCIAL.** Se contaron los umbrales en todo el universo elegible de enmalle, con el mismo filtro y clave con puerto de la ronda 19. La longitud registrada es LONGITUD_RED. El diccionario solo la describe como longitud de red en metros, sin especificar la relinga superior o el paño estirado. Los esquemas de las tablas de enmalle no contienen eslora ni un campo de categoría identificado por nombre.

| Año | Dominio | Claves | 25 paños | 26–35 | >35 | LONGITUD_RED >1.300 | >1.800 |
|---|---|---:|---:|---:|---:|---:|---:|
| 2024 | Todos | 3.808 | 1.311 | 112 | 3 | 130 | 113 |
| 2025 | Todos | 3.286 | 1.179 | 393 | 17 | 437 | 367 |
| 2024 | Portales | 820 | 0 | 0 | 0 | 0 | 0 |
| 2025 | Portales | 453 | 0 | 0 | 0 | 0 | 0 |

En 2025 hay tres claves por encima de 1.800 m que pertenecen a la retícula de 40,5 m y se omitían al contar solo excepciones. La factorización del largo tampoco reproduce el conteo de 25 paños observados. Se mantiene la separación entre dato registrado, hipótesis de armado y aplicación de umbrales. Los conteos no permiten determinar cumplimiento ni escoger paños como sustituto de esfuerzo efectivo.

Desglose de las claves con LONGITUD_RED >1.800 por código de puerto y paños (conteo):

- 2024, puerto 29: 28 (9), 29 (2), 30 (8), 31 (1), 32 (1), 33 (3), 34 (1), 35 (10).
- 2024, puerto 890: 24 (1), 28 (23), 30 (24), 32 (26), 33 (1), 36 (3).
- 2025, puerto 29: 26 (1), 28 (41), 29 (2), 30 (93), 32 (7), 34 (2), 35 (17), 36 (2), 38 (3), 40 (6).
- 2025, puerto 890: 28 (45), 30 (63), 31 (4), 32 (55), 35 (20), 36 (6).

Reproducción sobre los ZIP y miembros Access verificados: `python chile/audit_ifop_net_thresholds.py /ruta/privada/gestion_publica`.

**#42–#44 y #31/#33.** La ronda 20 ya responde las solicitudes de varianzas, excepciones locales, módulos con paños observados y duplicados entre semestres. Sin nueva aceptación de esos puntos. **#6/#36 PARCIAL.** Sigue sin verificarse fecha y posición de faena por viaje. El dictamen ambiental permanece condicionado a esa evidencia.

## Ronda 22 · Fecha diaria de enmalle por viaje y módulos por puerto

**#6/#36 PARCIAL.** Se filtró enmalle con objetivo merluza, se exigió una clave completa de viaje con puerto y se colapsaron repeticiones del mismo par de inicios de calado y virado. Se excluyeron tres claves de 2024 con más de un par distinto. La comparación exige que ambos inicios estén ordenados entre zarpe y recalada. Ninguna de las claves con par único falló ese control.

| Año | Claves objetivo | Con ambos inicios | Con par único y orden válido | Virado y recalada mismo día | Calado y virado mismo día | Horas virado–recalada P5/P50/P95 |
|---|---:|---:|---:|---:|---:|---|
| 2024 | 3.892 | 219 | 216 | 216 | 216 | 2,00 / 2,78 / 3,75 |
| 2025 | 3.321 | 208 | 208 | 208 | 208 | 2,00 / 2,83 / 4,26 |

El puerto 19 aporta 150 y 161 claves y el 705 aporta 66 y 47, respectivamente. Todos los pares incluidos en cada puerto comparten día con la recalada. P5/P50/P95 por puerto: 19, 2,17/2,83/3,68 y 2,17/2,92/4,37 h. Puerto 705, 1,77/2,65/4,05 y 1,90/2,70/3,57 h. Portales aporta cero claves con ambas maniobras.

La recalada es una hipótesis plausible de fecha diaria para evaluar en enmalle de Portales. El contraste observado proviene de dos puertos y de una minoría de claves con información completa. No cuantifica el error local, la fecha UTC ni la posición de faena. Mantener bloqueada la unión ambiental. Comando sobre Access verificados: `python chile/audit_ifop_enmalle_trip_dates.py /ruta/privada/gestion_publica`.

**#44 PARCIAL.** Con 55 m por paño informado ajustan 176 claves en 2024 y 124 en 2025 (±0,5 m de longitud total). La unión de seis módulos cubre 3.754/3.808 y 3.270/3.286 claves (98,6 % y 99,5 %), sin solapamientos observados. Módulo dominante por puerto entre los seis probados y coincidencias:

| Puerto | Módulo m | 2024 | 2025 |
|---|---:|---:|---:|
| 12 | 55 | 176/179 | 124/125 |
| 19 | 42 | 780/781 | 825/831 |
| 23 | 42 | 99/101 | 66/66 |
| 29 | 65 | 37/37 | 193/194 |
| 560 | 40,5 | 817/820 | 453/453 |
| 564 | 40,5 | 267/269 | 78/78 |
| 603 | 42 | 91/91 | 104/104 |
| 702 | 48 | 400/467 | 353/355 |
| 705 | 45 | 968/970 | 833/834 |
| 890 | 65 | 90/93 | 241/246 |

El predominio es descriptivo por puerto de recalada. No identifica el protocolo de medición ni implica que todos los viajes usen el mismo paño. Comando: `python chile/audit_ifop_net_quantization.py /ruta/privada/gestion_publica`.

**CERRADOS por acuerdo**, en su alcance específico: #42 descomposición de varianza (sin inferir preservación del orden de viajes), #43 tres excepciones locales, #45 corrección normativa, #46 conteos y #31/#33 duplicados. **#46 PARCIAL** la referencia física de LONGITUD_RED. No se verificó un manual aplicable que distinga relinga de paño estirado. **#31/#33 PARCIAL.** La brecha con figura 8 sigue sin explicación y no bloquea el análisis descriptivo de kg por viaje. **#41 ACEPTADO** en alcance agregado, con revisión independiente pendiente.

## Avance de ronda 22 · Cobertura de clorofila según fecha candidata

**#17 PARCIAL.** Se cruzaron las 3.132 claves candidatas de los anexos IFOP verificados con los conteos diarios ya reproducidos de GlobColour L3 y L4 en el recuadro técnico. Se usó la fecha registrada de recalada como etiqueta D y se compararon D−1, D y D+1. Son escenarios de sensibilidad, sin asignar huso ni fecha de captura. El indicador es al menos una celda finita en todo el recuadro, sin seleccionar posición pesquera ni evaluar asociación con capturas. [Censo diario](arco_coverage_2024_2025.json) · [Catálogo L3 de Copernicus](https://data.marine.copernicus.eu/product/OCEANCOLOUR_GLO_BGC_L3_MY_009_107/description).

| Año | Arte | Claves | L3 D−1 | L3 D | L3 D+1 | L3 los tres días | L3 ningún día | Ventana incompleta en el censo |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 | Enmalle | 875 | 825 | 806 | 804 | 720 | 3 | 0 |
| 2024 | Espinel | 528 | 497 | 496 | 488 | 442 | 4 | 0 |
| 2025 | Enmalle | 476 | 432 | 436 | 425 | 373 | 0 | 9 |
| 2025 | Espinel | 1.253 | 1.108 | 1.037 | 1.024 | 791 | 0 | 3 |
| Total | Ambos | 3.132 | 2.862 | 2.775 | 2.741 | 2.326 | 7 | 12 |

Entre las 3.120 claves con ventana completa, 787 tienen L3 finito en alguna fecha pero no en las tres. En 350 claves con ventana completa, L3 falta en D y aparece en un día vecino. L4 tiene al menos una celda finita en los tres días para las 3.120 ventanas completas. En las 12 restantes, D+1 está fuera del censo 2024–2025. Este techo de cobertura regional no garantiza observación óptica directa ni cobertura de la celda de faena. Se mantienen separadas las tres fechas, sin rellenar D con un vecino. Para un contraste futuro de clorofila se requiere una posición de faena y una regla temporal respaldadas, con el estado de cobertura conservado por clave y escenario.

Reproducción desde la raíz: `python chile/audit_candidate_chl_date_sensitivity.py /ruta/privada/gestion_publica chile/research_2026_11_04/arco_coverage_2024_2025.json`.

**#6/#36 PARCIAL.** La sensibilidad de disponibilidad no valida la recalada como fecha de faena ni identifica una posición. El conjunto combinado sigue sin ser evaluable con la evidencia actual.

## Ronda 23 · Selección de viajes y cobertura regional de clorofila

**#6/#36 PARCIAL.** Reejecución sobre Access verificados, enmalle con objetivo merluza, clave completa por viaje y puerto. Las 216 y 208 claves de los puertos 19 y 705 con un par único y orden válido de maniobras son todas viajes de un mismo día registrado. En ese subconjunto la coincidencia de día entre maniobra y recalada se deduce del filtro de orden. Cero viajes de varios días entran en esa comparación. En todo el extracto objetivo de enmalle (3.892 y 3.321 claves completas), se observaron cero claves con calado interpretable anterior al zarpe, y cero con algún virado interpretable pero ningún calado interpretable. Sin embargo, solo 219 y 208 claves tienen ambos inicios interpretables en al menos una fila, y ninguna es de Portales. Los ceros describen el registro disponible y no excluyen que una red quede calada entre viajes.

En Portales, el intervalo zarpe–recalada acota el día **si la faena está dentro del intervalo**. D y D−1 son los escenarios biológicos prioritarios bajo reloj común y recalada posterior a la faena. D+1 se conserva como control de desplazamiento, sin interpretación de huso para estas claves (ver ronda 24). D+1 no representa faena posterior a la recalada. Sigue faltando una posición de faena verificable por viaje y la evidencia local para trasladar el supuesto de intervalo. Reproducción: `python chile/audit_ifop_enmalle_trip_dates.py /ruta/privada/gestion_publica`.

**#17 PARCIAL.** Además de alguna celda finita, se exigieron 64 celdas L3 finitas en el recuadro, un umbral diagnóstico equivalente a la mitad del conteo fijo L4. No supone que esas celdas sean las mismas que el soporte L4 ni que cubran una posición de faena.

| Año | Arte | Claves | L3 ≥64 D−1 | L3 ≥64 D | L3 ≥64 D+1 | Los tres | Ninguno | Ventanas mixtas | Fuera del eje |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 | Enmalle | 875 | 575 | 580 | 600 | 308 | 45 | 522 | 0 |
| 2024 | Espinel | 528 | 343 | 372 | 386 | 232 | 49 | 247 | 0 |
| 2025 | Enmalle | 476 | 302 | 301 | 284 | 177 | 53 | 237 | 9 |
| 2025 | Espinel | 1.253 | 888 | 785 | 761 | 392 | 42 | 816 | 3 |
| Total | Ambos | 3.132 | 2.108 | 2.038 | 2.031 | 1.109 | 189 | 1.822 | 12 |

En D, el umbral reduce el conteo regional de 2.775 a 2.038 claves. L4 gap-free es un producto interpolado y en el censo mantiene 128 celdas finitas por fecha. Su conteo sirve como control de disponibilidad del producto y no mide observaciones ópticas directas. [Catálogo L4 de Copernicus](https://data.marine.copernicus.eu/product/OCEANCOLOUR_GLO_BGC_L4_MY_009_104/services) · [Censo diario](arco_coverage_2024_2025.json). Reproducción: `python chile/audit_candidate_chl_date_sensitivity.py /ruta/privada/gestion_publica chile/research_2026_11_04/arco_coverage_2024_2025.json`.

**#44 CERRADO** como descriptor declarado por puerto, con acuerdo de Claude. Los alcances ya cerrados de #42, #43, #45, #46 y #31/#33 se mantienen. #41 sigue **ACEPTADO** en alcance agregado. El dictamen provisional permite explorar kg por viaje muestreado y arte. Los datos verificados siguen sin permitir evaluar el cruce pesquero con el ambiente.

## Ronda 24 · Control de calendario y cobertura en D−1/D

**#47 ACEPTADO** el resultado bajo las convenciones ensayadas. Se releyeron las 3.132 claves IFOP y se aplicaron 0, +3 y +4 h a cada extremo. Cero cambios de día en zarpe y recalada con cada desplazamiento. Si ambos campos usan una de esas convenciones y la faena está contenida en el intervalo de un solo día, su fecha UTC queda acotada. El cálculo no acredita el huso del origen ni el supuesto de faena dentro del viaje. La conversión desde un reloj UTC+k (k positivo) restaría horas y podría mover una fecha hacia D−1, no D+1. D+1 queda rotulado como control de desplazamiento fuera de las hipótesis de faena ensayadas. No es un control causal: el ambiente puede estar autocorrelacionado. El QUID GlobColour, versión 7.0, sección II.5.3, explica que la etiqueta de un producto global diario reúne observaciones de aproximadamente 00:00 a 23:59 UTC del día indicado, con la salvedad de la composición global. [Manual de calidad](https://documentation.marine.copernicus.eu/QUID/CMEMS-OC-QUID-009-101to104-111-113-116-118.pdf) · [Hora oficial, SHOA](https://www.directemar.cl/cambio-de-hora-en-chile-continental-e-insular-occidental).

**#17 PARCIAL.** Con ≥64 celdas L3 finitas, el par (D−1,D) tiene eje completo para las 3.132 claves:

| Año | Arte | Ambas fechas | Ninguna | Cambia de estado |
|---|---|---:|---:|---:|
| 2024 | Enmalle | 394 | 114 | 367 |
| 2024 | Espinel | 278 | 91 | 159 |
| 2025 | Enmalle | 218 | 91 | 167 |
| 2025 | Espinel | 581 | 161 | 511 |
| Total | Ambos | 1.471 | 457 | 1.204 (38,4 %) |

Como paso independiente, se desglosó el umbral en D por estado de captura registrado: 1.954/2.998 claves con merluza positiva, 16/20 con peso cero explícito de merluza, 45/83 con código 999 y peso cero, 22/30 con objetivo no listado y 1/1 con conflicto 999 y peso positivo. Es una comparación descriptiva ponderada por claves, con grupos pequeños. No se imputaron ceros ni se atribuyeron diferencias a nubosidad o captura. La disponibilidad regional puede cambiar la composición de una muestra filtrada. El umbral regional no demuestra cobertura en la posición de faena.

Reproducción sobre los Access verificados y el [censo fijado](arco_coverage_2024_2025.json): `python chile/audit_candidate_chl_date_sensitivity.py /ruta/privada/gestion_publica chile/research_2026_11_04/arco_coverage_2024_2025.json`.

**#6/#36 CERRADO** el subpunto de la coincidencia automática en la muestra de otros puertos con viajes de un solo día. La procedencia de fecha y posición en Portales sigue **PARCIAL**. El dictamen provisional permite explorar kg por viaje muestreado y arte. Falta una referencia de fecha y posición de faena vinculable a las claves para evaluar el cruce ambiental.

## #17 PARCIAL. Clorofila L3 en la celda de referencia de Portales

Entre 2024 y 2025 hubo 639 de 731 días con algún valor finito en el recuadro y 546 en la celda pública de referencia. Por inclusión, hubo 93 días con dato regional y sin dato en esa celda costera mixta.

De 3.132 claves candidatas de IFOP, 2.775 tienen cobertura regional en su fecha registrada de retorno. Para acotar cuántas pudieron tener soporte en la celda, se cuentan las claves por fecha y se suman los 546 menores o mayores pesos entre los 639 días elegibles. El resultado, **1.654–2.775**, es una cota conservadora con estos agregados. Los extremos de cada estrato pueden corresponder a calendarios diferentes. El censo por celda no identifica los días concretos y la celda de referencia no representa ubicaciones de faena. La lectura de esa ronda excedió el tiempo de espera. La ronda 26 presenta el recuento directo.

```bash
python chile/audit_candidate_port_pixel_bounds.py /ruta/privada/gestion_publica \
  chile/research_2026_11_04/arco_coverage_2024_2025.json \
  chile/research_2026_11_04/arco_cell_support.json
```

[Cotas originales](https://github.com/ywarthonv-source/predictamar-litoral/blob/9ae926e608183cc1ff7796585cf6d3b41eb23105/chile/research_2026_11_04/candidate_port_pixel_bounds.json).

## #48 PARCIAL. Disponibilidad regional según mes y estado de captura

De las 83 claves con código 999 y peso cero, 45 cumplen el umbral regional L3 ≥64 en la fecha registrada de retorno. Si a cada mes se aplica la proporción observada en las claves positivas de ese mismo mes, se esperan 55,12 de 83, frente a 54,10 usando la proporción positiva global (1.954/2.998). El ajuste descriptivo por mes del año, agrupando 2024 y 2025, no explica la diferencia observada. La unidad del indicador ambiental es el día y varias claves pueden compartirlo. El cálculo no establece significancia, sesgo causal ni un efecto de nubosidad. Queda por contrastar año, arte y dependencia por fecha.

Reproducción: `python chile/audit_candidate_chl_month.py /ruta/privada/gestion_publica chile/research_2026_11_04/arco_coverage_2024_2025.json`. [Tabla mensual](candidate_chl_month_audit.json).

## Ronda 26. Cobertura diaria en la celda pública y agrupación por fecha

**#17 PARCIAL.** Los dos censos coinciden en 62.568 celdas-día finitas L3 y registran cero valores finitos L3 fuera de las 128 celdas con soporte fijo L4. Los 333 días con las 128 celdas finitas garantizan cobertura en la referencia pública. De los 306 días con cobertura parcial, la referencia tiene dato en 213. Al fijar esos 333 días y ordenar los pesos por fecha de retorno en los otros 306, la cota total mejora a 1.661–2.775 claves. [Cotas por estrato](candidate_port_pixel_bounds.json).

La nueva lectura de ARCO reprodujo el total regional de cada uno de los 731 días y los 546 días finitos en la celda (fila 6, columna 11). En la fecha de retorno registrada, **2.399/3.132** claves coinciden con L3 finita en la celda, frente a **2.775/3.132** con L3 en cualquier celda del recuadro. La diferencia es de 376 claves. Esto evalúa disponibilidad en una celda costera de referencia. Para asociar ambiente y captura todavía se requiere posición y fecha de faena verificables. [Máscara ambiental pública, hashes y conteos agregados](candidate_port_pixel_daily.json). [Ficha de Copernicus](https://data.marine.copernicus.eu/product/OCEANCOLOUR_GLO_BGC_L3_MY_009_103/services).

**#48 PARCIAL.** Las 83 claves 999 con peso cero ocupan 59 fechas de retorno. 57 de esas fechas y 80 de esas claves coinciden con al menos una clave positiva. La diferencia de −10,96 puntos porcentuales en el umbral regional también refleja pesos distintos de fechas compartidas. Una permutación exploratoria de etiquetas de cobertura entre fechas muestreadas dentro de cada año y mes, conservando juntas las claves del día, dio p unilateral 0,0443 (20.000 permutaciones, semilla 20261105). La dirección se examinó tras observar la diferencia y el ejercicio supone fechas intercambiables dentro de cada estrato. No controla autocorrelación ni separa arte. En el esquema de las cuatro tablas artesanales no se identificó un campo explícito de viento, meteorología, oleaje o motivo de no captura. La hipótesis de mal tiempo sigue sin verificar. [Diagnóstico original por fecha](https://github.com/ywarthonv-source/predictamar-litoral/blob/969be2580a49d9f80185e4e69ce724216b72048d/chile/research_2026_11_04/candidate_chl_date_clusters.json).

**#47 ACEPTADO** el respaldo documental de la etiqueta diaria. La sección II.5.3 del QUID GlobColour v7.0, p. 27, da el ejemplo de un día global que reúne observaciones aproximadamente entre las 00:00 y las 23:59 UTC. Es la convención del producto y no certifica la hora de faena. [QUID, p. 27](https://documentation.marine.copernicus.eu/QUID/CMEMS-OC-QUID-009-101to104-111-113-116-118.pdf#page=27).

Reproducción de los nuevos diagnósticos con los Access verificados, NumPy, pandas, numcodecs y mdb-export:

```bash
python chile/audit_candidate_port_pixel_daily.py /ruta/privada/gestion_publica \
  chile/research_2026_11_04/arco_coverage_2024_2025.json chile/research_2026_11_04/arco_cell_support.json
python chile/audit_candidate_chl_date_clusters.py /ruta/privada/gestion_publica \
  chile/research_2026_11_04/arco_coverage_2024_2025.json chile/research_2026_11_04/candidate_port_pixel_daily.json
```

## Ronda 27. Cruce con tablas auxiliares y contraste bilateral

**#6/#36 PARCIAL.** Se reexportaron las diez tablas auxiliares presentes en los Access artesanales verificados de 2024 y 2025. El cruce exacto exige mismo año, código de embarcación, marcas de zarpe y recalada, código de pesquería y puerto de recalada 560. Se prueban por separado coincidencias con la misma clave y otro puerto o puerto vacío. Se comparan conjuntos de días de lance parseados y pares de coordenadas completos según sus valores exportados, por clave de viaje.

En 2024 ninguna tabla auxiliar tiene filas con recalada 560. En 2025, LONGITUD aporta 337 filas y 13 claves coincidentes (8 de enmalle y 5 de espinel). Los 13 días de lance ya están en la bitácora principal y la tabla carece de pares de coordenadas. COMERCIALIZACIÓN aporta 1.694 claves coincidentes (466 y 1.228), sin campos de día de lance ni posición. CIAMT, IOE, BIOLOGICO y PRESENCIA de 2025 no tienen filas con recalada 560. Ninguna tabla de los dos años aporta coincidencia exacta con otro puerto o puerto vacío. El alcance se limita a enlaces exactos en estas tablas. No se examinó enlace aproximado, ni la coincidencia de valores demuestra independencia de fuentes. [Conteos agregados por tabla](ifop_auxiliary_links_audit.json).

El informe de seguimiento IFOP 2025, §4, p. 10 impresa (16 del PDF), describe observadores embarcados y en lugares de desembarque. Ese marco no identifica por clave el origen de la fecha ni de la posición de faena. Sigue faltando una referencia de faena con fecha y posición vinculables a las claves de Portales. [Informe oficial](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-581228_Seccion_II_Pesqueria_centro_sur.pdf#page=16).

**#17 CERRADO** el recuento de cobertura en la celda de referencia por aceptación mutua. El recuento mensual por día confirma diferencias estacionales, con 32/60 días finitos en junio y 54/62 en enero. La cercanía entre cobertura por claves y por días en el total no prueba que las claves sean representativas por mes o arte. El soporte en la posición de faena sigue abierto bajo #6/#36.

**#48 PARCIAL.** Se repitió la permutación agrupada por fecha dentro de año y mes sobre los Access verificados. La cola bilateral usa distancias absolutas al centro exacto de la distribución nula condicionada, calculado con los pesos y la fracción de días cubiertos de cada estrato. En el criterio regional p bilateral = 0,0891. En la celda pública coinciden 56/83 claves 999 y 2.301/2.998 positivas (−9,28 puntos), p bilateral = 0,3440. Ambos son contrastes exploratorios, sin estratificar por arte ni modelar dependencia serial. La evidencia no permite afirmar una diferencia de cobertura por estado de captura. [Agregados, cobertura mensual y semilla](candidate_chl_date_clusters.json).

**#47 PARCIAL** en la comprobación independiente de la fuente. Extracto de §II.5.3, p. 27, del QUID v7.0: “The product named with the date 2019-04-28 is a collection of data approximately collected between 2019-04-28 at 00:00 UTC and 23:59 UTC.” [Manual oficial](https://documentation.marine.copernicus.eu/QUID/CMEMS-OC-QUID-009-101to104-111-113-116-118.pdf#page=27). El subpunto de huso se mantiene cerrado.

```bash
python chile/audit_ifop_auxiliary_links.py /ruta/privada/gestion_publica
python chile/audit_candidate_chl_date_clusters.py /ruta/privada/gestion_publica \
  chile/research_2026_11_04/arco_coverage_2024_2025.json chile/research_2026_11_04/candidate_port_pixel_daily.json
```

## Ronda 28. Posicionamiento satelital público como fuente de contraste

**#6/#36 y #40 PARCIAL.** Se descargaron dos CSV de la sección Flota Artesanal del catálogo de posicionamiento de Sernapesca, etiquetados 19-06-2024 y 18-06-2025. Se ensayó un reporte de junio por temporada como prueba acotada de acceso y esquema. El primero contiene 8.221 posiciones entre el 18 y el 19 de junio, 70 dentro del recuadro diagnóstico. El segundo contiene 44.613 del 18 de junio, 276 dentro del recuadro. Estos conteos son reportes de posición, sin atribución a Portales ni a operaciones. [Catálogo oficial](https://www.sernapesca.cl/informacion-utilidad/posiciones-geograficas-del-sistema-de-posicionamiento-satelital/). [CSV 2024](https://www.sernapesca.cl/app/uploads/2024/06/report_31_20240619_flota_artesanal.csv). [CSV 2025](https://www.sernapesca.cl/app/uploads/2025/08/report_31_20250618_flota_artesanal.csv).

El CSV 2024 trae distintivo de llamada. El de 2025 trae `call_sign` e `internal_ref`. Al cotejar esas cadenas (mayúsculas y espacios exteriores normalizados) con los códigos IFOP de todos los candidatos de la temporada correspondiente, hubo cero coincidencias en ambos artes y muestras. La fecha etiquetada de 2024 tiene cero recaladas candidatas. La de 2025 tiene 12 (2 enmalle, 10 espinel). El diccionario artesanal identifica `COD_BARCO` como código IFOP (ronda 13); no se encontró una equivalencia pública documentada con los identificadores de estos CSV. La coincidencia de fechas o el formato del código no permiten identificar una embarcación. [Columnas, hashes y conteos por arte](sernapesca_vms_linkage_audit.json).

La fuente demuestra que se pueden descargar trayectorias históricas de una parte de la flota artesanal. Estos dos archivos no demuestran cobertura de los candidatos, ni tienen campos de lance, arte, especie o captura. Una trayectoria vinculada serviría para contrastar desplazamiento y horario, y haría falta una referencia adicional para distinguir la maniobra y atribuirle la captura. La posición y la fecha de faena siguen sin verificar en el conjunto candidato. [Descripción oficial del reporte básico](https://www.sernapesca.cl/preguntas-frecuentes/sistema-de-posicionamiento-satelital/).

Reproducción con ambos CSV guardados como `vms_2024.csv` y `vms_2025.csv` en un directorio privado y los anexos IFOP verificados:

```bash
python chile/audit_sernapesca_vms_linkage.py /ruta/privada/gestion_publica /ruta/privada/vms
```

## Ronda 29. Serie histórica de Portales, ASIPA 2010–2022

**#6/#36 PARCIAL.** Se incorpora una serie histórica separada de las bitácoras IFOP 2024–2025, por instrucción de Randy. El cálculo relee el ZIP ASIPA 1.5 con SHA-256 comprobado, selecciona localidad PORTALES del bloque de captura 14-01 y cuenta cada identificador de evento una vez por especie, con estado exclusivamente `present`. El año proviene de los componentes de fecha. En todos los eventos incluidos, el día coincide con el de `eventDate`. La coincidencia interna no valida la fecha ni la posición de faena.

| Año | Merluza común | Reineta |
|---|---:|---:|
| 2010 | 661 | 0 |
| 2011 | 1158 | 32 |
| 2012 | 1315 | 65 |
| 2013 | 1301 | 20 |
| 2014 | 1375 | 0 |
| 2015 | 1293 | 0 |
| 2016 | 1138 | 0 |
| 2017 | 1270 | 4 |
| 2018 | 1502 | 29 |
| 2019 | 1496 | 18 |
| 2020 | 1135 | 9 |
| 2021 | 1150 | 24 |
| 2022 | 1244 | 35 |
| **Total** | **16.038** | **236** |

Un cero en la tabla indica que el extracto no contiene eventos positivos para esa especie y año. No representa ausencia biológica ni viaje sin captura. Los conteos no son operaciones independientes, esfuerzo ni toneladas. La serie se publica como [agregados anuales por especie y arte declarado en el nombre del conjunto](asipa_portales_history_2010_2022.json), separada del inventario IFOP. La ficha ASIPA indica CC BY-NC 4.0. [Fuente y licencia](https://gbif-chile.mma.gob.cl/ipt/resource?r=asipa_demersales&v=1.5).

Reproducción con el ZIP conservado en una ruta privada: `python chile/audit_asipa_portales_history.py /ruta/privada/asipa_demersales_1_5.zip`. Sigue pendiente determinar qué eventos tienen fecha y posición de faena verificables antes de un cruce ambiental.

## Ronda 30. Procedencia y concentración espacial del histórico ASIPA

**#49 PARCIAL.** Se releyó el ZIP original con SHA-256 verificado. El filtro por subcadena solo selecciona el valor exacto `PORTALES` en el bloque 14-01 para ambos objetivos. `samplingProtocol` está vacío en todos los incluidos. Se usa `datasetName` para distinguir las encuestas de enmalle y espinel. Esta etiqueta identifica el conjunto declarado y no acredita el método de georreferenciación de un evento.

| Año | Merluza enmalle | Merluza espinel | Reineta enmalle | Reineta espinel |
|---|---:|---:|---:|---:|
| 2010 | 661 | 0 | 0 | 0 |
| 2011 | 1148 | 10 | 0 | 32 |
| 2012 | 1239 | 76 | 0 | 65 |
| 2013 | 827 | 474 | 0 | 20 |
| 2014 | 893 | 482 | 0 | 0 |
| 2015 | 1199 | 94 | 0 | 0 |
| 2016 | 928 | 210 | 0 | 0 |
| 2017 | 253 | 1017 | 0 | 4 |
| 2018 | 175 | 1327 | 0 | 29 |
| 2019 | 28 | 1468 | 0 | 18 |
| 2020 | 490 | 645 | 0 | 9 |
| 2021 | 874 | 276 | 4 | 20 |
| 2022 | 837 | 407 | 1 | 34 |
| Total | 9.552 | 6.486 | 5 | 231 |

En merluza, 43 de 646 pares concentran al menos la mitad de los 16.038 eventos y 186 concentran al menos el 90 %. Por fecha registrada son 711 y 1.527 de 1.946 días. En reineta son 34 y 119 de 142 pares, y 23 y 70 de 93 días. Los umbrales ordenan las frecuencias de mayor a menor y toman el primer recuento que alcanza la proporción. Los cuatro campos consultados (`coordinateUncertaintyInMeters`, `coordinatePrecision`, `georeferenceRemarks`, `footprintWKT`) no existen en la tabla Event del ZIP. La repetición es compatible con posiciones redondeadas o referencias reutilizadas, entre otras causas. El análisis no distingue esas hipótesis. Con la evidencia disponible todavía no se ha acreditado ningún evento con fecha y posición de faena verificadas para un cruce a resolución de celda. Esto no descarta que existan operaciones recuperables. [Agregados y diagnóstico](asipa_portales_history_2010_2022.json). Reproducción: `python chile/audit_asipa_portales_history.py /ruta/privada/asipa_demersales_1_5.zip`.

**#6/#36 y #40 PARCIAL.** El art. 64 B confirma que la obligación de posicionador incluye la flota artesanal de 15 m o más y, de 12 a menos de 15 m, la inscrita en cerco pelágico. Los recursos bentónicos tienen disposición aparte. La FAQ describe el reporte básico como posición, rumbo y velocidad de la nave. La regla no identifica esloras ni cobertura de Portales. Incluso si se confirma una nave con posicionador, faltan una equivalencia de códigos y una referencia del lance para asociar captura. El rastreo queda como vía complementaria, sin prioridad sobre una fuente de operación vinculable. [Ley, art. 64 B](https://www.bcn.cl/leychile/navegar?idNorma=13315&idVersion=2026-11-01). [Sernapesca, descripción del reporte](https://www.sernapesca.cl/preguntas-frecuentes/sistema-de-posicionamiento-satelital/).

**#48 ACEPTADO** el resultado no concluyente. En la celda el centro nulo estratificado es −3,73 puntos y el contraste observado es −9,28, a 5,55 puntos por debajo del centro. Esto cuantifica la parte compatible con la composición temporal bajo el contraste, sin atribución causal al calendario o nubosidad. [Agregados reproducibles](candidate_chl_date_clusters.json).

## Ronda 31. Resolución publicada y procedencia de las posiciones ASIPA

**#49 PARCIAL.** Sobre el ZIP verificado se clasificaron los pares numéricos únicos de merluza con ambos ejes dentro de una tolerancia de 0,0001° de la rejilla. Las categorías son excluyentes. El resultado es idéntico con 0,000001°. Los estratos pueden compartir pares.

| Estrato | Minuto entero | Décima de minuto solamente | Fuera de ambas rejillas |
|---|---:|---:|---:|
| all | 624 | 3 | 19 |
| Encuesta Pesq DCS/DSA Art Espinel · 2017–2022 | 426 | 1 | 6 |
| Encuesta Pesq DCS/DSA Art Espinel · 2010–2016 | 169 | 1 | 1 |
| Encuesta Pesqueria Enmalle · 2010–2016 | 424 | 1 | 8 |
| Encuesta Pesqueria Enmalle · 2017–2022 | 348 | 0 | 5 |

624/646 pares (96,6 %) son compatibles con minutos enteros. Al contar por evento, los decimales efectivos de la representación, tras quitar ceros finales, son 0, 1, 2 o 13 en ambos ejes. Trece decimales de salida no equivalen a precisión de medición. La rejilla es evidencia del redondeo o formato de los valores publicados, sin identificar instrumento, método de captura ni incertidumbre. [Agregados por estrato y eje](asipa_portales_history_2010_2022.json). Reproducción: `python chile/audit_asipa_portales_history.py /ruta/privada/asipa_demersales_1_5.zip`.

La tabla 8 de FIPA 2024-02 identifica bitácoras de embarque o encuestas en tierra para viajes artesanales de enmalle y espinel. La p. 64 impresa describe la interpretación de ciertos formatos como grados y minutos sin segundos, sin asignarla específicamente a Portales. El EML incluido en el ZIP verificado (SHA-256 `0664827fa2ad3ee1a54d83e970adb0f3ea14c6e839e8faba8a811368ad236635`, `methods/sampling/samplingDescription`) dice que las coordenadas se asignan según los lances reportados por observadores, con variaciones por antigüedad o formato. Es evidencia de la unidad que el recurso pretende representar. No discrimina por evento de Portales observación a bordo, entrevista u otra asignación. Todavía falta una referencia enlazable que confirme procedencia, fecha de operación e incertidumbre. [FIPA, tabla 8](https://www.subpesca.cl/fipa/613/articles-122024_informe_final.pdf#page=40). [FIPA, p. 64 impresa](https://www.subpesca.cl/fipa/613/articles-122024_informe_final.pdf#page=69). [Ficha ASIPA 1.5 y EML](https://gbif-chile.mma.gob.cl/ipt/resource?r=asipa_demersales&v=1.5).

**#49b ACEPTADO** como advertencia de interpretación. El cambio entre 2015 (1.199 enmalle, 94 espinel) y 2019 (28 y 1.468) es un cambio en la composición de los eventos publicados por etiqueta de encuesta. No acredita por sí solo un cambio de actividad ni un cambio deliberado de diseño. Mantener el desglose por año y arte y tratar la causa como hipótesis. [Tabla anual](asipa_portales_history_2010_2022.json).

## Ronda 32. Rejillas ponderadas por evento y dictamen provisional

**#50 PARCIAL.** Reejecución sobre ZIP ASIPA 1.5 verificado. Cada evento se asigna una sola vez por eje o par al paso más grueso compatible con los valores publicados. Tolerancia 0,000001° por eje. Para el par se exige el mismo paso en ambos ejes.

| Unidad | 1° | 6′ | 3′ | 1′ | 0,1′ | Fuera |
|---|---:|---:|---:|---:|---:|---:|
| Latitud | 769 | 1360 | 3048 | 10846 | 1 | 14 |
| Longitud | 3 | 3138 | 3593 | 9292 | 2 | 10 |
| Par | 1 | 209 | 1471 | 14334 | 3 | 20 |

El patrón de 3′ o más grueso abarca 5.177 latitudes, 6.734 longitudes y **1.681 de 16.038 pares por evento (10,5 %)**. Los 769 eventos de latitud entera se reparten entre tres valores (767, 1 y 1). El máximo número de longitudes distintas para una latitud entera es 21. Los tres casos de longitud entera comparten un solo valor. Se omiten los valores de coordenadas. Los pasos son divisibilidades observadas, compatibles también con una rejilla más fina que contiene esos puntos. No demuestran redondeo deliberado a pasos distintos, precisión real ni relleno. La hipótesis de valores por defecto sigue sin verificar. [Agregados por eje, arte y periodo](asipa_portales_history_2010_2022.json). Reproducción: `python chile/audit_asipa_portales_history.py /ruta/privada/asipa_demersales_1_5.zip`.

**#49 PARCIAL.** La p. 22 impresa de FIPA 2024-02 enuncia seis decimales en la sección general de estandarización de cabeceras, con referencia a la Res. Ex. 34/2023. El ZIP examinado conserva valores de 13 decimales efectivos. La documentación consultada no explica la diferencia para esta versión del recurso. La combinación de valores largos y compatibilidad con minutos enteros apoya la hipótesis de conversión sexagesimal, sin identificar el origen de medición o el flujo de exportación. [FIPA, §4.1.5.1](https://www.subpesca.cl/fipa/613/articles-122024_informe_final.pdf#page=27). **#49b CERRADO** por acuerdo en la advertencia de composición de encuestas.

### Dictamen provisional con las fuentes verificadas

| Vía | Alcance hoy | Dato faltante |
|---|---|---|
| ASIPA Portales | Presencias declaradas por año y arte. | Llave a un registro de operación que confirme fecha, posición y procedencia de cada enlace. |
| Anexos artesanales IFOP 2024–2025 | Análisis descriptivo de kg reportados por viaje candidato muestreado y arte. Hay 3.132 claves candidatas y 2.998 cantidades positivas. | Fecha y posición de faena ligadas a la clave y marco de muestreo. Para comparar estados o normalizar por esfuerzo se requieren además ceros interpretables y esfuerzo comparable. |
| Cruceros IFOP | Evidencia biológica regional de arrastre científico. Los 32 lances del recuadro resultaron positivos para merluza. | Diseño que permita evaluar el objetivo artesanal acordado. |
| Copernicus | Cobertura ambiental verificable. 2.399 claves con clorofila L3 en la celda pública el día de recalada. | Enlace a una posición de operación verificable y una fecha compatible con el producto. |

El conjunto unido al ambiente por faena sigue **sin ser evaluable con la evidencia reproducida**. Para probar el enlace mínimo hace falta un subconjunto trazable de operaciones del mismo alcance, con identificador de viaje y lance, fecha con convención horaria, posición con método e incertidumbre y vínculo con la captura. IFOP es una posible fuente por su rol de recopilación. La disponibilidad y el permiso comercial siguen pendientes. Este dictamen está sujeto a revisión de Claude.

## Ronda 33. Dictamen por alcance y contraste de latitudes vecinas

**#50 CERRADO** en el alcance acordado. La compatibilidad aritmética con 3′ o múltiplos más gruesos no acredita un paso de captura distinto de 1′ ni una precisión de medición. Las referencias uniformes e independientes son ilustrativas. No constituyen un modelo del muestreo local.

**#50b PARCIAL.** Reejecución sobre el ZIP verificado, con tolerancia de 0,000001° por latitud. Los 767 eventos de la latitud entera dominante se compararon con los conteos en −3′, −2′, −1′, +1′, +2′ y +3′: 1.278, 840, 1.164, 574, 529 y 614. El cociente es 0,921 frente a la media de las seis filas. No se observa un exceso respecto a esa media local. Este control no identifica si hubo relleno ni corrige diferencias de esfuerzo o geografía. [Agregados](asipa_portales_history_2010_2022.json). Reproducción: `python chile/audit_asipa_portales_history.py /ruta/privada/asipa_demersales_1_5.zip`.

**#51 ACEPTADO** el dictamen por alcance, con una distinción entre disponibilidad ambiental comprobada y concentración lista para analizar:

| Alcance | Dictamen |
|---|---|
| Viaje candidato × arte × día de recalada × celda fija de Portales | **Viable condicionado, exploratorio.** El enlace por fecha con la máscara ambiental es reproducible. De 3.132 claves, 2.399 coinciden con clorofila L3 finita y 2.301 de las 2.998 claves de captura positiva están en esa intersección. El derivado conserva la máscara de disponibilidad y agregados, no los valores diarios de concentración. Para una asociación descriptiva hay que extraer los valores diarios de la misma celda y producto, verificar su máscara contra los 731 días publicados (546 finitos) y conservar el arte y la fecha como unidades de agrupación. El análisis se refiere a la celda costera el día de recalada. |
| Cruce ambiental por faena, presencia/ausencia y CPUE estricta | **No viable con los datos verificados.** Falta fecha y posición de faena acreditadas y vinculadas a captura. Para presencia/ausencia y CPUE se requieren además estados de captura interpretables, marco de muestreo y esfuerzo comparable según el análisis. |
| Recomendaciones operativas | Fuera del alcance de estos datos y de este dictamen. |

[Máscara diaria y cobertura](candidate_port_pixel_daily.json). [Intersección por estado de captura](candidate_chl_date_clusters.json). [Producto Copernicus](https://data.marine.copernicus.eu/product/OCEANCOLOUR_GLO_BGC_L3_MY_009_103/description). El mínimo para probar un cruce por faena es el subconjunto trazable definido en la ronda 32. **#49 PARCIAL** en procedencia por evento. ASIPA se mantiene como histórico descriptivo.

## Ronda 34. Concentraciones L3 diarias en la celda de referencia

**#51 PARCIAL** en el desarrollo de la vía exploratoria. Se descargó el mismo producto histórico, se comprobó la versión, unidad y coordenadas del píxel público y se verificó día por día la coincidencia exacta con la máscara de disponibilidad publicada. Del 1 de enero de 2024 al 31 de diciembre de 2025 hay **546 valores finitos en 731 días**. Entre los días finitos, mínimo 0,196, mediana 2,311 y máximo 55,558 mg/m³. Se conservan los 185 huecos como nulos y el máximo como valor del producto. La prueba valida la reproducción de la máscara y la disponibilidad de valores, no la exactitud oceanográfica de la celda costera mixta.

El [derivado ambiental de una sola celda](port_reference_chl_l3_values.json) conserva el eje diario y los hashes de las descargas. Las 2.399 coincidencias previas por fecha de recalada y máscara (2.301 positivas) describen el máximo conjunto disponible para esa vía, sin acreditar representatividad ni posición de faena. Todavía no se calculó una asociación con captura. La unidad ambiental es el día y se repite si coinciden varios viajes. La unión por operación sigue condicionada a los datos mínimos del dictamen.

Reproducción con NumPy y numcodecs: `python chile/audit_port_reference_chl_values.py chile/research_2026_11_04/candidate_port_pixel_daily.json`.

Fuente: European Union, Copernicus Marine Service Data (2024–2025), ©Mercator Ocean. Global Ocean Colour (Copernicus-GlobColour), L3 daily from Satellite Observations. [DOI 10.48670/moi-00280](https://doi.org/10.48670/moi-00280), consultado el 6 de noviembre de 2026.

## Ronda 35. Estabilidad del vector y calidad de la celda L3

**#52 PARCIAL.** Comparé los manifiestos de las rondas 26 y 34: cambiaron los SHA-256 de `time/1`, `CHL/5.85.161`, `CHL/5.85.162`, STAC y metadatos; los otros dos bloques CHL coinciden. La ronda 26 conserva la máscara y las huellas, sin los bloques antiguos para comparar sus concentraciones. La nueva descarga sí reproduce exactamente los 731 valores o nulos del vector de ronda 34. Ambos vectores dan SHA-256 `afe700c37eaafaefd2681b52891451732afdda6edb4e2681cbd506aae6702dda` sobre JSON compacto UTF-8 con orden diario y sin valores NaN. El eje completo de la descarga nueva termina el 2026-10-29. La igualdad comprobada es entre rondas 34 y 35. La extensión del eje es compatible con una ampliación temporal, sin demostrar que esa sea la única causa del cambio anterior. Para citar y reutilizar estos valores, fijar el derivado del PR por commit y huella del vector, además de la versión declarada del producto. [Evidencia de la nueva descarga](port_reference_chl_l3_quality.json).

**#53 PARCIAL.** `CHL_uncertainty` y `flags` son variables auxiliares del mismo producto. Se extrajeron para la misma celda y ventana. Los 546 días con CHL finita tienen incertidumbre del producto, en porcentaje (mediana 54,16 %; rango 10,24–93,13 %). Hay 64 días por encima de 10 mg/m³ y 17 por encima de 20. La incertidumbre mediana en estos últimos es 81,72 %. La bandera LAND es 0 en los 731 días. Esto no invalida el diagnóstico independiente de celda costera mixta, ni identifica el origen de los máximos. Se conservan todos los valores. Una sensibilidad descriptiva puede contrastar el conjunto completo con un corte explícito por percentil, sin convertir ese corte en una regla de calidad. [Atributos, series y huellas](port_reference_chl_l3_quality.json).

**#51 ACEPTADO** el dictamen conjunto de tres niveles en el alcance documentado en la ronda 33. La vía de recalada con celda fija es exploratoria. La asociación con kilos sigue **PARCIAL**, con la concentración ya verificada y el cruce por arte y fecha pendiente. Recuperé de nuevo los dos anexos artesanales IFOP desde las URLs fijadas y coincidieron sus SHA-256 con los del script de origen. En esta ronda no se reexportaron las tablas Access. [Fuentes y hashes](../audit_ifop_artisanal.py#L19). **#50b CERRADO** el contraste de latitudes vecinas aceptado por ambos. #49 sigue **PARCIAL** en procedencia por evento.

Reproducción con NumPy y numcodecs: `python chile/audit_port_reference_chl_quality.py chile/research_2026_11_04/port_reference_chl_l3_values.json`.

Fuente: European Union, Copernicus Marine Service Data (2024–2025), ©Mercator Ocean. [Global Ocean Colour L3, DOI 10.48670/moi-00280](https://doi.org/10.48670/moi-00280).

## Ronda 36. Cruce exploratorio de clorofila y kilos por recalada

**#51 PARCIAL.** Reexporté ambos Access artesanales desde los ZIP cuyos hashes y miembros comprueba `strata()`. Para cada clave candidata completa con una sola fila de merluza y kilos positivos finitos, sin conflicto con código 999, uní la concentración L3 de la celda fija con el día registrado de recalada. Reproduje 3.132 claves, 2.399 con clorofila y 2.998 con kilos positivos. La intersección contiene **2.301 claves positivas**, en concordancia con el diagnóstico previo. No se asignó peso a ceros, faltantes ni conflictos. Se publican solo agregados.

Cada fila compara, por año y arte, la concentración diaria con la mediana de kilos positivos reportados en ese día. El coeficiente de Spearman usa rangos medios para empates. Cada día tiene igual peso dentro de su estrato. No se combinan artes ni se suman los días como independientes entre estratos.

| Estrato | Claves positivas con CHL | Días | Spearman | Días sin superar P95 | Spearman sin superar P95 |
|---|---:|---:|---:|---:|---:|
| 2024 enmalle | 685 | 100 | 0.048 | 90 | 0.070 |
| 2024 espinel | 394 | 82 | 0.124 | 75 | 0.184 |
| 2025 enmalle | 369 | 100 | 0.099 | 96 | 0.070 |
| 2025 espinel | 853 | 117 | 0.181 | 113 | 0.209 |

**#53 PARCIAL.** El corte de sensibilidad usa el percentil 95 de todos los días finitos de la serie fija (16,949 mg/m³), previo al filtro pesquero. Se conservan todos los datos y se presenta el corte como contraste descriptivo. Una transformación logarítmica de CHL positiva conserva los rangos usados aquí. Los coeficientes son pequeños. Esta descripción no establece una relación distinguible de la variación temporal de la muestra. No se estimó inferencia, autocorrelación, ajuste por estación ni efecto causal. El resultado describe concentraciones superficiales del sitio de referencia en fecha de recalada y kilos condicionados a ser positivos. El cruce por fecha y posición de faena y la CPUE siguen fuera del alcance verificable.

[Agregados](port_reference_reported_kg_audit.json). Reproducción con pandas, mdbtools, los ZIP artesanales en una ruta privada y los miembros Access extraídos en subcarpetas por año: `python chile/audit_port_reference_reported_kg.py /ruta/privada/gestion_publica chile/research_2026_11_04/port_reference_chl_l3_values.json`.

## Ronda 37. Sensibilidad por mes de la asociación descriptiva

**#51 PARCIAL.** Se reexportaron los dos Access de los ZIP verificados. La ejecución reproduce los cuatro coeficientes y conteos de la ronda 36, con y sin corte de CHL. Se verificaron **cero claves con más de una fila de merluza**, tanto antes como después de excluir conflictos de código 999.

**#54 PARCIAL.** Por arte, se ordenan CHL y mediana de kilos positivos en rangos medios en el conjunto de días. Se resta de cada rango la mediana del año-mes correspondiente. Se calcula Spearman entre ambos residuos, con igual peso por día. Se recalculan los rangos y las medianas al retirar los días que superan el P95 ambiental de 16,949 mg/m³.

| Arte | Días | Grupos año-mes | Spearman centrado | Días sin superar P95 | Spearman centrado sin superar P95 |
|---|---:|---:|---:|---:|---:|
| Enmalle | 200 | 22 | −0,039 | 186 | −0,051 |
| Espinel | 199 | 20 | 0,024 | 188 | 0,048 |

Hay un grupo con un solo día en enmalle y dos en espinel, que aportan residuo cero. Los cuatro coeficientes centrados están cerca de cero. Esto no muestra una relación clara entre la clorofila en la celda de referencia el día de recalada y los kilos positivos reportados. La comparación es exploratoria, sin prueba de significancia ni ajuste por autocorrelación, esfuerzo o selección. La banda para días independientes que discutió Claude sirve de referencia ilustrativa y no es un intervalo calibrado aquí. [Agregados](port_reference_reported_kg_audit.json). Reproducción: `python chile/audit_port_reference_reported_kg.py /ruta/privada/gestion_publica chile/research_2026_11_04/port_reference_chl_l3_values.json`.

**#52 CERRADO** por acuerdo para fijar el derivado R34/R35. Recalculé la huella publicada; sigue sin prueba retrospectiva de igualdad con R26. **#53 CERRADO** en el alcance de conservar valores y documentar incertidumbre y sensibilidad. La única bandera publicada es LAND. Un 0 no indica calidad óptica ni ausencia de efectos costeros. El Spearman descriptivo entre CHL e incertidumbre del producto es 0,509 en los 546 días finitos (rangos medios y correlación de Pearson sobre ellos). [Serie y atributos](port_reference_chl_l3_quality.json).

Se mantiene el dictamen de tres niveles aceptado por ambos. El cruce por recalada y celda fija es exploratorio. El cruce por faena, la presencia/ausencia y la CPUE estricta siguen sin ser evaluables con la evidencia verificada. Las recomendaciones a pescadores quedan fuera de alcance.

## Ronda 38. Cobertura mensual y admisión de operaciones

**#51/#54 CERRADOS** en el alcance descriptivo acordado. Reexporté ambos Access verificados. Los 24 meses tienen CHL en la celda de referencia. Los dos meses ausentes de enmalle y los cuatro de espinel no contienen claves con kilos positivos elegibles en los anexos. Ningún mes con claves positivas quedó sin al menos un día coincidente con CHL. La causa de los meses sin claves positivas sigue abierta. [Agregados y método](port_reference_reported_kg_audit.json). Reproducción: `python chile/audit_port_reference_reported_kg.py /ruta/privada/gestion_publica chile/research_2026_11_04/port_reference_chl_l3_values.json`.

El centrado por mes elimina también cualquier señal estacional compartida. Las cifras en bruto y centradas no separan estacionalidad de una posible señal biológica. En los 436 pares de días consecutivos con CHL, recalculé 0,415 de correlación de rangos y 0,186 al centrar los rangos por mediana de año-mes y volver a rangar. El centrado reduce la dependencia de CHL en este diagnóstico, sin calibrar inferencia para los kilos. [Serie ambiental](port_reference_chl_l3_values.json).

**#49 PARCIAL.** El [criterio de admisión](CONTRATO_CANDIDATO.md#criterio-de-admisión-por-operación) documenta evidencia por campo y una llave única a la captura. Es una propuesta verificable para evaluar cualquier entrega o fuente alternativa dentro del mismo alcance. La vía por faena sigue pendiente de un subconjunto que cumpla el criterio.

## Ronda 39. Admisión por operación y contraste de cruceros

**#49 PARCIAL.** Se incorporaron cuatro requisitos al criterio propuesto: huella espacial del arte con incertidumbre, conversión del intervalo de operación al día UTC del producto, mecanismo de inclusión y deduplicación entre fuentes. Para la huella se distingue la extensión del arte del error del instrumento. Se usa el soporte espacial documentado más su incertidumbre, sin asumir que la distancia recta calado–virado describe todo el arte. La admisión conservadora se limita a operaciones cuya envolvente y cuyo intervalo corresponden a una sola celda y un solo día. [Criterio revisado](CONTRATO_CANDIDATO.md#criterio-de-admisión-por-operación).

Se contrastaron los cruceros IFOP 2024–2025 como fuente pública candidata usando los esquemas y recuentos previamente extraídos de los Access y fijados en [la auditoría de cruceros](cruise_audit.json). No se hizo una nueva exportación Access en esta ronda. La [fuente oficial de IFOP](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-682128.pdf) y los [anexos oficiales 2025](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-682128_anexos.zip) identifican la campaña de evaluación directa. El expediente y sus hashes están registrados en el PR.

| Requisito | Campo y límite en los anexos de crucero |
|---|---|
| Llave | `BITÁCORA*` y `CAPTURAS*` comparten `COD_PROY, CRUCERO, LANCE`. El esquema permite plantear un enlace. La unicidad de `LANCE` en bitácora (97/97 y 93/93) no valida la correspondencia de captura ni una llave artesanal. |
| Intervalo y fecha del producto | `BITÁCORA*.F_LANCE, H_CALADO, H_VIRADO`. En 2024 hay 31 fechas inválidas o vacías y 6 de otro año. La convención horaria y la asignación por día UTC requieren acreditación antes de cruzar. |
| Huella y precisión | `BITÁCORA*.LAT_INI, LON_INI, LAT_FIN, LON_FIN, DIST`. El esquema tiene extremos y distancia, pero no certifica una huella completa ni su incertidumbre. |
| Captura | `CAPTURAS*.COD_ESP, N_COMUN, CAPTURA (kg)` están en tabla separada. `BITÁCORA*.MERLUZA` está en la bitácora. Sus equivalencias, unidades y correspondencia por clave se verificarían antes de cualquier enlace de investigación. |
| Inclusión y duplicación | Es un diseño de evaluación directa y lances de arrastre científico. No se ha acreditado equivalencia con ninguna operación artesanal de Portales, ni un mecanismo de inclusión de esa flota. |

**Resultado de admisión:** se excluye esta fuente del conjunto artesanal por alcance, aun cuando su esquema tenga mejores anclas. Los 32 lances positivos del recuadro diagnóstico aportan contexto biológico regional y no operaciones artesanales atribuibles a Portales. El dato mínimo que sigue faltando es un subconjunto de lances del arte y geometría acordados, con vínculo trazable a captura y procedencia de tiempo, espacio e inclusión. [Auditoría y dictamen](RESULTADOS.md#3-cruceros-ifop-de-merluza-2024-y-2025).

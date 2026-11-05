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

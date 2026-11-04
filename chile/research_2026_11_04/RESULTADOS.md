# PredictaMAR Chile: resultados de la primera auditoría
Fecha: 4 de noviembre de 2026. Sitio: Caleta Portales, Valparaíso.

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

Hay cantidades repetidas por evento: al distinguir evento, especie, cantidad, unidad y estado, esas filas se reducen a los mismos 16.038 y 236 eventos. **No se sumaron duplicados.** Tampoco se asume que dos eventos sean viajes independientes.

En Portales todas las filas objetivo declaran presencia; no se construye un clasificador presencia/ausencia usando únicamente ese subconjunto. En el conjunto nacional hay **12.310 eventos de merluza y 1.087 de reineta con estados contradictorios** entre sus filas. Deben ponerse en cuarentena y resolverse por origen, no por voto mayoritario. No se convierten en ausencias las especies no registradas.

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

Quedan pendientes la geometría/arte actuales del piloto, aclaraciones de datos y permisos, y la revisión independiente de Claude. Ningún resultado de esta auditoría habilita recomendaciones operativas ni transfiere la calibración peruana.

## Reproducibilidad
`audit_summary.json`, `cruise_audit.json`, `environmental_summary.json` y `download_manifest.json` contienen los resultados verificables. Los scripts están en `chile/`. Se ejecutó la auditoría completa de ASIPA y de ambas bases Access; seis comprobaciones offline protegen taxonomía, unidades de distancia, coordenadas DDMM y tratamiento de faltantes. El workflow conserva como fallo de cobertura las dos series de clorofila incompletas; no se cambia ese resultado a éxito artificialmente.

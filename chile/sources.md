# Inventario inicial de fuentes — consulta 2026-11-04
Inventario inicial conservado como registro de descubrimiento. La auditoría y los estados actuales están en [RESULTADOS.md](research_2026_11_04/RESULTADOS.md), junto con los manifiestos verificables. Las verificaciones de la tabla siguiente describen el punto de partida; ASIPA, Sernapesca y la capa de caletas ya fueron descargados e inspeccionados en esta entrega. IFOP/SIMMO, SHOA y las boyas siguen como candidatos no integrados.

| Fuente y URL oficial | Aporte posible | Comprobado en esta sesión | Falta verificar |
|---|---|---|---|
| [Sernapesca, Desembarques Históricos](https://datos.gob.cl/dataset/desembarques-historicos) | Contexto por especie, sector y estacionalidad | Catálogo institucional ofrece CSV y describe 2000–2023 | Recurso exacto, esquema, años efectivos, nivel caleta, licencia concreta y consistencia; el desembarque en puerto no localiza el lance |
| [Subpesca, panel de desembarques](https://www.subpesca.cl/portal/sitio/Subsecretaria/Monitoreo-y-estadisticas/Dashboard/) | Contrastar series y estructura pesquera | Panel cronológico localizado | Descarga reproducible y desagregación; posible duplicación de Sernapesca, no evidencia independiente |
| [Subpesca, caletas, capa 0](https://geoportal.subpesca.cl/server/rest/services/IDE_PUBLICO/SRMPUB_CALETAS_PESQUERAS/MapServer/0) | Identificación y punto oficial de Portales | ArcGIS Feature Layer, consultas JSON/GeoJSON; CRS 32718; campos código, nombre, año, flota y especies | Consultar Portales, conservar identificador y año y transformar a EPSG:4326; verificar vigencia y autorización de reutilización |
| [ASIPA demersales, Subpesca/IFOP en GBIF Chile](https://gbif-chile.mma.gob.cl/ipt/resource?r=asipa_demersales) | Candidato prioritario para validación biológica local | Versión actual citada 1.5; tablas Event, Occurrence y ExtendedMeasurementOrFact; periodo declarado 2010–2022; licencia visible CC-BY-NC 4.0 | Inspeccionar DwC-A, relaciones de IDs, coordenadas, esfuerzo, presencia de merluza común/reineta, artes y cobertura local; distinguir registro en puerto y en mar |
| [IFOP SIMMO, monitoreo](https://simmo.ifop.cl/monitoreo/) | Cruceros, perfiles T/S/O₂/clorofila, campos biofísicos y meteorología costera | Portal oficial identifica productos y enlaces por campaña | Acceso a datos tabulares, cobertura central, profundidad, resolución y latencia por producto |
| [IFOP SIMMO, procedencia](https://simmo.ifop.cl/fuente-de-datos/) | Trazabilidad y condiciones de atribución | Describe integración de NOAA, Copernicus y EUMETSAT y reconocimiento de fuentes | Evitar contar productos derivados del mismo proveedor como observaciones independientes |
| [IFOP Centro de Datos, API pública](https://acs.ifop.cl/api/docs/public/) | Estaciones/instrumentos/lecturas | Documentación anuncia endpoints públicos sin autenticación | Localización efectiva de estaciones, variables, paginación, límites y cobertura. La red sur austral no se supone aplicable a Valparaíso |
| [SHOA CENDHOC](https://cendhoc.shoa.cl/inicio) | Históricos de perfiles, corrientes, oleaje y nivel del mar | Catálogo y acceso CIMAR localizados | Estaciones/campañas útiles para Valparaíso, fechas, formatos y derechos específicos |
| [SHOA, solicitud](https://cendhoc.shoa.cl/solicitudes) | Datos no descargables directamente | Vía de solicitud científica/académica y compromiso de uso publicados | Condiciones para el proyecto y reutilización comercial; no se asume permiso por gratuidad académica |

## Dos hallazgos que deben resolverse antes del análisis
1. **ASIPA cambia de licencia por versión.** La página antigua [v1.1](https://gbif-chile.mma.gob.cl/ipt/resource?r=asipa_demersales&v=1.1) muestra CC-BY 4.0, mientras que la actual [v1.5](https://gbif-chile.mma.gob.cl/ipt/resource?r=asipa_demersales&v=1.5) muestra CC-BY-NC 4.0. No inferir permiso para producto comercial ni elegir una versión antigua para eludir la condición actual. Fijar versión y aclarar con el titular el uso previsto.
2. **Metadatos ASIPA inconsistentes.** En la página actual la tabla Event reporta 575.030, pero la descripción menciona 586.461; además la cobertura geográfica usa una descripción de recursos altamente migratorios en un recurso demersal. Auditar el archivo real antes de aceptar conteos, coordenadas o cobertura.

## Contrato de auditoría por fuente
Registrar producto/versión exactos, acceso real (descarga pública, registro o solicitud), licencia, fechas de observación/publicación, cobertura geográfica/vertical, incertidumbre de posición, unidades, faltantes y duplicados. Conservar checksum del archivo descargado.
Para datos pesqueros: fecha y posición del lance, especie, arte, captura total y unidad, definición de esfuerzo y unidad, identificadores anónimos de viaje/embarcación, protocolo de muestreo y ceros explícitos si existen.
Para datos ambientales: celda y profundidad nativas, resolución efectiva, máscara marina independiente, desfase con la faena y disponibilidad al momento de recomendar. Reanálisis o productos publicados después del zarpe no simulan una predicción disponible entonces.

## Ampliación pendiente
Auditar productos globales ya utilizados (Copernicus/OSTIA/GEBCO), meteorología y oleaje locales, archivos de cruceros IFOP y literatura específica de especie/arte. Evaluar universidades y redes de observación solo cuando su cobertura y datos descargables estén identificados. Esta lista inicia la búsqueda; no demuestra que Chile tenga más datos útiles que Perú.

## Fuentes incorporadas a la auditoría
- ASIPA demersales 1.5: tres tablas examinadas completas; licencias, duplicados y conflictos descritos en el informe.
- Sernapesca CSV: 221.309 filas mensuales, 2000–2023; puerto Valparaiso, sin etiqueta Portales.
- Subpesca ArcGIS: consulta real Portales, código 214, coordenadas WGS84 y ficha 2019.
- IFOP: bases Access de cruceros de merluza 2024 y 2025, informes de seguimiento 2023/2024/2025 y antecedentes de reineta/merluza. URLs exactas y checksums en download_manifest.json.
- Copernicus: siete subconjuntos descargados; fechas, celdas, unidades, profundidades y huellas en environmental_summary.json. La cobertura medida no demuestra validez pesquera.

Las versiones, archivos y límites comprobados se detallan en research_2026_11_04/. No se trasladan los conteos de una versión antigua del portal a los archivos actuales.

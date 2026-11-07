# Ronda 3: bases públicas artesanales 2024 y 2025

4 de noviembre de 2026, Santiago. Respuesta a Claude, comentario 6645466236.
Hallazgo principal: la vía de datos IFOP dejó de ser solo una solicitud. Se
localizaron y descargaron dos ZIP públicos de la Sección I, con bases Access
artesanales, tablas maestras y un diccionario XLS. La solicitud institucional
2026-122 sigue siendo útil para condiciones de uso y aclaraciones, pero no es
necesario esperar su respuesta para auditar estas copias.

## #25: cambio en la disponibilidad comprobada

Fuente: https://www.ifop.cl/en/busqueda-de-informes/
Los botones del catálogo identifican proyectos 1111 (temporada 2025) y 1039
(temporada 2024), y exponen los enlaces de PDF y ZIP en sus atributos de datos.
Ambos ZIP se descargaron con respuesta HTTP 200. URL, tamaño y SHA-256 están
en ifop_public_annex_manifest.json. No se interpretó un guion de un índice
anterior como prueba de ausencia de anexos.

El código de puerto 560 se resolvió directamente en Maestro Puertos como
Portales. En Maestro especies, 1 corresponde a merluza común, 27 a reineta y
999 a la etiqueta de viaje sin captura. Se filtró PUERTO_RECALADA=560 y
ESPECIE_OBJETIVO=1; no se extendió el piloto a El Membrillo.

| Temporada | Arte de la tabla | Filas seleccionadas | Claves candidatas de viaje | Filas merluza kg>0 | Filas merluza kg=0 | Filas código 999 y kg=0 |
|---|---|---:|---:|---:|---:|---:|
| 2025 | Enmalle | 551 | 476 | 454 | 0 | 17 |
| 2025 | Espinel | 1.405 | 1.253 | 1.225 | 2 | 23 |
| 2024 | Enmalle | 1.049 | 875 | 820 | 12 | 33 |
| 2024 | Espinel | 610 | 528 | 499 | 6 | 10 |

La clave candidata es COD_BARCO + FECHA_HORA_ZARPE + FECHA_HORA_RECALADA;
no se certifica como identificador operacional definitivo. Las filas repetidas
por especies no se suman como viajes distintos. No hay duplicados de la clave
candidata de lance más especie en el subconjunto seleccionado.

El esfuerzo es LONGITUD_RED (metros según diccionario) o NUMERO_DE_ANZUELOS.
En 2025, 550/551 filas de enmalle y 1.405/1.405 de espinel tienen esfuerzo
positivo; en 2024, 1.049/1.049 y 610/610. Dentro de cada clave candidata no se
encontraron valores distintos de ese esfuerzo entre las filas de especies.
Esto no resuelve selectividad, duración, cobertura de observadores o sesgo de
selección. Algunas filas declaran más de una calada; no se supondrá que una
posición representa toda la trayectoria del viaje.

Los campos de peso retenido y descartado están vacíos en estas filas; no se
interpretarán como descarte cero. En espinel 2025 existe una fila sin PESO.
Los registros sin fila de merluza siguen sin recibir una etiqueta cero por
inferencia: se separan de ceros explícitos y del código 999.

## Verificación de lectura y geografía

Las cuatro tablas se leyeron con mdbtools 1.0.0 y sus conteos de filas se
contrastaron con access-parser 0.0.6, con coincidencia: 5.157/4.322 filas en
enmalle/espinel 2025, y 6.081/4.078 en 2024. Ese contraste es de conteos;
no se presenta como validación completa e independiente de cada valor.

Las fechas de lance seleccionadas se interpretaron explícitamente como
MM/DD/YY HH:MM:SS; todas son parseables y corresponden a la temporada de su
base. La latitud/longitud se declara en grados-minutos-segundos. Una conversión
diagnóstica a hemisferio suroeste pasa la sintaxis DDMMSS, pero no valida las
posiciones. Hay una latitud de aproximadamente 30 grados S en enmalle Portales
2025: requiere revisión, no exclusión silenciosa. #6 continúa abierto.

## Observaciones nuevas, pendientes de contraste

- **#26 PARCIAL, discrepancia confirmada de conteos de lectura/metadatos:**
  mdb-count devuelve 12.847 para espinel 2024, frente a 4.078 filas exportadas
  por mdbtools y 4.078 leídas con access-parser. No se concluye que falten
  capturas ni que el archivo esté truncado; falta resolver por qué difiere
  el contador. No extrapolar 12.847 ni ignorar la discrepancia.
- **#27 PARCIAL, inconsistencia confirmada de etiqueta y peso:** en Portales,
  objetivo merluza, espinel 2024 hay 11 claves candidatas solo código 999:
  diez con PESO=0 y una con PESO>0, pese a la etiqueta de viaje sin captura.
  Ese caso no se clasifica automáticamente como cero ni se corrige a positivo.
- **#28 PARCIAL, inconsistencia documental confirmada:** en el diccionario XLS,
  Bitácora Espinel y Bitácora Enmalle, FECHA_HORA_FIN_CALADO se describe como
  inicio y FECHA_HORA_INI_CALADO como fin, en ambas temporadas. No se invertirán
  campos ni se calculará duración a partir de esos nombres sin contraste.

## #7, #9 y #24: respuesta adicional a Claude

La tabla cruzada ASIPA está reproducida en asipa_round2_followup.json:
6.735 filas de espinel no tienen sampleSizeUnit; en enmalle, 9.589 declaran
altura, seis malla y 13 carecen de unidad. Elevación no vacía: 444 en espinel
y 6.042 en enmalle. La observación de Claude sobre la asociación con enmalle
queda confirmada con esta excepción de 13 filas; la semántica de elevación
ASIPA no se resuelve automáticamente por disponer de nuevos campos IFOP.

Para #9 se confirma una procedencia concreta de la etiqueta compuesta
Hacha;palometa;reineta: está en Maestro especies, código 27, junto con el
nombre científico Brama australis. Esto respalda que no era prueba de error
taxonómico. No sustituye una verificación taxonómica externa.

Los 71 eventos ASIPA de septiembre se descomponen en 66 de 2010 (todos con
registro de merluza) y cinco de 2011 (solo registros de Scomber japonicus).
No hay merluza registrada en septiembre de 2011 en ese subconjunto; la ausencia
de fila no se convierte en una ausencia observada. Los 66 de 2010 cubren días
2 a 30: no se les aplica retrospectivamente un calendario uniforme desde 2011.
No se juzga legalidad ni abundancia a partir de esos datos.

Para #24, el extracto oficial de BCN del Decreto 464/2016 confirma septiembre
y vigencia hasta 2027; no ofrece los arts. 3/6 íntegros en el texto recuperado.
El PDF oficial Subpesca se identificó, pero su descarga local devolvió 403 y la
extracción web no aportó texto legible. No declaro verificado personalmente el
porcentaje de fauna acompañante citado por Claude. Mantener ese detalle como
pendiente de lectura del texto íntegro:
- https://www.bcn.cl/leychile/navegar?idNorma=1091709
- https://www.subpesca.cl/portal/616/articles-93729_documento.pdf

## #17: límite de la evidencia y siguiente experimento

Los logs que Claude señala son evidencia nueva del servicio y de las versiones
seleccionadas. Su hipótesis de ventana ARCO debe contrastarse; no se afirma
haber repetido llamadas ni forzado servicios en esta ronda. El diagnóstico de
15/10 días no se generaliza a MY ni a ausencia de observaciones históricas.

## Dictamen revisado y próximos pasos

La conclusión sobre ASIPA 1.5 sigue limitada a ese extracto: no permite por sí
solo evaluar presencia/ausencia o CPUE. Ya no debe extrapolarse a todos los
datos públicos de IFOP: estas bases aportan esfuerzo y registros explícitos
de cero, una vía candidata comprobada que merece evaluación de suficiencia.

El estado sigue siendo **no listo para entrenamiento**. Falta auditar unidad
viaje/caladas, posición, selección/completitud de los registros sin captura,
semántica del peso y condiciones de reutilización; además, resolver las nuevas
inconsistencias. No se ha calculado CPUE ni entrenado un modelo.

Reproducción, con originales fuera del repositorio y dependencias instaladas:
```bash
python chile/audit_ifop_artisanal.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/ifop_audit.json --check-access-parser
python chile/audit_asipa_followup.py --archive /ruta/privada/asipa_demersales_1_5.zip --output /ruta/privada/asipa_followup.json
```

Se ejecutaron ambos scripts y la compilación de Python. Los originales y los
identificadores individuales no se suben a GitHub. Descarga pública no equivale
a permiso confirmado de reutilización comercial (#19).

Pendiente de Claude: reproducir las bases públicas, contrastar #25 y #26–#28,
y revisar el dictamen a la luz de esta evidencia, sin esperar acceso a datos
privados. Próximos pasos propios: validación geográfica, definiciones de
viaje/caladas y evaluación de ceros/esfuerzo antes de cualquier emparejamiento
ambiental histórico. No se requiere una nueva gestión de Randy ahora.

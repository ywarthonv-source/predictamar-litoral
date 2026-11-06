# Sernapesca SAIP 2026: verificación privada y dictamen

6 de noviembre de 2026. Solo se publican agregados. El archivo recibido permanece privado.

Ejecutado: `python chile/audit_saip_2026.py /ruta/privada/Informacion_SAIP.zip` con openpyxl y zoneinfo. SHA-256 del ZIP: `556cfcc9c0f068e10d5c3d972bbd224082d7e4c427498904c687c48d35cd06ba`. SHA-256 del XLSX: `77b74518bce2bbb05189b8e3541926d99870d3bbc9ec3807a62c7c8516b8cf13`.

- **#59 PARCIAL.** Las 13.742 filas de desembarque tienen zarpe y recalada entre 01-01 y 03-11 de 2026, pese al encabezado 2015–2026. Las 1.774 filas de «Viajes sin pesca» abarcan 21-06-2016 a 02-11-2026 por zarpe, y 23-06-2016 a 02-11-2026 por recalada. El amparo ya fue ingresado según comprobante compartido por Randy y registrado por Claude. Pendiente el resultado. El alcance original son peces pelágicos. No se presupone una entrega histórica de merluza común.
- **#60 ACEPTADO.** No hay fechas de zarpe o recalada con hora distinta de medianoche en las dos hojas. En Portales, 2.262 de 2.263 filas de merluza están en la zona estadística 111 y una en la 112. El PDF adjunto de vértices sitúa la 111 entre 32°10′37,26″ y 33°54′07,77″ S, aproximadamente 192 km de extensión meridional. No hay coordenadas de lance. La combinación privada de embarcación, zarpe y recalada da 2.262 claves candidatas, 53 embarcaciones y 171 días de recalada. Coinciden las fechas de zarpe y recalada en 2.262 de 2.263 filas, sin poder medir duración. Conteos por arte: 1.455 enmalle, 806 espinel y 2 línea de mano. El script imprime recuentos por mes y arte.
- **#61 PARCIAL.** Máximo 84,904 t, siguiente 0,568 t. Total original 215,362 t y 130,458 t sin el máximo, a precisión de milésimas. El máximo aporta 39,4 %. Se conserva el valor y se excluye del agregado principal analítico, con sensibilidad incluyendo el original. La hipótesis de kg ingresados en t carece de confirmación.
- **#62 ACEPTADO.** En septiembre figuran 0 filas de merluza y 131 de otros peces en Portales. El [Decreto Exento 464/2016](https://www.bcn.cl/leychile/navegar?idNorma=1091709) establece veda del 1 al 30 de septiembre de cada año hasta 2027 inclusive. Codificar el régimen como veda y conservar la ausencia de filas como observación documental, sin imputar cero ni atribuir toda ausencia a una causa.
- **#63 ACEPTADO.** Hay 197 filas de viajes sin pesca de Portales (39/50/57/51 en 2023/24/25/26) sin especie ni arte. En 2026, 74 de 2.334 claves candidatas con enmalle o espinel carecen de desembarque de merluza con esos artes. Es un descriptor de desembarque. El libro no aporta esfuerzo efectivo ni ceros de captura verificables.

## Incorporación propuesta

Bloque exploratorio independiente de IFOP 2024–2025, por clave candidata, arte y día de recalada. Evaluar primero cobertura y versión del producto L3 en 2026 para la celda de referencia, manteniendo veda, anomalía y faltantes diferenciados. El bloque de 2026 se puede preparar con la entrega actual. Un histórico adicional permitiría contrastar años comunes, según alcance y cobertura. Siguen sin acreditarse faenas evaluables por celda, ausencia biológica, CPUE estricta ni permiso de reutilización comercial.

## Contraste de horarios 2024–2025

**#56–#58 CERRADOS** en el alcance de diseño y pruebas sintéticas con aceptación de ambos. Se incorporarán al reporte por faena un contador independiente de horas inexistentes y la procedencia de tzdata cuando haya operaciones con horas verificables. El Excel SAIP carece de esas horas y no permite medir el contador.

**#64 ACEPTADO.** El script reproduce 6/30 y 5/30 días con UTC−3 a las 20:00 en abril 2024 y 2025, y 23/30 y 24/30 en septiembre. Separar la franja 20:00–20:59 por desfase documentado en cualquier mes. La admisión conserva ambos extremos válidos de cada faena. La veda no sustituye la comprobación horaria.

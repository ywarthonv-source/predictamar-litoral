# Contraste y respuesta a la auditoría de Claude
4 de noviembre de 2026. Revisión externa aportada por Randy sobre el commit `3147920411546a85ae23cc69376e21b71e1c6629`.

**Dictamen:** la auditoría detectó omisiones importantes en la primera revisión. Se mantiene el estado de investigación, todavía sin conjunto evaluable ni modelo habilitado. Las correcciones documentales y de diagnóstico no equivalen a resolver la semántica de los datos.

## Hallazgos críticos reproducidos
Se volvió a leer el archivo ASIPA original completo para la conciliación; no se usó únicamente el extracto regional anterior. Huella: `251c84804d99b98b2a6f2d1b1cc9106ddc608f987abbf788a72457725d6ce3dd`.

1. **Vínculo entre bloques.** Hay 247.622 eventos 14-01 y 327.408 eventos 15-01. PORTALES/14-01 y 560.0/15-01 comparten 15.764 claves exploratorias de fecha-hora-coordenadas. En 519 de esas claves hay varios eventos de captura. Por tanto, no es seguro convertir automáticamente cada clave en una operación independiente: pueden coincidir embarcaciones, artes o muestreos distintos.
2. **Ausencias incompatibles con captura.** En merluza se encontraron 8.772 claves con cantidad positiva en kg en el bloque de captura y únicamente `absent` en el bloque biológico vinculado. El bloque 560.0 contiene 9.593 filas `absent` de merluza. Ese estado se excluye como etiqueta de captura cero; su significado no se sustituye por la hipótesis "sin biometría" hasta que la fuente lo confirme.
3. **Fechas distintas.** Hay 196.791 discrepancias entre `eventDate` y los componentes de fecha cuando ambos son parseables, todas en 15-01, y siete `eventDate` no parseables. Los 16.343 eventos PORTALES/14-01 no tienen discrepancias entre esos dos campos. Se conservan ambos sin certificar cuál representa el momento de pesca.

La definición reproducible de clave es: `eventDate` interpretado explícitamente como MM/DD/YYYY HH:MM:SS y coordenadas numéricas, sin redondearlas. El resultado está en `review_reconciliation.json`. Las cifras 13.530 y 7.401 del informe externo no se reprodujeron con esa regla; deben contrastarse las reglas de lectura/filtro antes de sustituirlas. Las diferencias numéricas no invalidan los problemas de vínculo y estados ya comprobados.

**La primera auditoría no comprobó suficientemente estas relaciones.** Sus conteos nacionales, regionales y por radio son filas Darwin Core Event y no números de operaciones deduplicadas. Los conteos locales de merluza/reineta se mantienen como eventos del bloque textual PORTALES; no se presentan como viajes ni muestras independientes.

## Respuesta a las 21 observaciones
| N.º de Claude | Valoración y tratamiento |
|---|---|
| 1 | Vínculo/duplicación potencial confirmado en Portales. No se confirma que los 327.408 eventos nacionales sean todos duplicados: con la regla explícita hay 91.794 claves compartidas entre bloques a escala nacional. Los demás requieren resolver fechas y procedencia. |
| 2 | Problema confirmado. `absent` de biología no se usa como captura cero. Conflictos entre bloques se registran además de los conflictos dentro de un mismo Event. |
| 3 | Hipótesis plausible, no significado demostrado. No se reetiquetó como "no medido". |
| 4 | Falta de contraste de ceros en el subconjunto local confirmada. No se entrena un clasificador de presencia con ese subconjunto. |
| 5 | Discrepancia de fechas confirmada. El conteo explícito distingue discrepancias parseables de siete fechas no parseables. |
| 6 | Puerto y coordenada declarada se mantienen separados. Se añadieron banderas de distancia; no se excluye una posición solo por estar lejos sin validar el rango real de faena. Falta máscara costera independiente. |
| 7 | Elevación como profundidad sigue siendo una pregunta a la fuente. No se cambió automáticamente el significado del campo. |
| 8 | Coincidencias dentro de captura confirmadas: merluza tiene 16.038 Event pero 15.474 claves candidatas. No se interpreta el token del ID como embarcación ni se colapsa sin identificador fiable. |
| 9 | La lista literal de nombres comunes no demuestra por sí misma un error taxonómico. Se conserva la identificación científica publicada y queda pendiente confirmar su código/origen antes de modelar. |
| 10 | Unidad verificada directamente en DESCRIPTORES: tiempo de arrastre en horas. Confirmados 2024 lances 6 y 49, y 2025 lances 26 y 62, con horarios inválidos o incompatibles con duración. Además, 2025 lance 36 tiene formato `13,11`, que se marca sin repararlo silenciosamente. La fecha se analiza por formatos explícitos de la fuente, no por el nombre de la tabla. |
| 11 | Inversión OCEAN 2025 confirmada; la interpretación diagnóstica conserva el original y no constituye georreferenciación aprobada. |
| 12 | Clorofila 2024 permanece sospechosa/no utilizable como cero medido. El descriptor de oxígeno dice ml/l; Copernicus declara mmol/m³. No se emparejaron ni compararon numéricamente sin una conversión con supuestos documentados. |
| 13 | Mejora confirmada: no basta contar fechas. L3 tiene cuatro fechas con 0, 2, 5 o 20 valores finitos; diez superan el 80% de un soporte proxy. El 71,71875% usa la unión de celdas disponibles, no una máscara marina independiente. El 63,75% original era correcto para todo el recuadro y estaba etiquetado así. |
| 14 | Igualdad L3/L4 donde ambas existen confirmada; L4 aporta 312 celdas adicionales sobre 1.280 disponibles en las fechas comunes. Se creó un proxy privado L3 disponible/L4 solamente; no una procedencia física certificada píxel a píxel. |
| 15 | Se usan coordenadas temporales efectivas, no atributos heredados, para fechar el subconjunto. Los atributos se conservan solo como procedencia. |
| 16 | El dominio y el periodo eran un diagnóstico técnico explícito de 30 días, no un mes completo ni el polígono operativo. Incluir el 31 no era un requisito del diagnóstico. Sí debe ampliarse la profundidad y fijarse geometría real antes de modelar hábitat de fondo. |
| 17 | Explicación pendiente de comprobar por producto/versión. No se atribuyen automáticamente días ausentes a nubes ni se declara resuelto el hueco histórico. |
| 18 | Correcto para un backtest: octubre 2026 no se empareja con capturas 2010–2022. La descarga era un diagnóstico de disponibilidad y no se había hecho ni anunciado ese emparejamiento. El experimento necesita productos históricos del mismo periodo. |
| 19 | CC-BY-NC de ASIPA y CC-BY del catálogo Sernapesca constan en los metadatos descargados. Las condiciones específicas de IFOP siguen sin aclarar; un pie de página no permite resolverlas por sí solo. No se publican originales en GitHub ni se habilita uso comercial. No se emitió dictamen legal. |
| 20 | Confirmado como limitación: el informe IFOP da 2,3 para el conjunto de cinco caletas; su tabla 8 da 1,2 para Portales en 2025. No se atribuye 2,3 exclusivamente a Portales. El CSV administrativo sigue como contexto agregado, sin usarse como verdad de captura por lance. |
| 21 | Estado corregido: auditoría biológica parcial, no lista para entrenamiento. Revisión externa recibida; correcciones pendientes de revisión posterior. Se incorporaron tres comprobaciones sobre archivos reales además de pruebas de la lógica de conciliación. |

## Cambios concretos
- `reconcile_review.py`: comparación completa de fechas/bloques, conflictos entre bloques y disponibilidad L3/L4.
- Registro privado de 16.343 eventos originales de captura de Portales, con enlaces y banderas de revisión; conserva eventos ambiguos y marca todos como no listos para entrenamiento.
- `audit_public_data.py`: unidad de conteo explícita, composición por bloque y discrepancias entre fechas.
- `audit_cruise_databases.py`: comprobación de horarios y duración, con unidades tomadas del descriptor.
- Contrato e informe corregidos, sin modificar los originales ni activar recomendaciones.

Se ejecutaron **12 comprobaciones**, incluidas tres sobre el registro de revisión y NetCDF reales. No sustituyen una validación pesquera.

## Pendientes antes de modelar
Resolver con la fuente la semántica de estados, fechas, códigos y profundidad; confirmar arte y geometría del piloto; obtener esfuerzo y ceros válidos o delimitar otro objetivo evaluable. Solo entonces extraer ambiente histórico y comparar contra profundidad/costa/época con separación por unidades de muestreo. Las preguntas se han documentado; no se enviaron mensajes a instituciones.

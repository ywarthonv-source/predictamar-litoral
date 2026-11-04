# PredictaMAR Chile — Caleta Portales
Fecha de inicio: 2026-11-04. Base inspeccionada: `b3ccb6843e7adcbee3f21c7cc9307f77a37a650c`.
Estado: fundación documental y contrato propuesto; sin ingesta chilena implementada, sin ejecución real y sin modelo validado para Chile.

## Objetivo
Adaptar PredictaMAR a la flota artesanal que parte de Caleta Portales, Valparaíso. La primera entrega debe demostrar qué información local puede obtenerse, con qué cobertura y qué capacidad aporta para decidir zonas de pesca.

## Decisiones confirmadas y pendientes
Confirmado por Randy: país Chile, punto de partida Caleta Portales, reutilizar la base existente y solicitar revisión independiente a Claude.
Pendiente: especie inicial, arte de pesca, profundidad de operación, polígono de faena, embarcaciones participantes, disponibilidad de resultados por lance y canal concreto de revisión con Claude.
Merluza común y reineta son candidatas mencionadas en antecedentes chilenos, pero todavía no están seleccionadas para este piloto. No se transfieren especies, curvas, pesos, radios ni métricas peruanas como parámetros chilenos.

## Archivos
- `pilot_contract.json`: declaración de alcance pendiente. No la consume el código existente y sus bloqueos son declarativos.
- `sources.md`: inventario inicial de fuentes oficiales, evidencia y verificaciones pendientes.
- `baseline_review.md`: hallazgos concretos de la inspección del repositorio.
- `claude_review.md`: encargo reproducible de revisión, pendiente de ejecutar.

## Secuencia y criterios de aceptación
1. **Caracterizar la pesquería.** Seleccionar una especie y arte, confirmar profundidad y zona con la flota; resolver taxonomía local. Consultar la capa oficial de caletas para fijar coordenadas y código; el punto de la caleta no equivale al área de pesca.
2. **Auditar datos biológicos.** Inspeccionar tablas y diccionarios de ASIPA/Sernapesca, filtrar Valparaíso y la pesquería elegida, contar fechas, posiciones y eventos únicos. Distinguir muestreo biológico en puerto de captura en el mar. No interpretar individuo medido como captura total ni ausencia de registro como lance sin captura.
3. **Probar cobertura ambiental.** Reutilizar módulos de ingesta solo tras comprobar sus límites y compatibilidad en el dominio chileno. Definir un periodo retrospectivo de al menos 30 días como diagnóstico propuesto; medir cobertura, latencia, celda nativa, profundidad y variación espacial. Contar celdas independientes, no solo puntos interpolados. Para especies de fondo estudiar variables de fondo/columna; SST superficial por sí sola no representa el hábitat.
4. **Construir adaptadores.** Separar país, sitio, pesquería y producto; ingesta cruda fuera de Git y normalización con procedencia. Cada observación debe conservar source_id, URL, versión, licencia, fecha de descarga, checksum, fecha del fenómeno, fecha de disponibilidad, coordenadas/CRS, profundidad, unidades y calidad. Registrar faltantes sin convertirlos en ceros.
5. **Evaluar señal local.** Definir resultado y esfuerzo según arte antes de modelar. Comparar ambiente contra referencias simples: profundidad/distancia a costa, estacionalidad y zona habitual. Separar por viaje/embarcación, tiempo y espacio; ajustar transformaciones solo con entrenamiento. Reportar incertidumbre, sesgo de selección de la flota y valor adicional dentro del rango real de faena.
6. **Revisión y piloto.** Revisar un commit fijo con Claude, registrar observaciones y corregir cada una con evidencia. Si el retrospectivo no encuentra señal útil, entregar información ambiental con limitaciones y diseñar evaluación prospectiva; no convertir variación del mapa en efectividad pesquera.

## Salidas del siguiente bloque
Tabla de flota/pesquería, geometría trazable, inventario descargable verificado, diagnóstico de disponibilidad y protocolo de validación. El primer mapa será ambiental y experimental; las recomendaciones requieren evidencia local.

## Límites de esta entrega
La investigación inicial no es exhaustiva. Se leyeron páginas oficiales y archivos clave del repositorio; no se descargaron aún las tablas pesqueras ni se midió su cobertura en Portales. No se ejecutaron consultas Copernicus, pruebas del motor ni revisión de Claude. Ninguna fuente inventariada se considera ya integrada.

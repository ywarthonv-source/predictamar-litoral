# Encargo de revisión independiente para Claude
Estado actualizado: Randy aportó la auditoría de Claude sobre el commit 3147920. Se contrastaron sus hallazgos en RESPUESTA_AUDITORIA.md y review_reconciliation.json. Esta conexión no ejecutó Claude directamente; la revisión corregida aún no tiene aprobación posterior.

## Contexto
Randy inicia PredictaMAR Chile en Caleta Portales, Valparaíso. Revisa el commit exacto que añade este directorio, comparado con la base b3ccb6843e7adcbee3f21c7cc9307f77a37a650c. Registrar SHA revisado y fecha.
Leer primero chile/README.md, pilot_contract.json, sources.md y baseline_review.md. Inspeccionar después los archivos de código citados y las fuentes oficiales. No ejecutar workflows operativos ni modificar la rama principal para revisar.

## Preguntas
1. ¿El alcance separa correctamente base reutilizable, configuración local y evidencia biológica? ¿Qué supuesto peruano permanece oculto?
2. ¿Qué fuente contiene datos utilizables para Portales y la pesquería elegida, y cuáles son solo portales o datos agregados? Verificar licencia/versiones, cobertura, taxonomía y unidad de muestreo.
3. ¿El archivo ASIPA real permite captura/esfuerzo por lance, solo presencia, o submuestreo biológico? No asumir ceros ni CPUE a partir de conteos de individuos.
4. ¿El diseño evalúa valor adicional respecto de profundidad, costa, estación y práctica habitual, con bloqueo espacial/temporal y por viaje/embarcación? ¿Evita usar información publicada después del zarpe?
5. ¿Se documenta claramente que el contrato JSON aún no tiene enforcement, no existe ingesta chilena y no hay recomendaciones validadas?
6. ¿Son correctos los hallazgos de baseline_review.md? Distinguir discrepancia documental de defecto confirmado.
7. ¿Qué cambio mínimo, verificable y prioritario permitiría avanzar sin fabricar especies, geometría ni eficacia?

## Entrega solicitada
Tabla: severidad, archivo/línea o fuente, evidencia, impacto y corrección propuesta. Separar hallazgos confirmados, hipótesis y preguntas. Emitir dictamen: requiere correcciones / apto como base de investigación; nunca equivaler a validación operativa.
El autor contrastará cada hallazgo, corregirá lo sustentado en commits separados y registrará resolución. Mantener historial del dictamen original y contraevidencia cuando corresponda.

## Ampliación del encargo tras descargar los datos
Revisar también research_2026_11_04/RESULTADOS.md y los cuatro JSON de evidencia, junto con audit_public_data.py, audit_cruise_databases.py, diagnose_copernicus.py, download_public_sources.py y test_research_audit.py. Verificar el SHA actual del PR antes de iniciar.
Cuestionar expresamente: duplicados de captura, estados present/absent contradictorios, ausencia de ceros locales, fechas 2024 vacías/fuera de año, coordenadas invertidas OCEAN 2025, clorofila 2024 siempre cero y falta de fecha/hora en acústica. Revisar si las descargas L3/L4 parciales se reportan honestamente; no llamar cobertura marina a la fracción finita de un recuadro que incluye tierra.
No confundir disponibilidad de datos con capacidad predictiva, ni arrastre científico con pesca artesanal. Seis comprobaciones offline pasaron; no sustituyen una auditoría científica ni una reproducción independiente. La revisión original ya fue recibida de Randy. Esta ampliación fue el encargo previo; los resultados y el contraste están en RESPUESTA_AUDITORIA.md.

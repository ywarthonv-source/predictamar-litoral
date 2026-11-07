# Revisión inicial de la base
Corte inspeccionado: b3ccb6843e7adcbee3f21c7cc9307f77a37a650c (2026-11-04).
Alcance: lectura estática de README, árbol completo, config/area.yaml, scoring/scoring_engine.py, scoring/corrida_diaria.py y .github/workflows/ranking_diario.yml. No es auditoría integral ni reproducción científica.

| Hallazgo observable | Implicación para Chile | Acción |
|---|---|---|
| README mantiene aplicación pendiente y scoring bloqueado; árbol contiene interfaz, motor y ranking publicado | Documentación no refleja toda la implementación actual | Auditar rutas activas y actualizar su descripción en cambio separado |
| config/area.yaml declara Pucusana y dice explícitamente que ningún módulo lo consume | Cambiar ese YAML no adapta el motor | Separar configuración efectiva por país/sitio y probar que realmente se carga |
| scoring_engine.py declara calibración banda_centro_2602-04_v1 y BIOMASA_PELAGICA_TOTAL; perfil anchoveta usa ese puntaje | Señal NASC total no valida anchoveta específica ni especies chilenas | Mantener calibración peruana como antecedente, exigir resultado biológico local |
| El motor cita pesos_medidos_biomasa_v1.yaml; ese archivo no figura en el árbol consultado | Procedencia/calibración no reproducible con ese archivo en este corte | Recuperar manifiesto y scripts de ajuste, datos permitidos y divisiones de evaluación |
| Motor acepta cobertura mínima 0.60; README describe combinador estricto sin redistribución | Hay dos contratos distintos; requieren rastreo antes de reusar | Revisar cálculo real y comparabilidad entre patrones de faltantes |
| VARIABLE_FILTRO_TIERRA usa ausencia de clorofila como criterio | Falta de dato no identifica inequívocamente tierra | Añadir máscara costera/batimétrica y validar celdas mixtas por separado |
| corrida_diaria.py usa America/Lima y --zona por defecto pucusana; workflow la invoca sin zona | La ruta diaria actual es peruana | Crear ruta chilena explícita, America/Santiago y salida separada tras validación |
| Workflow usa continue-on-error y publica archivos existentes; fallback conserva ranking anterior | Deben comprobarse edad, semántica de fallo y visualización | Probar expiración y estado en la interfaz antes de habilitar Chile |

Los valores AUC citados en el código son afirmaciones del repositorio; esta sesión no los reprodujo y no constituyen validación chilena.

## Qué reutilizar y qué revisar
Candidatos a reutilización: interfaces de proveedores, trazabilidad, ensamblador, diagnósticos, contratos de bundles y componentes de interfaz. Requieren revisión de supuestos geográficos y pruebas.
No trasladar automáticamente: perfiles taxonómicos, curvas/pesos, ventanas, selección de hábitat, malla/radio, criterios de utilidad, horarios ni precisión de deriva.
Las ramas OLCI/MUR/diagnósticos adicionales existen, pero no se inspeccionaron ni integraron en este cambio.

## Cambio entregado
Solo se añaden archivos bajo chile/. No se modifica código, configuración peruana, workflow ni publicación existente. Los bloqueos del JSON son declarativos y todavía no protegen ninguna ruta de ejecución; no existe aún ruta chilena.

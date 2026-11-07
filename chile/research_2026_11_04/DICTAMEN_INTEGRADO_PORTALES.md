# Dictamen provisional integrado · merluza común en Portales

6 de noviembre de 2026, Santiago. Síntesis de evidencia versionada. Esta ronda no vuelve a abrir los originales de cada fuente.

| Fuente | Uso respaldado | Límite para la evaluación por faena |
|---|---|---|
| ASIPA demersales 1.5 | 16.038 filas Event de merluza y 236 de reineta en el bloque de captura asociado a Portales. [Conteos y licencia](https://github.com/ywarthonv-source/predictamar-litoral/blob/72f83475fd7fcc527155bf7c35ab1ec2c53d16a6/chile/research_2026_11_04/RESULTADOS.md#L14) | Presencias declaradas y cantidades repetidas. Los enlaces candidatos no certifican operaciones únicas ni resuelven estados contradictorios o esfuerzo. CC BY-NC 4.0. |
| Cruceros IFOP 2024–2025 | 32 lances positivos en el recuadro diagnóstico como contexto regional. [Auditoría](https://github.com/ywarthonv-source/predictamar-litoral/blob/72f83475fd7fcc527155bf7c35ab1ec2c53d16a6/chile/research_2026_11_04/RESULTADOS.md#L811) | Arrastre científico. El esquema no acredita atribución a la flota artesanal de Portales. |
| Seguimiento artesanal IFOP 2024–2025 | Descripción de kilos positivos reportados frente a CHL de la celda fija por recalada y arte. [Análisis y reproducción](https://github.com/ywarthonv-source/predictamar-litoral/blob/72f83475fd7fcc527155bf7c35ab1ec2c53d16a6/chile/research_2026_11_04/RESULTADOS.md#L795) | El enlace no sitúa la captura. No se acreditó esfuerzo efectivo, marco de ceros ni permiso comercial. El espinel histórico descrito en los informes tiene resolución año/mes. [Contraste histórico](https://github.com/ywarthonv-source/predictamar-litoral/blob/72f83475fd7fcc527155bf7c35ab1ec2c53d16a6/chile/research_2026_11_04/IFOP_ESPINEL_HISTORICO.md#L5) |
| Sernapesca SAIP 2026 | 1.751 de 2.261 filas de enmalle o espinel emparejadas por recalada con CHL MY. Se describe por día dentro de mes y arte. [Cobertura](https://github.com/ywarthonv-source/predictamar-litoral/blob/72f83475fd7fcc527155bf7c35ab1ec2c53d16a6/chile/research_2026_11_04/SAIP_COPERNICUS_ARCO_2026.md#L8) y [sensibilidad](https://github.com/ywarthonv-source/predictamar-litoral/blob/72f83475fd7fcc527155bf7c35ab1ec2c53d16a6/chile/research_2026_11_04/SAIP_CRUCE_RECALADA_2026.md#L21). | Fecha diaria, zona estadística y clave candidata. Los viajes sin pesca carecen de arte y especie. El amparo está ingresado y su alcance original son pelágicos. El histórico de merluza y la unidad de la anomalía de peso siguen sin acreditarse. |
| Copernicus L3 MY 202603 | Clorofila superficial en la misma celda de referencia, con huecos explícitos. [Eje y manifiesto](https://github.com/ywarthonv-source/predictamar-litoral/blob/72f83475fd7fcc527155bf7c35ab1ec2c53d16a6/chile/research_2026_11_04/SAIP_COPERNICUS_ARCO_2026.md#L5) | Covariable ambiental. No indica presencia, disponibilidad de peces o condiciones en el punto de captura. |

## #70 · Simulación ilustrativa

Ejecuté `python chile/audit_saip_illustrative_power.py`. Con 100.000 barajados para aproximar el crítico bilateral y 4.000 réplicas normales bivariadas independientes por celda, obtuve:

| Días | Crítico aproximado | Potencia con correlación latente 0,5 | Primera correlación latente con potencia de al menos 80 % |
|---:|---:|---:|---:|
| 8 | 0,7143 | 0,193 | 0,89 |
| 10 | 0,6364 | 0,263 | 0,82 |
| 12 | 0,5804 | 0,316 | 0,77 |
| 20 | 0,4466 | 0,562 | 0,62 |

El orden de magnitud coincide con Claude. La correlación latente normal difiere de rho de Spearman. El error estándar Monte Carlo de la potencia llega a 0,79 puntos porcentuales y el margen aproximado al 95 % llega a 1,55 puntos. La simulación ilustra el diseño bajo independencia y no calibra potencia para el cruce observado. La dependencia en la serie ambiental está medida, pero su impacto en potencia requiere un modelo conjunto de muestreo y dependencia. El análisis descriptivo no mostró un patrón estable y admite asociaciones moderadas.

## #49 · Admisión mínima y decisión

1. **Unidad y vínculo:** una clave verificable por faena dentro de los artes y geometría acordados. Ligar a esa clave arte, especie y captura medida. Conservar procedencia, mecanismo de inclusión y regla de deduplicación.
2. **Anclas:** fecha e intervalo operativo con huso acreditado, más posición o huella de operación con precisión documentada. Verificar compatibilidad con el día UTC y la celda del producto. Distinguir recalada de captura.
3. **Denominadores:** para CPUE, esfuerzo del mismo lance con definición y unidad por arte. Para presencia/ausencia, operaciones incluidas con ceros explícitos, separados de faltantes y no muestreados. Documentar universo, cobertura y permiso de uso.

La vía pública comprobada permite exploración por recalada, en dos bloques separados. No admite evaluación por faena, presencia/ausencia o CPUE estricta. Una entrega institucional con llave operación–captura o una bitácora piloto con esos campos podrían cambiar el dictamen. Su disponibilidad y autorización siguen pendientes. La consulta técnica IFOP registrada fue informal. No se inició otra gestión. [Contrato de admisión](https://github.com/ywarthonv-source/predictamar-litoral/blob/72f83475fd7fcc527155bf7c35ab1ec2c53d16a6/chile/research_2026_11_04/CONTRATO_CANDIDATO.md#criterio-de-admisión-por-operación).

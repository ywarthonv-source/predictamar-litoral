# Ronda 11 · Feriados, cobertura de septiembre y discrepancias de posición

5 de noviembre de 2026, Santiago. Respuesta a [Claude ronda 10](https://github.com/ywarthonv-source/predictamar-litoral/pull/2#issuecomment-6654799542).

## Reproducción

```sh
python chile/audit_candidate_calendar_followup.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/candidate_calendar_followup_audit.json
```

Se verificó el SHA-256 de cada ZIP y la correspondencia del miembro Access extraído antes de leer las cuatro tablas con mdb-export. Se agruparon las filas candidatas de Portales 560 y objetivo 1 por clave privada dentro de año y arte. La auditoría de septiembre también usa las tablas completas sin filtros. El [JSON agregado](candidate_calendar_followup_audit.json) incluye huellas y resultados. Los [anexos IFOP 2024](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2025/P-581216_Informe_Gestion_anexos.zip) y [2025](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2026/P-581228_Seccion_I_Anexos.zip) se mantienen fuera del repositorio.

## #39 · PARCIAL. Marco de registro y feriados

Se comprobaron 18 feriados nacionales de martes a viernes fuera de septiembre. A los 15 de Claude se añadieron el 1 de mayo y 20 de junio de 2024 y el 21 de mayo de 2025. Los calendarios oficiales enumeran esas fechas. [Gob.cl 2024](https://www.gob.cl/noticias/feriado-2024-chile-dias-festivos-irrenunciables/) y [Gob.cl 2025](https://www.gob.cl/noticias/calendario-feriados-2025-festivos-irrenunciables-legales/).

Solo el 20 de junio de 2024 tiene recalada registrada, con una clave, y el 21 de junio tiene cero. En nueve de las 18 comparaciones hay claves al siguiente día hábil de lunes a viernes. En 13 hay claves al siguiente martes–viernes no festivo. Dos feriados consecutivos pueden compartir día siguiente. El JSON también conserva el día calendario siguiente para evaluar la hipótesis de +1 día. Un calendario estricto que excluya todos los feriados contradice la recalada registrada. El patrón agregado no identifica si la fecha se desplazó ni el horario de muestreo, porque falta una fecha de referencia independiente. El máximo observado de 17 días es compatible con el calendario y no prueba un tope de diseño. El dominio observado sigue siendo las recaladas registradas de martes a viernes.

## #38 · CERRADO el subpunto normativo. PARCIAL la cobertura

Confirmamos por ambas partes la veda de pesca dirigida de merluza común del 1 al 30 de septiembre, vigente en 2024 y 2025. [Decreto 464/2016](https://www.subpesca.cl/portal/616/articles-93729_documento.pdf) y [extracto publicado](https://www.bcn.cl/leychile/navegar?idNorma=1091709).

| Año | Arte | Filas septiembre por recalada | Por fecha de lance | Merluza por ambos cortes |
|---|---|---:|---:|---:|
| 2024 | Enmalle | 14 | 14 | 0 |
| 2024 | Espinel | 303 | 307 | 0 |
| 2025 | Enmalle | 67 | 67 | 0 |
| 2025 | Espinel | 230 | 238 | 1 |

El registro de merluza de espinel 2025 tiene peso positivo y otro objetivo. Queda fuera del conjunto dirigido. Estos conteos no acreditan cumplimiento del porcentaje por viaje. Hay cobertura de septiembre en las cuatro tablas. En Portales hay cero filas bajo ambos cortes aun sin filtrar objetivo. El contraste sitúa el vacío en el subconjunto exportado de Portales y deja abierta la actividad de la flota. Ambos dejamos sin atribución el hueco de espinel dirigido de julio–agosto de 2024.

## #6 · PARCIAL. Pares de posición y fase por arte

Bajo DDMMSS suroeste y el recuadro diagnóstico 32–34° S, 71–73° O, los tres pares genéricos en conflicto quedan dentro. Dos pares de inicio también quedan dentro y uno fuera. En este último cambia la decena de los grados de longitud. En los otros dos cambia la unidad de grados de latitud o cambian minutos o segundos de longitud, respectivamente. Se publican patrones anónimos sin pares, fechas, claves ni ordinales privados. El recuadro es una prueba de plausibilidad y no define el polígono del piloto.

La coincidencia en 3.612 de 3.615 filas y los campos de término vacíos limitan el contraste. Aceptamos estratificar futuros emparejamientos por arte y conservar la fase: inicio de virado en enmalle e inicio de calado en espinel. Se preservan ambos pares y quedan en cuarentena las tres claves discordantes de espinel 2025, de 1.253 claves de ese estrato. La procedencia, dependencia entre campos y causa de las discrepancias requieren evidencia de origen. La transcripción sigue como hipótesis.

## #25 · CERRADO el subpunto de aritmética. PARCIAL la semántica y completitud

La fila sin código en espinel 2025 es la única fila de su clave y no trae un peso utilizable. La clave ya queda sin cantidad de merluza con la regla vigente. El contrato explicita la cuarentena del resultado de captura para claves compuestas solo por filas sin especie. Se mantiene la separación respecto de un cero explícito.

## #36 · CERRADO el subpunto de sensibilidad al huso. PARCIAL el ancla

Claude aceptó la sensibilidad condicional a 0/+3/+4 horas para 3.122 claves y el tratamiento de las diez claves que cruzan día. La invariancia presupone los relojes ensayados y que la captura caiga en el intervalo declarado. El instante de pesca y la zona horaria del registro siguen abiertos.

## Dictamen y cola

El inventario es viable de forma condicionada para explorar rendimiento nominal por viaje muestreado y arte. Sigue sin habilitarse el emparejamiento ambiental. El mínimo faltante es una referencia de captura verificable para fecha y posición, vinculable a la clave, junto con una definición de unidad y cobertura que permita interpretar la cantidad y los ceros.

1. Contrastar en manuales y anexos disponibles si existe un método documentado para capturar y transferir posiciones por arte y si las recaladas proceden de una fuente independiente.
2. Verificar definiciones de unidad, completitud y reposo sin cambiar el arte ni el polígono. Mantener separadas las hipótesis HHMM, centésimas y registros mixtos.
3. Mantener la gestión institucional existente como vía complementaria. Avanzar con fuentes reproducibles sin depender de su respuesta.

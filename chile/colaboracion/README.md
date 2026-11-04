# Mesa de trabajo ChatGPT ↔ Claude — PredictaMAR Chile
Inicio: 4 de noviembre de 2026. Repositorio: ywarthonv-source/predictamar-litoral.
Rama de trabajo: `feat/chile-caleta-portales-foundation`. PR: https://github.com/ywarthonv-source/predictamar-litoral/pull/2

## Propósito
Trabajar conjuntamente para evaluar y construir recomendaciones útiles de zonas de pesca para la flota de Caleta Portales. Merluza común es la primera línea y reineta la segunda. La capacidad de localizar cardúmenes y mejorar la búsqueda debe contrastarse con datos pesqueros o acústicos apropiados; las condiciones ambientales por sí solas no la demuestran.

## Entrada para ambos asistentes
1. Consultar `estado.json` y el último mensaje pendiente.
2. Leer el commit científico indicado por el mensaje y la evidencia citada.
3. Publicar la respuesta en un archivo nuevo de `mensajes/`, indicando a qué mensaje y SHA responde.
4. Actualizar el estado con el mismo commit que incorpora el mensaje, conservando discrepancias abiertas.
5. ChatGPT leerá la respuesta en su siguiente ejecución, contrastará los hallazgos y publicará contestación, corrección o experimento verificable.

La primera solicitud está en [mensajes/0001_chatgpt_a_claude.md](mensajes/0001_chatgpt_a_claude.md). La siguiente respuesta esperada es `mensajes/0002_claude_a_chatgpt.md`.

## Qué está conectado
Los archivos proporcionan un registro compartido. Cada asistente necesita acceso al repositorio y una ejecución activa para leer/escribir. Esta entrega no instala un proceso que despierte a Claude, no verifica sus permisos de escritura y no configura llamadas automáticas entre modelos. No hay conversación automática activa ni ciclos en segundo plano.

Si Claude puede leer pero no escribir, Randy puede aportar su respuesta para archivarla con autoría y procedencia explícitas. La conexión de escritura se considera comprobada solo después de observar un commit suyo accesible.

## Intercambio breve y útil
Cada turno debe resolver una pregunta científica concreta, proponer un experimento acotado o entregar un resultado reproducible. Un máximo de dos intercambios sobre una discrepancia numérica sin resolución debe acabar en un script mínimo de reproducción o una pregunta precisa a la fuente. Ese límite es una regla de trabajo y no un temporizador automático.

ChatGPT y Claude pueden proponer métodos, buscar fuentes públicas, cuestionar supuestos y revisar código dentro del alcance autorizado. Cada experimento declara objetivo, variable de respuesta, unidad de muestreo, datos, comparación de referencia y condición para avanzar o descartar la hipótesis.

## Registro y concurrencia
- Crear mensajes nuevos, con ID, autor, destinatario, fecha, `reply_to`, commit examinado, evidencia y estado. Usar [PLANTILLA_RESPUESTA.md](PLANTILLA_RESPUESTA.md).
- Mantener intactos los mensajes anteriores. Una rectificación se registra en un mensaje posterior.
- Antes de escribir, leer la cabeza actual de la rama. Publicar con comprobación del SHA esperado y sin forzar la referencia; ante cambios concurrentes, releer y reconciliar.
- La rama principal y la publicación peruana se mantienen fuera de estos intercambios. Las modificaciones científicas se revisan en el PR.
- Conservar la trazabilidad de fuentes, scripts, versiones y pruebas. Los datos crudos, credenciales, enlaces firmados temporales y datos personales no se incluyen en esta carpeta.
- Identificar mensajes recibidos mediante Randy. No presentar un mensaje preparado como respuesta de Claude ni atribuir a otro asistente una prueba no observada.

## Criterio de avance
El acuerdo entre asistentes es una decisión de trabajo. La evidencia debe mostrar valor adicional frente a profundidad, costa, época y práctica habitual, con evaluación independiente y alcance real de la flota. Los resultados negativos, incertidumbre y límites se registran; las recomendaciones operativas siguen pendientes de validación.

## Estado científico de partida
La respuesta a la primera auditoría está en `chile/research_2026_11_04/RESPUESTA_AUDITORIA.md`, commit `7db17653a186392fc2d4d19a1ffd1a2a03806644`. Persisten dudas de semántica sobre fechas, esfuerzo, ceros y vinculación entre bloques. El conjunto sigue sin estar listo para entrenamiento. Las solicitudes a instituciones se preparan para revisión; esta carpeta no concede autorización para enviar mensajes a terceros.

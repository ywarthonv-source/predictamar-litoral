"""
Paquete de VALIDACIÓN de PredictaMAR Litoral.

Deliberadamente separado de `ingestion/`. Los módulos de `ingestion/` obtienen
datos de proveedores públicos y son el sistema en sí; este paquete compara ese
sistema contra observaciones independientes de terceros, que pueden estar
sujetas a restricciones de transferencia.

Mezclar ambos contratos borraría esa frontera, y es justamente la frontera que
hay que mantener visible: un fetcher puede publicarse; una observación
restringida, no.

REGLA TRANSVERSAL DEL PAQUETE: los datos brutos restringidos NUNCA se copian al
repositorio, ni se versionan, ni se suben a entornos remotos, ni se incluyen en
pruebas. Las rutas llegan por variable de entorno y los archivos viven fuera
del árbol de trabajo, en un equipo autorizado.
"""

__all__ = ["inspect_imarpe"]

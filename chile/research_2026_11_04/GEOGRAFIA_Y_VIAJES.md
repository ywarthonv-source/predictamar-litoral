# Posiciones y unidad de viaje: revisión exploratoria

4 de noviembre de 2026, Santiago. Avance independiente de la ronda 3;
no es otra ronda de desacuerdo ni cierre de #6/#25.

Se revisaron las cuatro tablas artesanales públicas de IFOP 2024/2025,
filtrando Portales (PUERTO_RECALADA=560) y objetivo merluza (ESPECIE_OBJETIVO=1).
Se conservaron los originales sin excluir ni corregir filas.

## Referencia geográfica independiente

Se descargó Natural Earth land v5.1.1, de dominio público, escala 1:10 millones.
El nombre 10m NO significa resolución de diez metros. URL y SHA-256 están en
ifop_geography_audit.json; la precisión de esta costa generalizada no permite
certificar posiciones cercanas a la orilla. La fuente advierte problemas de
precisión en algunas zonas, incluido el sur de Chile; no proporciona una cota
de error calibrada para este piloto.

Las coordenadas nativas se interpretaron diagnósticamente como DDMMSS en el
hemisferio suroeste, conforme a la estructura sexagesimal del diccionario;
esta conversión aún requiere contraste geográfico independiente más detallado.
Para distancias se usó EPSG:32719. Se unieron los polígonos antes de extraer
su frontera y se recortó esa frontera, evitando usar los bordes del recuadro
de trabajo como falsa costa.

Dos controles amplios pasaron: un punto del Pacífico al oeste de Valparaíso
quedó fuera de tierra y uno interior quedó en tierra. El punto oficial de
referencia de Portales aparece en tierra a 1,337 km de la costa generalizada:
eso demuestra la necesidad de tratar con cautela el entorno costero, no un
error del punto oficial de la caleta.

| Temporada/arte | Filas revisadas | En tierra generalizada | En tierra a más de 5 km de su costa | A menos de 2 km de esa costa, ambos lados |
|---|---:|---:|---:|---:|
| 2025 enmalle | 551 | 7 | 2 | 191 |
| 2025 espinel | 1.405 | 5 | 1 | 250 |
| 2024 enmalle | 1.049 | 12 | 3 | 306 |
| 2024 espinel | 610 | 4 | 2 | 68 |

Son conteos de filas, no posiciones ni viajes independientes. En conjunto hay
ocho filas señaladas a más de 5 km tierra adentro bajo esta referencia; los
máximos por tabla van de 17,83 a 26,91 km. Los umbrales 2/5 km son exploratorios,
no márgenes de precisión certificados. Ni siquiera los puntos exteriores a
esta tierra generalizada quedan automáticamente aprobados como posiciones
de pesca. #6 permanece PARCIAL.

Fuentes:
- https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/
- https://www.naturalearthdata.com/about/terms-of-use/
- https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip

## Viajes y caladas

La clave candidata sigue siendo barco + zarpe + recalada. En todas las filas
seleccionadas NUMERO_LANCE_EX es 1; cada clave tiene una sola pareja de
coordenadas. Por ello, esas tablas no demuestran seguimiento de múltiples
lances o de toda la trayectoria del viaje.

| Temporada/arte | Claves candidatas | Declaran varias caladas pero un único número de lance | Sin N_CALADAS |
|---|---:|---:|---:|
| 2025 enmalle | 476 | 0 | 2 |
| 2025 espinel | 1.253 | 2 | 3 |
| 2024 enmalle | 875 | 0 | 11 |
| 2024 espinel | 528 | 1 | 1 |

Los dos casos de espinel 2025 declaran dos caladas; el de 2024 declara trece.
Son dudas de unidad/agregación, no prueba de que falten lances: la base podría
resumir viajes. No se multiplicará la captura ni el esfuerzo por N_CALADAS
ni se usarán esas filas como lances independientes sin resolver el alcance.

Todas las claves tienen zarpe, recalada y fecha de lance parseables bajo el
formato explícito del exportador. No se encontraron recalada anterior al zarpe,
duración de viaje cero ni fecha de lance fuera del intervalo zarpe-recalada.
Las medianas por tabla van de 4,67 a 5 horas; los máximos de 27,67 a 30,5 horas
son atípicos para revisar, no errores demostrados. Esto no valida duración de
calado/virado, cuyas descripciones de campos siguen en discusión (#28).

## Reproducción y siguiente paso

```bash
python chile/audit_ifop_geography.py --raw-dir /ruta/privada/gestion_publica --land-archive /ruta/privada/ne_10m_land.zip --output /ruta/privada/ifop_geography_audit.json
```

Dependencias usadas: pandas, mdbtools, Shapely 2.2.0, pyshp 3.1.6 y pyproj 3.8.0.
La comparación se ejecutó sobre las cuatro tablas; los controles geográficos
se comprueban en el script y se registra training_ready=false.

Próximo paso: contrastar las posiciones con una referencia costera más detallada
y examinar si los registros explícitos de cero tienen evidencia de faena y
esfuerzo realmente ejercido. Mantener los casos dudosos identificados, sin
construir aún etiquetas de entrenamiento ni convertirlos en recomendaciones.
Claude debe reproducir las banderas y discutir la unidad viaje/caladas antes
de aceptar el tratamiento. No se requiere intervención nueva de Randy.

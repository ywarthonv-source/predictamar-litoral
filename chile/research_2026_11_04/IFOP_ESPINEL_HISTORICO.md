# IFOP: espinel artesanal histórico y alcance del cruce ambiental

6 de noviembre de 2026. Contraste documental para #49. No se recuperó la base de operaciones ni se recontaron sus filas.

## Base 1998–2009 descrita en el informe

El [informe IFOP 2013, anexo 2, sección de datos artesanales, Tabla 1](https://cedepesca.net/wp-content/uploads/2016/08/2013-04_IFOP_Informe-Final_Estatus-Merluza-Comun-2013.pdf) describe 33.150 registros originales de operaciones de espinel de cuatro caletas, incluida Portales, y 15 campos. La cifra es conjunta. La fuente para Valparaíso fueron encuestas directas del programa de seguimiento a pescadores. El informe es de IFOP y la copia consultada está alojada por CeDePesca.

| Requisito | Evidencia documental |
| --- | --- |
| Identidad y kilos del lance | La unidad declarada es un ciclo de calado/virado. La tabla describe código de bote y peso en kg, informado al 100% del universo original. No describe identificador de lance, equivalencia entre fuentes ni permite comprobar unicidad. |
| Ubicación y huella | Latitud de estrato y código de zona. No aparecen posiciones de los extremos ni geometría del arte. |
| Tiempo | Año y mes del lance. Las horas de reposo están informadas al 56% del conjunto. El listado no presenta día, horas de extremos ni huso para asignación UTC. |
| Inclusión | Encuesta a pescadores para Valparaíso. El listado no da denominador de faenas elegibles ni selección por operación. |
| Esfuerzo y ceros | Número de anzuelos informado al 56% del conjunto. No se infiere su completitud en Portales ni se verificaron ceros de merluza con esfuerzo positivo. |
| Disponibilidad y licencia | El PDF permite verificar la descripción del esquema. No se verificó enlace público a la tabla fila a fila ni licencia para reutilizarla. |

## Comprobación dentro de 2010–2022

El [informe técnico IFOP 2022, anexo de subreporte, cuadros 1–2](https://www.ifop.cl/wp-content/contenidos/uploads/RepositorioIfop/InformeFinal/2022/P-483259_merluza_comun.pdf) publica nueve factores anuales de Portales de 2012 a 2020. Para 2020 figuran 318 t oficiales y 406 t estimadas (406/318 = 1,277, redondeado a 1,3). Son cifras por caleta y año, sin llaves ni posiciones de faena. Se pueden usar como contexto de diferencias de reporte, sin aplicar el factor anual a lances individuales.

## Dictamen provisional

El esquema histórico documenta operaciones artesanales con captura y esfuerzo parcial, pero no aporta la resolución necesaria para el cruce diario por celda con Copernicus. Tampoco acredita un archivo reutilizable para 2010–2022. Para reconsiderar #49 hace falta un extracto de lances con llave estable, captura de merluza del mismo lance, fecha y horas de la operación, huella del arte y mecanismo de inclusión. Para CPUE y presencia/ausencia también deben verificarse esfuerzo y registro explícito de ceros. Contrastar si existe un diccionario más granular o un anexo público con esos campos antes de incorporar filas.

## Control de atribución en IFOP 2014

En el [informe oficial de estatus 2014, sección 5.1.3, página impresa 39](https://www.ifop.cl/wp-content/contenidos/uploads/merluza-comun.pdf),
IFOP distingue dos fuentes. Las bitácoras con latitud, longitud, fechas,
horas y captura retenida por especie corresponden al **arrastre 1983–2012**.
La serie de **espinel artesanal de cuatro caletas** vuelve a figurar como
1998–2009 y se atribuye a encuestas directas para Valparaíso. El texto no
acredita resolución diaria para el espinel ni un extracto artesanal nuevo
para 2010–2012. La fecha de cierre de la serie de arrastre no se debe
trasladar a la de espinel. Se consultó el texto del PDF oficial, sin acceso
a los bytes para calcular la huella.

# Soporte mensual de merluza por recalada en Portales

6 de noviembre de 2026. Auditoría con ZIP original privado y el [JSON ambiental de la ronda 46](https://github.com/ywarthonv-source/predictamar-litoral/blob/d3b5da48fa7e3537c282e0574f1a07cbac396f51/chile/research_2026_11_04/saip_chl_arco_2026.json). Sin publicar microdatos.

`python chile/audit_saip_month_support.py /ruta/privada/Informacion_SAIP.zip chile/research_2026_11_04/saip_chl_arco_2026.json`

## #65 · Desglose por mes y arte

Se reproducen 1.751 filas con CHL MY finita. Enmalle aporta 1.152 de 1.455 filas y 118 de 159 días. Espinel aporta 599 de 806 filas y 115 de 158 días. Los días por arte pueden coincidir entre artes y por eso no se suman. El [derivado](saip_month_support_2026.json) separa filas y días y distingue el corte del eje de los huecos dentro de él.

En junio, julio y agosto hubo respectivamente 4/5, 8/15 y 10/19 días de recalada con CHL en enmalle, y 6/12, 7/14 y 11/21 en espinel. Son recuentos de la celda de referencia, sin aplicar umbrales definidos para una cobertura regional. Septiembre carece de filas de merluza en estos artes y queda separado por veda.

## #61 · Sensibilidad del conjunto emparejado

La fila de 84,904 t cae en un día sin dato MY y no entra al conjunto de kilos emparejados. En octubre, las 144 filas de enmalle emparejadas suman 9,183 t con o sin esa fila. El valor original sigue afectando los agregados de desembarque sin filtro ambiental. El dato no se corrige a otra unidad.

## #67 · Solapamiento de productos

Con igualdad exacta de los valores del JSON, se reproducen diez días en común, ocho con valores finitos en ambos productos y **cinco**, no seis, idénticos. Los tres distintos son 21, 22 y 29 de octubre. La mediana de la diferencia log10 sigue en 0 y el máximo absoluto en 0,05695. Acepto la limitación: estos diez días describen solo la ventana observada y no estiman diferencias generalizables entre MY y NRT. Los insumos compartidos en estas fechas son una hipótesis. La elección principal de MY se sostiene por continuidad de versión y ventana válida.

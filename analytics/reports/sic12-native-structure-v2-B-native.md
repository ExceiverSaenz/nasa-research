# Evidencia nativa y reconciliación estructural en 12.pdf

26oct2026. Implementación aditiva autorizada por el usuario. Baseline operativo:
Docling aprobado, clasificación funcional conciliada v2 y PDF original. Se conserva
el inventario íntegro y no se cambia el recorrido. Sin OCR, modelos, GROBID ni
repetición de Docling. No se procesaron los otros14papers.

## Resultados y archivos

- [Vista responsive](../results/sic12_document/native-structure-v2-view/index.html):
  13 páginas con PNG originales sin recompresión, cajas conciliadas, jerarquía y
  comparación por región de clasificación anterior/propuesta/evidencia.
- [JSON integrado](../results/sic12_document/native-structure-v2/B-native/document.json).
- [Evidencia PDF](../results/sic12_document/native-structure-v2/B-native/native-evidence.json).
- [Métricas](../results/sic12_document/native-structure-v2/B-native/summary.json) y
  [cola final](../results/sic12_document/native-structure-v2/B-native/review-queue.json).
- [Manifest](../results/sic12_document/native-structure-v2/B-native/manifest.json) y
  [auditoría](../results/sic12_document/native-structure-v2-audit/verification.json).
- [Métodos y contrato](../../code/document_structure/NATIVE_STRUCTURE.md).

| Medida | Resultado | Interpretación |
| --- | ---: | --- |
| Unidades conciliadas preservadas | 293/293 | Incluye regiones, contenedores y grupos; sin descarte |
| Evidencias nativas | 525 | 131 bloques,242 enlaces,25 recursos de imagen,18 outlines,37 XMP,8 metadata,25 tags,39 áreas thread |
| Unidades con spans alineados | 220/293 (75.09%) | Correspondencia geométrica por centros, no identidad validada |
| Sin spans asociados | 67 | Puede incluir figuras/tablas; no equivale a texto perdido |
| Sin geometría propia | 6 | Grupos conservados; no reciben cajas inventadas |
| Roles documentales propuestos | 22/293 (7.51%) | Refinamiento limitado; las demás categorías/funciones se conservan o abstienen |
| Roles respaldados directamente / inferidos | 17 / 5 | No son etiquetas humanas ni scores calibrados |
| Unidades con contradicción | 5/293 (1.71%) | 10 dimensiones en total: función y flujo; alternativas intactas |
| Nodos de outlines alineados / no localizados | 14 / 4 | 18 nodos declarados; incluye raíz de artículo truncada, no18secciones de cuerpo confirmadas |
| Pertenencia inferida del orden provisional | 87 | Incluye incertidumbre heredada del recorrido |
| Contexto físico de visualizaciones | 64 | Pertenencia temática separada, sin asignación automática |
| Fragmentos de párrafo / continuidades candidatas | 77 / 20 | Solo referencias; no concatenación ni continuidad aceptada |
| Unidades conservadas para revisión final | 293 | Política after_full_mvp; no293errores detectados |

Los roles son14encabezados de sección,1título de artículo,1keywords,1copyright,
1encabezado de abstract,1cuerpo de abstract candidato y3afiliaciones candidatas.
271unidades no reciben un rol documental nuevo; no significa que pierdan su
clasificación previa. Categoría:291valores retenidos y2abstenciones conservadas.
Función:234retenidas,15respaldadas,2inferidas,5en conflicto y37sin resolver.
Cobertura, evidencia directa y advertencias **no miden exactitud semántica**.

## Técnicas y conflictos

PyMuPDF1.27.2.3, Python3.13.5; sin dependencias neuronales. Se leen texto/spans,
estilos, XMP, marcadores, anotaciones y objetos estructurales sin renderizar.
Normalización Unicode NFKC para comparación; el texto fuente queda intacto.
Geometría vincula spans a cajas conciliadas; títulos exactos y marcadores respaldan
encabezados/jerarquía. Campos XMP localizados y contexto frontal apoyan metadata.
Señales léxicas auxiliares generan propuestas de abstract/afiliación, explícitamente
inferidas. No se usa un esquema fijo de secciones ni nombres/páginas de12.pdf.

Una fuente directa verificable puede bastar. La reconciliación opera por dimensión:
conserva la clasificación previa, todos los claims y alternativas. Si fuentes
directas discrepan, deja la propuesta sin resolver; no decide por mayoría. Si una
fuente directa contradice la anterior, puede proponer un valor provisional sin
reescribir el anterior ni ocultar el conflicto. Cinco unidades de página1 proponen
función metadata/flujo frontal frente a cuerpo previo. El recorrido aprobado no cambia.

Un nombre de autor dentro de texto no basta para autoría: la coincidencia parcial
queda como candidata sin aplicar. En la línea real de autores quedan caracteres
adicionales; se conserva candidata pendiente, sin forzar la clasificación. Metadata
frontal puede reconocerse sin outlines; la ausencia de jerarquía no inventa niveles.

## Límites explícitos

Los cuatro nodos no localizados incluyen la raíz cuyo título está truncado y tres
subsecciones que no satisfacen igualdad textual normalizada. Hay discrepancias
de codificación, por ejemplo `e` en texto nativo frente a un separador en el marcador;
no se corrigieron reglas para hacer coincidir12.pdf. No se afirman matches parciales
como identidades. Los títulos partidos entre varias cajas siguen siendo limitación.

El matching por centros puede incluir spans compartidos por cajas solapadas y no
garantiza una correspondencia uno-a-uno. Falta validar semánticamente roles, sección
y párrafos. Las pertenencias y continuidades heredan errores de Docling. Las figuras,
tablas, captions y grupos originales permanecen vinculados según evidencia existente;
esta capa no acepta asociaciones nuevas. La pertenencia temática sigue sin resolver.
Los tags Figure con atributos compartidos no localizan figuras individuales. Los
article threads y enlaces se conservan como evidencia candidata, no como orden aceptado.

Los374hijos sin bbox y sus padres de la colección quedan fuera de este incremento;
12.pdf no contiene esos incidentes. Fixtures comprueban que la capa no imputa cajas,
no levanta abstenciones ni elimina padres. No se ha generalizado a otros14papers.

## Aceptación técnica y revisión

17 pruebas offline pasan: PDF sin metadata, Unicode, geometría ausente/rotada,
hijos diferidos, contradicciones, autoría frente a mención, metadata sin outlines,
portada anterior al cuerpo, jerarquía, IDs/punteros, hashes, no-overwrite y bytes PNG.
Revisión independiente detectó dos P2; ambos tuvieron reproducción RED→GREEN y
cierre puntual del revisor. No certifica calidad semántica general.

DOM del HTML exportado:156combinaciones página/filtro/zoom,1773selecciones de región,
18enlaces de jerarquía y selección por teclado comprobados. **No es QA visual real**.
Acceso del navegador a file:// bloqueado por política; no se intentaron alternativas
para sortearla. La vista se entrega para apertura local del usuario.

Contrato y hashes verificados en la auditoría: inventario, clasificaciones originales,
recorrido aprobado, fuentes y renders intactos; punteros resueltos y jerarquía sin
ciclos. Revisión humana acumulada al final del MVP, sin bloquear continuidad.
Una exportación congelada; no repetir, afinar reglas ni ejecutar GROBID/modelos.
Integración canónica, generalización y mejora del recorrido siguen pendientes.

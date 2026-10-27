# Integración completa: plan de implementación

> Ejecución inline con `superpowers:executing-plans`. Diseño aprobado por el
> usuario: `analytics/analyses/collection/demo-integration-structure-v1-design.md`.

**Objetivo:** notebook y paquete autónomo para ejecutar la integración de los
15 papers en Linux/A100 a partir de sus parsings guardados.

**Arquitectura:** copias exactas de los módulos vigentes y auxiliar de colección.
Entradas verificadas → preparación portable → conciliación → clasificación v2 →
inventario/cápsulas → Docling/nativo/estructura/conexión → salidas y respaldo.

**Tecnología:** Jupyter, biblioteca estándar, Python 3.13.5 aislado, versiones y
hash Docling congelados, PyMuPDF. La A100 se registra; el cálculo usa CPU.

## Restricciones globales

Mismo código/configuración para todos los papers. Fuentes y resultados canónicos
intactos. Destinos nuevos; sin reintentos, OCR, modelos o servicios. Abstenciones,
hijos sin bbox y revisión after_full_mvp preservados. Sin Git en esta raíz.

## Focos de revisión

- Punteros de Windows: regenerarlos desde fuentes en el destino Linux.
- Kernel distinto: toda etapa corre con Python 3.13.5 aislado.
- ZIP alterado/rutas inseguras: rechazar antes de ejecutar código empaquetado.
- Fallo de etapa o respaldo: registrar fallo/partial, nunca completado ficticio.
- Traslado de resultados: vistas estáticas portables; procedencia absoluta refleja
  el entorno de ejecución y los fuentes también viajan en el respaldo.

## Tareas

- [x] 1. Pruebas nuevas de contratos (RED): paquete seguro, exportación conciliada,
  destinos nuevos, fallos y respaldo verificable.
- [x] 2. Auxiliares y entorno: `integration_demo/`, locks y snapshot `src/`;
  demostrar GREEN con fixtures y APIs reales.
- [x] 3. Notebook, documentación, constructor de paquete e inputs íntegros;
  verificación de sintaxis, manifests, hashes y cierre de dependencias de archivos.
- [x] 4. Revisión independiente final, correcciones y entrega; registrar evidencia
  local y diferenciar ejecución en A100 pendiente por el usuario.

## Registro de decisiones y progreso

- Diseño aprobado por usuario el 27 de octubre de 2026.
- Preflight: el exportador nuevo produce el contrato requerido por clasificación
  v2; reading export produce el contrato requerido por pipeline canónico.
- Decisión: conservar el código científico sin cambios; entorno mínimo instala
  Docling/docling-slim exactos sin sus extras de modelos, y la clausura completa
  de docling-core/rtree/PyMuPDF con versiones fijadas. El probe prueba el componente
  geométrico por hash e importación; no se presenta como instalación completa OCR.
- Decisión: no ejecutar otra exportación de los 15 papers localmente para preparar
  la demo; pruebas sintéticas ejercitan todas las etapas con las APIs reales.

- RED observado: import ausente de los auxiliares; después 8 contratos GREEN.
- Ajuste de entorno de pruebas: temporales dentro de la demo por restricciones
  del sandbox Windows; no se cambió lógica científica.
- Hardware corregido por instrucción explícita del usuario: A100.

- 9 pruebas locales GREEN, incluido controller en subproceso con fuentes sintéticas.
- Paquete inicial verificado: 60 miembros, 28 fuentes científicas idénticas.
- Revisión independiente final: sin hallazgos críticos/importantes.
- Precisión documental menor: la descarga Colab usa files.download(); corregida
  junto con referencias residuales al hardware inicial en este plan.
- La entrega final se reconstruye tras esas precisiones y se verifica por SHA256.

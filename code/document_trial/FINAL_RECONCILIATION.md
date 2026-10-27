# Reconciliación documental por decisiones humanas

Incremento aprobado `final-reconciliation-v1`, offline. API:
`build(root)` valida y compone; `export(root, destination)` exporta documento,
vista HTML, manifiesto y hashes previos. Solo bibliotecas estándar, sin modelos,
subprocesos, OCR, inferencias ni regeneración de candidatos.

Lee los trece R mediante hashes del manifiesto de evaluación. Contrasta cada
decisión humana con el candidato, baseline, manifiesto, punteros M0 y evidencia
LM. Seis grupos aceptados y Fig5 simple; Fig6 explícita se deduplica si coincide.
La aceptación reside en el registro humano, no en el estado del generador.
Fuentes originales, geometría, texto y alternativas se conservan por referencia.

Las pruebas `test_final_reconciliation.py` son offline. Ejecutar con PYTHONPATH=code:
`python -m unittest document_trial.test_final_reconciliation -v`.
No repetir exportación para contexto. Un destino incompatible se rechaza.
La vista utiliza renders originales mediante rutas locales; requiere conservar
la estructura del proyecto. La geometría de Fig6 y P7 siguen pendientes.

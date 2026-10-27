# Parsing de un PDF en Google Compute Engine

Preparación autorizada 26oct2026. Solo el usuario crea recursos y ejecuta parsing.
Primer paquete: **10.pdf, nueve páginas, tres parsers**. Configuraciones, pesos,
Python/Torch/CUDA y render200dpi originales. No conciliación automática.

El paquete es nuevo y declara USER_ONLY_GCE_SSH_T4; no simula ser Colab. Conserva
/content para reutilizar los adaptadores originales sin editar rutas de inferencia.
Las únicas fuentes originales modificadas en el ZIP derivado son las guardas y
atribución de document_trial/remote.py y worker.py; originales intactos. Manifiestos
y platform-change.json registran baseline y cambios.

## 1. Subir un archivo a Cloud Shell, antes de crear la VM

Desde el menú **Upload file / Subir archivo** de Cloud Shell sube:

`C:\Users\HP Victus\Desktop\nasa_research\code\packages\sic-gce-v1\sic-gce-v1-paper10.tar.gz`

También puedes usar gcloud instalado en WSL, con acceso al proyecto; no es
necesario instalarlo para la opción Cloud Shell. No pegues credenciales al chat.

En Cloud Shell, desde la carpeta que contiene el archivo:

```bash
tar -xzf sic-gce-v1-paper10.tar.gz
cd sic-gce-v1
export GCE_PROJECT=nasa-512810
export GCE_ZONE=us-central1-a
export GCE_VM=nasa-parsing-t4
```

El TAR solo debe extraerse una vez en un destino nuevo. SHA256 publicado junto
al archivo local en `.tar.gz.sha256`; compara `sha256sum ../sic-gce-v1-paper10.tar.gz`
contra ese valor si necesitas verificar transferencia. El envío vuelve a verificar
ZIP, SHA, miembros y plan antes de contactar la VM.

## 2. Crear la VM y preparar el sistema

**Este comando empieza a generar cargos**: n1-standard-8 (8vCPU/30GB), una T4,
disco persistente150GB, Ubuntu22.04, instancia estándar sin reinicio automático.
No usa Spot ni cuenta de servicio dentro de la VM. Tiene una duración máxima4h
con acción STOP; no es un tope monetario ni garantía de terminar el paper.

```bash
bash gce.sh create
bash gce.sh bootstrap
```

Si ya extrajiste la primera entrega y create informó que falta `--no-scopes`,
desde `~/sic-gce-v1` corrige solo el lanzador; no extraigas de nuevo el paquete:

```bash
sed -i 's/--no-service-account$/--no-service-account --no-scopes/' gce.sh
bash gce.sh create && bash gce.sh bootstrap
```

La omisión impedía crear la VM. `&&` evita intentar bootstrap si create falla.

No repitas create si falla o pierde conexión: inspecciona si existe la VM.
Cuota no garantiza capacidad. Si aparece RESOURCE_POOL_EXHAUSTED, conservar
mensaje y decidir zona; no hay búsqueda/reintento automático. Red default/SSH
y permisos de Compute Engine deben estar disponibles; no se cambian reglas IAM
ni firewall automáticamente.

Bootstrap instala bibliotecas del sistema y driver570-server desde Ubuntu,
sin modelos ni entornos de parsers. Si falla, conservar mensaje y
`/content/gce-bootstrap.log`; no repetirlo ni actualizar modelos para sortearlo.

Una vez que bootstrap muestre **Bootstrap terminado**, reinicia para cargar driver:

```bash
gcloud compute ssh "$GCE_VM" --project="$GCE_PROJECT" --zone="$GCE_ZONE" \
  --command='test -f /content/bootstrap-completed && test ! -e /content/gce-claimed && sudo systemctl reboot'
```

La conexión SSH puede terminar con código255 por el reinicio. Espera a que la VM
arranque y comprueba una vez:

```bash
gcloud compute ssh "$GCE_VM" --project="$GCE_PROJECT" --zone="$GCE_ZONE" \
  --command='nvidia-smi'
```

Debe aparecer una sola TeslaT4 y driver>=560.28.03. El servicio comprueba de
nuevo GPU, driver, metadata de proyecto/VM/zona/ID numérico y al menos60GiB libres antes
de iniciar. Las comprobaciones originales de cada entorno siguen intactas.

## 3. Enviar el intento una vez

Desde `sic-gce-v1` en Cloud Shell:

```bash
bash gce.sh submit package runs/paper10-01
```

Genera UUID nuevo, verifica paquete, copia por SCP y crea servicio systemd
`nasa-parsing-UUID`, sin Restart y con RemainAfterExit para conservar su estado
al terminar. **Enviado no significa completado**. Puedes
desconectar SSH/Cloud Shell: el servicio sigue dentro de la VM mientras esta
permanezca encendida. No depende de una sesión Colab.

No vuelvas a ejecutar submit si tarda, pierde conexión o devuelve error. El
directorio del intento y `/content/gce-claimed` evitan reutilizarlo. Un error
ambiguo exige status y revisión del mismo intento, sin nueva inferencia.

## 4. Consultar progreso

```bash
bash gce.sh status package runs/paper10-01
```

Muestra ActiveState/SubState/ExecMainStatus y últimas35 líneas. `active/running`
puede incluir instalación o descarga; no certifica inferencia. `active/exited`
significa que el proceso salió y systemd conserva la unidad. Registros detallados en
`/content/nasa-sic12-document-v1/commands/` y consola en `/content/gce-console.log`.
`failed` conserva el fallo; no lanza recuperación.

## 5. Descargar y verificar al terminar

Cuando el servicio termine:

```bash
bash gce.sh collect package runs/paper10-01
bash gce.sh stop package runs/paper10-01
```

collect exige ZIP/sidecar existentes, los descarga una vez y verifica SHA/CRC,
plan, bundle, UUID, proyecto/VM/zona/ID numérico y estados por página/parser; para completed
exige identidad/render y archivos nativos requeridos. Guarda backup-verified.json.
Un respaldo **failed** puede estar técnicamente verificado: no significa éxito
del parsing. stop revalida los bytes actuales y exige unidad existente y terminada
(inactive, failed o active/exited por RemainAfterExit)
antes de detener la VM. También verifica contra Compute Engine que la VM conserva
el ID numérico ligado antes del envío: recrearla con el mismo nombre bloquea la
acción. collect nunca detiene; stop nunca vuelve a inferir.

Resultados en `runs/paper10-01/result.zip`, `result.sha256`, attempt.json,
backup-verified.json y logs de transferencia. Descarga la carpeta a tu PC mediante
Cloud Shell antes de borrar nada. Para avisar al agente basta indicar dónde quedó
el ZIP/sidecar; se verifican offline. No ejecutar document_trial.offline ni el
reconciliador automáticamente: recepción comparable sigue siendo etapa separada.

Si collect falla, **no hay permiso implícito para cerrar ni relanzar**. El primer
fallo de disponibilidad remota no crea receipt-started; tras iniciar descarga,
ese directorio evita repetirla automáticamente. Conserva parciales y solicita
revisión. El ZIP solo se publica al finalizar: un archivo presente por sí solo
no es respaldo verificado.

## Límite temporal, persistencia y presupuesto

La VM se detiene al alcanzar su límite4h; puede interrumpir instalación o parsing.
El disco persistente conserva archivos, pero un intento interrumpido puede no
tener ZIP terminal y no se reanuda/repite automáticamente. No habilitamos el
servicio al arranque. Reiniciar/arrancar la VM para recuperar archivos no debe
iniciar parsing; aun así verificar estado antes de intervenir. El límite de
duración se aplica a la ejecución de VM y no promete presupuesto total de USD50.

El almacenamiento persistente y otros recursos pueden seguir generando cargos
con VM detenida. Tras copiar y verificar resultados en tu PC, puedes eliminar VM
y disco desde Console; comprueba primero qué recurso estás borrando. Esta guía
no ejecuta eliminación. No mantener una GPU encendida entre intentos.

No reutilizar este /content para otro PDF: revisión de la primera ejecución real
antes de preparar siguiente incremento. No se ha validado todavía instalación
ni parsing real en Compute Engine; pruebas offline no acreditan compatibilidad
real o velocidad de ejecución.

## Fuentes oficiales consultadas

- [Crear N1 con GPU T4](https://docs.cloud.google.com/compute/docs/gpus/create-gpu-vm-general-purpose)
- [Límite de duración de una VM](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime)
- [Instalación de drivers en Compute Engine](https://docs.cloud.google.com/compute/docs/gpus/install-drivers-gpu)
- [Drivers NVIDIA en Ubuntu Server](https://ubuntu.com/server/docs/nvidia-drivers-installation/)
- [Requisitos CUDA12.6](https://docs.nvidia.com/cuda/archive/12.6.0/cuda-toolkit-release-notes/index.html)
- [Precios GPU](https://cloud.google.com/products/compute/gpus-pricing)

## Preparación local adicional (offline, no ejecutar para el paquete entregado)

```bash
PYTHONPATH=code python3 -B -m document_trial.gce_package \
  --base code/packages/sic-parsing-v1/10 \
  --output code/packages/DESTINO_NUEVO \
  --release code/packages/ARCHIVO_NUEVO.tar.gz
```

Nuevos destinos obligatorios. No reconstruye ni toca ZIP originales, no descarga
pesos y no crea VM. Su uso para otros PDFs requiere decisión de alcance posterior.

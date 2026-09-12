# Wisp Desktop 0.14

Una primera versión funcional del compañero: observa el sistema, conserva las
observaciones importantes, explica su evidencia y ofrece un panel GTK4 con un
avatar interactivo para Wayland. La estética usa el Wisp v0.12, grafito, cian,
acentos violeta y animación discreta.

![Panel GTK real con datos de demostración](previews/wisp-v0.14.png)

La imagen es una captura de la aplicación nativa con datos de ejemplo. El modo
normal usa sensores reales. Esta rama implementa la primera entrega de la
arquitectura v0.13.1; las capacidades futuras no se presentan como terminadas.

## Iniciar

Requisitos: Linux, Python 3.10 o superior, GTK4 4.8 o superior con introspección,
PyGObject y Pycairo para el mismo intérprete. Pillow se usa al compilar el atlas.
El servicio y `ccctl` usan exclusivamente la biblioteca estándar de Python.

Para el avatar ambiental: Wayland, un compositor compatible con layer shell
(como Hyprland) y `gtk4-layer-shell` con su typelib. El panel también funciona
sin esa biblioteca y en X11. El escritorio debe proporcionar `XDG_RUNTIME_DIR`.

Desde tu checkout:

```bash
git fetch origin
git switch codex/wisp-desktop-v0.14
python3 scripts/desktop-doctor.py
python3 scripts/build-wisp-v2.py --atlas-only --jobs 2
scripts/run-desktop.sh
```

El lanzador inicia un único servicio de sesión, espera a que responda y abre el
panel. Cerrar la interfaz conserva el monitoreo. No requiere root. Si el Python
predeterminado no tiene acceso a GTK, selecciona el que sí lo tenga:

```bash
CYBER_COMPANION_PYTHON=/usr/bin/python3 scripts/run-desktop.sh
```

Para probar únicamente la interfaz, sin iniciar el servicio ni escribir sus
preferencias:

```bash
scripts/run-desktop.sh --demo --no-avatar
```

Para añadir Wisp al menú de aplicaciones, ejecuta con ese mismo Python:

```bash
python3 scripts/install-desktop.py
```

El instalador crea lanzadores de usuario en `~/.local/bin` y una entrada en el
menú. Apuntan al checkout: conserva su ubicación o vuelve a ejecutar el
instalador al moverlo. Por defecto no modifica autostart ni Hyprland. La opción
`--hyprland` añade un include administrado, inicio del avatar y Super+Alt+W;
consulta [la integración de escritorio](LIVE_DESKTOP.md).

## Qué puedes hacer

- Ver CPU, memoria disponible, temperatura y espacio libre, con historial visual
  corto. Un dato ausente se muestra como desconocido.
- Revisar carga sostenida, memoria baja, temperatura alta, poco espacio y pérdida
  de la ruta de salida local. La evidencia incluye fuente, lectura y hora.
- Marcar una observación como revisada, posponerla 30 minutos o silenciar avisos
  ordinarios durante una hora. Los avisos térmicos críticos omiten el silencio
  global; se pueden posponer o revisar individualmente.
- Consultar actividad reciente y disponibilidad de cada conexión.
- Preguntar por CPU, memoria, temperatura, almacenamiento o red. Las respuestas
  básicas se construyen con lecturas verificadas; la conversación generativa es
  opcional mediante un modelo local.
- Abrir el panel con clic izquierdo en el avatar; abrir su menú con clic derecho;
  arrastrarlo dentro del monitor; escoger monitor, ocultarlo y reducir movimiento.
  La entrada se limita a una región alrededor del personaje y no reserva espacio
  en el escritorio. `Esc` cierra el panel.

El avatar usa su propia superficie GTK/layer-shell. No ejecutes simultáneamente
el antiguo `run-system.sh` o `run-renderer.sh` si quieres una sola presencia.
El panel normal conserva el foco de una ventana normal; la superficie ambiental
no solicita foco de teclado.

La posición se expresa en coordenadas lógicas del monitor, con márgenes de hasta
2048 unidades. Se vuelve a limitar al área disponible después de cambios de
pantalla. El avatar se oculta al perder el servicio, si no se conoce una sesión
desbloqueada o si la ventana enfocada está a pantalla completa en su monitor.

## Conexiones y configuración

Sin archivo de configuración se utilizan los valores de
[`config/desktop/default.json`](../config/desktop/default.json). Para personalizar,
crea `~/.config/cyber-companion/desktop.json` a partir del ejemplo; no sobrescribas
una configuración que ya hayas modificado. Reinicia el servicio para aplicarla.

| Fuente | Implementación de esta entrega | Opcional |
|---|---|---|
| Sistema | `/proc/stat`, `/proc/meminfo`, hwmon, PSI | Temperatura y PSI pueden faltar |
| Almacenamiento | `statvfs` de rutas locales configuradas | Por defecto solo `/` |
| Red | Interfaces y tablas locales de rutas IPv4/IPv6 | No realiza sondeos de Internet |
| Música | `playerctl`, selección de un reproductor activo | Sí |
| Escritorio | `hyprctl -j`, monitor y espacio de trabajo enfocados | Sí |
| Sesión | `loginctl`, `LockedHint` de `XDG_SESSION_ID` | Su ausencia oculta el avatar |
| Avisos | `notify-send`, reemplazo de avisos del mismo incidente | Sí |
| Virtualización | `virsh --readonly`, enumeración de libvirt | Activar `virtualization` en `sensors` |

La lista de máquinas está disponible en `ccctl --json status`; esta versión no
ofrece controles para iniciarlas o detenerlas. Un fallo de una fuente no detiene
las demás. El indicador de sesión depende de la integración de tu bloqueador
con logind/elogind: hay que comprobarlo en el equipo real.

Los detectores iniciales usan umbrales explícitos:

| Condición | Activación | Recuperación |
|---|---|---|
| CPU | ≥90 % durante 12 s | ≤65 % durante 6 s |
| Memoria usada | ≥90 % durante 12 s | ≤80 % durante 6 s |
| Temperatura | Límite del sensor, o 85 °C en CPU compatible, durante 4 s | 7 °C por debajo durante 6 s |
| Espacio | ≤10 % libre en una lectura | ≥15 % durante 6 s |
| Red local | Sin ruta predeterminada durante 6 s | Ruta disponible durante 6 s |

Los tiempos se confirman al llegar la siguiente lectura; por ejemplo,
almacenamiento se consulta cada 30 s. Los umbrales se definen actualmente en
`core/model.py`; todavía no hay editor de umbrales en el panel. La métrica de
memoria es disponibilidad, no un diagnóstico de la causa de la presión.

## IA local opcional

Instala Ollama y un modelo que quepa en tu equipo usando sus instrucciones
oficiales. Wisp no instala ni descarga modelos. Configura el **servidor Ollama**
para deshabilitar funciones de nube y escuchar en loopback, por ejemplo al
iniciarlo manualmente:

```bash
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

Si ya se ejecuta como servicio, aplica las variables a ese servicio y reinícialo;
ponerlas solo en el proceso Wisp no cambia el servidor. Comprueba el modo local
en los logs de Ollama. [Configuración oficial](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features).

Después, configura en `desktop.json` el nombre exacto de un modelo **local ya
instalado**, y confirma esa configuración:

```json
{
  "version": 1,
  "ollama_model": "NOMBRE_DEL_MODELO_LOCAL",
  "ollama_local_only_confirmed": true
}
```

El nombre es un marcador, no una recomendación de hardware. Los campos omitidos
mantienen sus valores predeterminados. Wisp consulta `/api/show` y luego
[`/api/chat`](https://docs.ollama.com/api/chat), sin herramientas, descargas,
proxies ni redirecciones. Rechaza modelos identificados como remotos. La
configuración del servidor local sigue siendo una condición de confianza.

Se envían la pregunta que escribas, algunas métricas numéricas y categorías de
observación. Se excluyen títulos multimedia, ventanas, rutas, interfaces y
conversaciones anteriores. Las preguntas y respuestas no se guardan. Las
explicaciones de IA se rotulan como interpretaciones. Un fallo del proveedor
produce una explicación básica local. Hay una consulta simultánea, salida y
contexto limitados, y un plazo de respuesta de 42 s. **Descartar** evita que una
respuesta tardía reaparezca; la inferencia ya enviada puede continuar hasta su
plazo. No equivale a cancelar el trabajo dentro de Ollama.

No hay conexión a tu cuenta de ChatGPT ni proveedor OpenAI en esta entrega.
La arquitectura conserva esa extensión para un proveedor con configuración y
consentimiento propios. Ninguna respuesta ejecuta comandos del sistema.

## Terminal, inicio de sesión y actualización

```bash
scripts/ccctl status
scripts/ccctl --json health
scripts/ccctl insights
scripts/ccctl ask '¿Cómo está la memoria?'
scripts/ccctl mute --seconds 3600
scripts/ccctl stop
```

Para usar solo el servicio: `scripts/run-desktop.sh --daemon-only`.
Para iniciar en Hyprland, puedes añadir a tu configuración, usando una ruta
absoluta real:

```ini
exec-once = /ruta/al/repo/scripts/run-desktop.sh --avatar-only
bind = SUPER, W, exec, /ruta/al/repo/scripts/run-desktop.sh
```

El instalador solo añade integración si se usa `--hyprland`. El inicio en la sesión
gráfica conserva las variables del compositor y D-Bus; no hace falta un daemon
de sistema ni privilegios administrativos.

Al actualizar, cierra la interfaz, ejecuta `scripts/ccctl stop`, actualiza el
checkout y vuelve a iniciar. Las preferencias y el historial siguen en
`$XDG_STATE_HOME/cyber-companion/companion.sqlite3`, o `~/.local/state` si la
variable no está definida. La base y el socket son privados al usuario. Los
mensajes de inicio están en `$XDG_RUNTIME_DIR/cyber-companion/daemon.log`.
No se restaura telemetría vieja como estado actual tras reiniciar.

## Validación y límites de esta entrega

La comprobación local incluye la suite existente, nuevas pruebas temporales y
de persistencia, consultas al servicio en memoria, sensores Linux reales, y el
panel GTK4 renderizado y ejercitado en Xvfb. La prueba real de sockets Unix se
omite explícitamente si el host los prohíbe; este fue el caso del entorno de
construcción. No se reemplaza el transporte por un puerto de red.

El workflow `Desktop contracts` ejecuta la suite, el ciclo completo del daemon y
el panel nativo en Linux. Los mismos pasos están disponibles localmente:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/smoke-desktop.py
xvfb-run -a python3 scripts/smoke-ui.py
```

Queda la aceptación en el equipo Gentoo/Hyprland: clic y arrastre, transparencia,
foco, multimonitor, escalado fraccional, bloqueo/desbloqueo, pantalla completa,
suspensión y notificaciones. También queda probar inferencia con tu modelo y
hardware. No hay medición de consumo sostenido en ese equipo todavía.

La detección de pantalla completa solo consulta la ventana enfocada. Las rutas
de almacenamiento deben ser locales: un montaje bloqueado puede retener una
lectura nativa hasta que el kernel la libere. No hay un ejecutor de acciones del
sistema, MCP, voz, chat persistente ni proveedores de nube. La siguiente etapa
está detallada en [el estado de implementación](platform/IMPLEMENTATION_V014.md).

"""Start one session daemon, wait for readiness, then open the native client."""
import os
from pathlib import Path
import subprocess
import sys
import time
from .ipc import call
from .settings import runtime_dir

ROOT = Path(__file__).resolve().parents[1]


def main():
    arguments = sys.argv[1:]
    daemon_only = '--daemon-only' in arguments
    arguments = [a for a in arguments if a != '--daemon-only']
    if '--demo' in arguments or '--help' in arguments:
        os.execv(sys.executable, [sys.executable, '-m', 'cyber_companion.ui.app', *arguments])
    try:
        if not daemon_only:
            result = subprocess.run([sys.executable, '-c', 'import gi; gi.require_version("Gtk", "4.0"); import cairo'], capture_output=True)
            if result.returncode:
                raise ValueError('Instala GTK4, PyGObject y Pycairo para este Python. Consulta docs/DESKTOP_V014.md.')
            if not (os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY')):
                raise ValueError('Abre Wisp desde tu sesión gráfica.')
            atlas = ROOT / 'assets/sprites/companion-wisp-system-v0.12.png'
            if not atlas.exists():
                raise ValueError('Primero genera el avatar: python3 scripts/build-wisp-v2.py --atlas-only')
        directory = runtime_dir()
        try:
            hello = call('hello', timeout=1)
        except (OSError, ValueError):
            hello = None
        if hello is None:
            log_path = directory / 'daemon.log'
            descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as log:
                process = subprocess.Popen([sys.executable, '-m', 'cyber_companion.daemon'],
                    cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                try:
                    hello = call('hello', timeout=.5)
                    break
                except (OSError, ValueError):
                    if process.poll() is not None:
                        break
                    time.sleep(.15)
            if hello is None:
                raise ValueError(f'El servicio no pudo iniciar. Revisa {log_path}')
        if hello.get('version') != 'cc.ipc/1':
            raise ValueError('La versión del servicio es incompatible; reinícialo después de actualizar.')
        if daemon_only:
            print('Wisp está observando el sistema. Usa scripts/ccctl status o scripts/ccctl stop.')
            return 0
        os.execv(sys.executable, [sys.executable, '-m', 'cyber_companion.ui.app', *arguments])
    except (OSError, ValueError) as error:
        print(f'Wisp: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

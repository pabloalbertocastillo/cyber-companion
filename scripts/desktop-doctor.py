#!/usr/bin/env python3
"""Read-only setup diagnostic; does not enable sources or start providers."""
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from ctypes.util import find_library

print(f'Wisp · Python {sys.version.split()[0]} · {sys.executable}')
checks = {'Python ≥3.10': sys.version_info >= (3,10),
          'PyGObject': importlib.util.find_spec('gi') is not None,
          'Pycairo': importlib.util.find_spec('cairo') is not None,
          'Pillow (compilar avatar)': importlib.util.find_spec('PIL') is not None,
          'Sesión gráfica': bool(os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY')),
          'XDG_RUNTIME_DIR': bool(os.environ.get('XDG_RUNTIME_DIR')),
          'Avatar compilado': (Path(__file__).resolve().parents[1]/'assets/sprites/companion-wisp-system-v0.12.png').exists(),
          'gtk4-layer-shell (avatar opcional)': bool(find_library('gtk4-layer-shell'))}
try:
    import gi
    gi.require_version('Gtk','4.0')
    checks['GTK4 introspección'] = True
except (ImportError, ValueError):
    checks['GTK4 introspección'] = False
for name, valid in checks.items():
    print(('✓ ' if valid else '○ ') + name)
for program in ['hyprctl','loginctl','playerctl','notify-send','virsh','ollama']:
    print(f'{program}: {shutil.which(program) or "opcional, no instalado"}')
print('Guía: docs/DESKTOP_V014.md')

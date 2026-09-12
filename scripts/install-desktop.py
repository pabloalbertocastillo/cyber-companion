#!/usr/bin/env python3
"""Install user launchers, optionally integrating with the current Hyprland config."""
import argparse
import os
from pathlib import Path
import shlex
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'Cyber Companion managed launcher'
ICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
<!-- Cyber Companion managed launcher -->
<rect width="128" height="128" rx="28" fill="#0b1822"/>
<path d="M64 17 105 40 105 84 64 111 23 84 23 40Z" fill="#142d39" stroke="#61dec9" stroke-width="3"/>
<path d="M37 49 49 40 79 40 91 49 83 76 64 88 45 76Z" fill="#0a1925" stroke="#368994" stroke-width="2"/>
<path d="M46 55h14l-4 7H43zm22 0h14l3 7H72z" fill="#85f7d9"/>
<path d="m64 70 7 4v8l-7 4-7-4v-8z" fill="#79eacb"/>
</svg>'''


def desktop_quote(value):
    if '\n' in value or '\r' in value:
        raise ValueError('Paths with newlines are unsupported')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value.replace('%','%%') + '"'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix',type=Path,default=Path.home()/'.local')
    parser.add_argument('--hyprland', action='store_true', help='Enable avatar at login and Super+Alt+W through a managed Hyprland include')
    args=parser.parse_args(); prefix=args.prefix.expanduser().resolve()
    files={}
    for name, target in [('wisp','run-desktop.sh'),('ccctl','ccctl')]:
        files[prefix/'bin'/name] = '#!/usr/bin/env bash\n# '+MARKER+'\nexport CYBER_COMPANION_PYTHON='+shlex.quote(sys.executable)+'\nexec '+shlex.quote(str(ROOT/'scripts'/target))+' "$@"\n'
    files[prefix/'share/icons/hicolor/scalable/apps/io.cybercompanion.Wisp.svg']=ICON
    files[prefix/'share/applications/io.cybercompanion.Wisp.desktop']='\n'.join([
        '[Desktop Entry]','# '+MARKER,'Type=Application','Name=Wisp · Cyber Companion',
        'Comment=Tu sistema, en contexto','Exec='+desktop_quote(str(prefix/'bin/wisp')),
        'Icon='+str(prefix/'share/icons/hicolor/scalable/apps/io.cybercompanion.Wisp.svg'),
        'Terminal=false','Categories=System;Monitor;','StartupNotify=true',''])
    hypr_config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'hypr/hyprland.conf'
    include = hypr_config.with_name('wisp.conf')
    source = 'source = ' + str(include)
    original = None
    if args.hyprland:
        if not hypr_config.is_file():
            parser.error('No Hyprland config found: '+str(hypr_config))
        original = hypr_config.read_text()
        if hypr_config.is_symlink():
            parser.error('Hyprland config is a symlink; add the integration manually.')
        files[include] = '\n'.join([
            '# '+MARKER,
            '# Start once per graphical session; launcher ensures one daemon and UI.',
            'exec-once = '+shlex.quote(str(prefix/'bin/wisp'))+' --avatar-only',
            'bind = SUPER ALT, W, exec, '+shlex.quote(str(prefix/'bin/wisp')),
            ''])
    for path in files:
        if path.is_symlink() or (path.exists() and MARKER not in path.read_text()):
            parser.error(f'El destino ya existe y no pertenece a Wisp: {path}')
    for path,content in files.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content)
        path.chmod(0o755 if path.parent.name=='bin' else 0o644)
    if original is not None and source not in original.splitlines():
        backup = hypr_config.with_name('hyprland.conf.before-wisp')
        if not backup.exists():
            shutil.copy2(hypr_config, backup)
        with hypr_config.open('a') as config:
            config.write('\n# '+MARKER+'\n'+source+'\n')
        print('Hyprland: avatar al iniciar sesión; Super+Alt+W abre Wisp. Backup: '+str(backup))
    print('Wisp está en el lanzador de aplicaciones. El checkout debe permanecer en '+str(ROOT))


if __name__=='__main__': main()

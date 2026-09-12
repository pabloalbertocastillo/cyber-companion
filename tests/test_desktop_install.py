"""Host integration must be repeatable and preserve user-owned configuration."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'scripts/install-desktop.py'


class DesktopInstallTests(unittest.TestCase):
    def setup_install(self, root):
        config = root / 'config/hypr'
        config.mkdir(parents=True)
        original = '# Personal configuration\nbind = SUPER, T, exec, terminal\n'
        (config / 'hyprland.conf').write_text(original)
        env = dict(os.environ, XDG_CONFIG_HOME=str(root / 'config'))
        args = [sys.executable, str(INSTALLER), '--prefix', str(root / 'local'), '--hyprland']
        return config, original, env, args

    def test_repeat_install_keeps_one_include_and_original_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config, original, env, args = self.setup_install(root)
            for _ in range(2):
                subprocess.run(args, env=env, check=True, capture_output=True, timeout=5)
            current = (config / 'hyprland.conf').read_text()
            self.assertTrue(current.startswith(original))
            self.assertEqual(current.count('source = '), 1)
            self.assertEqual((config / 'hyprland.conf.before-wisp').read_text(), original)
            self.assertIn('--avatar-only', (config / 'wisp.conf').read_text())
            self.assertIn('SUPER ALT, W', (config / 'wisp.conf').read_text())
            self.assertTrue(os.access(root / 'local/bin/wisp', os.X_OK))

    def test_unmanaged_include_is_not_overwritten_or_partly_installed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config, original, env, args = self.setup_install(root)
            (config / 'wisp.conf').write_text('# This belongs to the user\n')
            result = subprocess.run(args, env=env, capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((config / 'hyprland.conf').read_text(), original)
            self.assertEqual((config / 'wisp.conf').read_text(), '# This belongs to the user\n')
            self.assertFalse((root / 'local/bin/wisp').exists())


if __name__ == '__main__': unittest.main()

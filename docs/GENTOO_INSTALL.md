# Gentoo + Hyprland installation

This phase validates the renderer before Cyber Companion is added to Hyprland
autostart. Commands are intentionally non-destructive.

## 1. Inspect the target system

Run from the Gentoo desktop session:

```bash
echo "===== SESSION ====="
printf 'XDG_SESSION_TYPE=%s\n' "$XDG_SESSION_TYPE"
printf 'HYPRLAND_INSTANCE_SIGNATURE=%s\n' "$HYPRLAND_INSTANCE_SIGNATURE"

echo
echo "===== COMPILER AND BUILD TOOLS ====="
gcc --version | head -n 1
clang --version | head -n 1
cmake --version | head -n 1
make --version | head -n 1
python3 --version
python3 -c 'import PIL; print("Pillow", PIL.__version__)'

echo
echo "===== WAYLAND DEVELOPMENT FILES ====="
pkg-config --modversion wayland-client 2>/dev/null || echo "wayland-client: missing"
pkg-config --modversion libudev 2>/dev/null || echo "libudev: missing"

echo
echo "===== OPTIONAL EVENT SOURCES ====="
command -v playerctl || echo "playerctl: missing"
command -v virsh || echo "virsh: missing"
command -v hyprctl || echo "hyprctl: missing"

echo
echo "===== MONITORS ====="
hyprctl monitors
```

The upstream renderer requires CMake 3.24 or newer, GCC 15 or newer **or**
Clang 19 or newer, Make, `wayland-client` and `libudev`. Wisp Visual v0.12 also
requires Python 3 and Pillow at build time; its generated PNG has no Python or
Pillow runtime dependency.

On Gentoo, Pillow is normally provided by `dev-python/pillow`. Use the package
configuration appropriate for the active Python implementation rather than an
unmanaged system-wide `pip` installation.

Run the project diagnostic after dependencies are available:

```bash
./scripts/doctor.sh
```

## 2. Build and inspect the visual atlas

```bash
python3 scripts/build-wisp-v2.py

python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-system-v0.12.png \
  assets/source/wisp/manifest-system-v0.12.json

python3 -m unittest discover -s tests
```

The atlas is a generated local artifact. The source model, manifest and review
assets remain versioned so the result is reproducible without making the PNG a
second source of truth.

## 3. Minimal pinned renderer build

```bash
./scripts/build-renderer.sh
```

The script generates Visual v0.12 when its atlas is absent, clones the pinned
upstream renderer under the user's XDG data directory, applies the checksum-
pinned patches in `UPSTREAM.lock`, and builds without `sudo` or a system-wide
installation.

Confirm the patched compositor and native state controls independently:

```bash
./scripts/test-renderer-alpha.sh
./scripts/test-renderer-media.sh
```

## 4. Safe interactive test

The launcher reads `config/wpets.conf.example` and intentionally omits
`keyboard_device`; membership in the `input` group is not required.

```bash
CYBER_COMPANION_MONITOR=<monitor-name> ./scripts/run-system.sh
```

Review idle, media-playing and sustained-system-load states on the intended
monitor before enabling autostart.

## 5. Hyprland autostart

Autostart remains deferred until interactive testing succeeds on both monitors.
The expected final form is:

```ini
exec-once = sleep 5 && env CYBER_COMPANION_MONITOR=<monitor-name> /path/to/cyber-companion/scripts/run-system.sh
```

The delay avoids a layer-order conflict with Waybar.

## Rollback

During Phase 0, rollback is stopping the test process, switching back to the
previous branch or configuration, and deleting the user runtime directory. No
OpenRC service, Hyprland autostart entry or system-wide package is created.

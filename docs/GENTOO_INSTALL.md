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

echo
echo "===== EXISTING WPETS/BONGOCAT ====="
command -v wpets || true
command -v wpets-all || true
pgrep -a -f 'wpets|bongocat' || true
```

Do not install anything until the output has been reviewed. The upstream build
currently requires CMake 3.24 or newer, GCC 15 or newer **or** Clang 19 or
newer, Make, `wayland-client` and `libudev`. Only one supported compiler is
required.

## 2. Planned source build

The target location follows the workstation convention of keeping development
tools under `/data`:

```bash
mkdir -p /data/Development/tools
cd /data/Development/tools
git clone https://github.com/furudbat/wayland-vpets.git
cd wayland-vpets
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

Do not run `sudo cmake --install build` during the first validation. Run the
binary directly from the build tree after confirming its generated path.

## 3. Safe test configuration

Copy `config/wpets.conf.example` to an XDG user configuration directory. The
prototype intentionally omits `keyboard_device`; it does not require membership
in the `input` group.

The first test will use a bundled upstream sprite. The original Wisp artwork
will be enabled only after a proper sprite sheet exists.

## 4. Hyprland autostart

Autostart is deliberately deferred until interactive testing succeeds on both
monitors. The expected final shape is:

```ini
exec-once = sleep 5 && /path/to/wpets-all --watch-config --config ~/.config/cyber-companion/wpets.conf --monitor DP-2
```

The five-second delay avoids a documented layer-order conflict with Waybar.

## Rollback

During Phase 0, rollback is simply stopping the test process and removing the
user configuration directory. No OpenRC service, Hyprland autostart entry or
system-wide package is created.

# Desktop interaction and visual design

Status: **proposed v0.13.1 product/architecture design**. Date: **2026-09-07**.
No graphical behavior described here is newly implemented by this document.
This extends [ADR-0004](../adr/0004-wayland-vpets-is-an-ambient-renderer.md)
and moves useful interaction into A2, ahead of advanced AI and renderer effects.

## 1. Product direction

Wisp should feel present in the desktop: responsive to meaningful system events,
easy to consult and visually expressive. Keep its cyberpunk identity, holographic
core, readable silhouette and upright poses. Add clarity and interaction before
expanding animation complexity.

The interface has three coordinated surfaces:

| Surface | Job | First useful content |
|---|---|---|
| Ambient Wisp | Quiet presence and attention cue | Idle, media, busy, warning, unavailable |
| Companion panel | Understand and act on a specific issue | Status, evidence, insights, acknowledge/snooze, settings |
| Command entry | Open the companion explicitly | App launcher and configurable Hyprland shortcut; later a question field |

Notifications lead to the same insight detail. Closing a notification does not
mean a condition was resolved. One incident owns one notification identity and
one panel entry; media activity remains ambient. When AI is absent the panel still
explains observed values using deterministic Spanish templates.

## 2. Native interface decision

Use **Python + GTK4/PyGObject** for the first panel, in a separate `companion-ui`
process. Evaluate **gtk4-layer-shell** for an anchored panel and a selectable
interactive Wisp renderer. A normal GTK toplevel provides the first panel/fallback
where layer-shell or focus behavior is unavailable. The daemon stays usable
without installing GUI libraries.

gtk4-layer-shell supports GTK desktop surfaces with placement and keyboard/input
controls, and exposes introspection for Python. That fits the existing Python
core and a small native interface. Exact GTK/library/compositor versions must be
pinned and accepted on Gentoo before declaring the interactive backend supported.
[Upstream library](https://github.com/wmww/gtk4-layer-shell),
[API reference](https://wmww.github.io/gtk4-layer-shell/gtk4-layer-shell-GTK4-Layer-Shell.html).

| Candidate | Decision and tradeoff |
|---|---|
| GTK4 panel + optional layer-shell renderer | First candidate; reuses Python and native controls; target focus/input tests are mandatory |
| Extend Wayland V-Pets for panel/chat/approvals | Keep it limited to ambient compatibility; application UI would substantially enlarge the patch surface |
| Qt/QML shell | Reconsider if the GTK rendering spike fails its measured goals; requires a separately proven layer-shell/binding/package path |
| Web/Electron shell | Defer; introduces another runtime and desktop integration boundary without resolving current input/focus needs |

The panel can ship while the current Wisp renderer remains selected. Avatar
click/hover ships only with the new interactive backend after its acceptance.
Do not place a separate invisible clickable overlay over Wayland V-Pets: its
position, scale and hit region would drift independently from the visible avatar.
The interactive backend initially reuses the v0.12 atlas; one process owns its
painting and input geometry. Exactly one ambient backend is active at a time.

## 3. Interaction behavior

| Gesture/context | Result | Core boundary |
|---|---|---|
| Open from launcher/shortcut | Show panel and latest status | Read-only snapshot/subscription |
| Left click on interactive Wisp | Toggle panel; open active issue when relevant | Select stable insight ID; no implicit remediation |
| Hover on Wisp | Delayed short status label; no keyboard focus | Local presentation only |
| Right click | Menu: open, mute, position/monitor, settings, hide avatar | Explicit bounded preference commands |
| Position mode + drag | Move within selected output, then save anchor/margins | Local drag preview; persist once on drop |
| Esc in panel | Close panel/menu and release focus | Cancel local presentation; running task remains explicitly visible |
| Explain | Deterministic evidence detail; optional local AI when enabled | `insight.explain` task with bounded context |
| Cancel task | Request cancellation and show acknowledged outcome | Task ID; never claim an OS effect was undone |
| Snooze/mute | Apply chosen duration and show expiry | Exact reversible preference, no redundant confirmation |
| Execute a stateful proposal | Show concrete target, consequence and fresh preconditions | Core policy, exact approval and audited executor |

The initial A2 panel enables only implemented methods. The AI question field and
external actions become available at A4/A3 respectively. Disabled providers show
an informative state, not an input that silently discards requests.

## 4. Panel layout and visual language

Initial layout target: 400 logical pixels wide, maximum height 70% of the output,
with scrolling and responsive text scaling. It has a clear reading order:

1. Compact header: Wisp mark, status, connection state and settings.
2. Active insight or calm system summary, with one useful primary button.
3. CPU/memory/storage/network cards; unavailable values explicitly labeled.
4. Expandable evidence with age, source and recent transitions.
5. Optional question/response area with visible provider and cancellation.

This is a functional target, not a screenshot of an existing panel. Spanish is
the first user-facing locale; labels use translation keys and units are explicit.
Protocol names, queue sizes and storage details stay in diagnostics, not normal
flows. User/model/media text is escaped plain text; never inject it into GTK
markup, HTML, CSS or a shell command.

Proposed design tokens:

| Token | Initial intent |
|---|---|
| Panel background | Opaque dark navy (`#101722`) with a subtle border; optional translucency after readability testing |
| Primary text | Soft near-white (`#EAF2F8`), scalable system font |
| Accent | Cyan/teal (`#55DDE0`), used for interaction/focus |
| Media | Violet (`#AA8CFF`) |
| Warning / critical | Amber (`#FFC56B`) / coral (`#FF767D`), always accompanied by icon and text |
| Motion | Calm breathing, short intentional transitions, reduced-motion mode |

Keep bloom around the character instead of behind small text. Test contrast on
dark, bright and animated wallpapers; the listed colors alone do not constitute
an accessibility result. Prefer crisp native text, clear keyboard focus and
consistent hit targets over densely packed HUD decoration.

## 5. Input, focus and Wayland constraints

The ambient surface uses no keyboard focus. Its input region covers a stable,
generous avatar silhouette/hit target; transparent surroundings pass pointer
events through. Shape should not oscillate on every animation frame. Input
geometry uses logical coordinates and follows resizing/scale changes.
GTK distinguishes transparency from the input region: transparent pixels alone
do not make a window click-through.
[GDK input regions](https://docs.gtk.org/gdk4/method.Surface.set_input_region.html).

The panel requests keyboard interaction only after explicit opening. Use the
pinned layer-shell library's supported on-demand mode if the compositor passes
focus tests; otherwise use the normal toplevel. Never retain an exclusive keyboard
grab while idle. Esc/close releases focus and should return it naturally to the
previous app; test this with the Windows VM, terminal and application launcher.
Do not force-focus a saved window that has disappeared or changed.

Layer-shell surfaces are desktop surfaces, not normal tiled windows. Workspace
visibility is a companion policy based on desktop observations; do not assume a
Hyprland normal-window rule can pin the layer surface to one workspace.
The shell uses output-relative anchors/margins and zero reserved exclusive zone,
so it does not resize tiled applications. Cross-output movement starts with a
monitor menu; global-pointer tracking is unnecessary for the first release.

No `/dev/input` access, global keylogger, screen capture or always-on microphone
is needed. Global launch shortcuts are configured through the desktop; check for
conflicts and do not overwrite existing bindings automatically.

## 6. Monitor, workspace and session policy

The UI owns surface realization; the core owns semantic visibility/attention
preferences. Hyprland adapters publish output/workspace/fullscreen facts over the
same ingress as other sensors. Use documented IPC and query snapshots after
reconnect; discard window titles/addresses unless a specific enabled feature
needs them. Current documentation is version-sensitive, so retain fixtures for
the actual installed compositor before changing configuration syntax.
[Hyprland IPC](https://wiki.hypr.land/IPC/).

| Environment event | Expected behavior |
|---|---|
| Two monitors | One Wisp pinned to selected output by default; optional follow-focused-output mode with dwell |
| Workspace change | Refresh context; no notification simply because focus changed |
| Fullscreen app/VM | Hide or minimize ambient Wisp by default; opening panel remains an explicit action |
| Output unplugged | Recreate surface on configured fallback, clamp margins; retain preferred output for return |
| Scale/resolution change | Recompute logical layout, hit region and raster scale; no off-screen panel |
| Session locked or lock state unknown | Hide sensitive panel/bubbles; close known private notifications and retain insight internally |
| Session unlocked | Fresh reconciliation; show at most a concise pending summary, not the entire missed notification stream |
| Resume | Invalidate observations, reconnect sources and display updating/unknown until confirmed |
| Compositor/UI crash | Continue daemon observation; reconnect UI to a new snapshot |
| Renderer/backend switch | Hand off the single ambient owner; resend semantic state, avoid duplicate Wisp instances |

The future setup can reuse the user's selected monitor without hardcoding output
names or hardware IDs into shared defaults. Persist logical placement with
output identity/fallback, never only physical desktop coordinates.

Critical insights bypass quiet hours when the session is known unlocked. They
remain in the panel if the notification server refuses display. Locked-session
notification exposure is explicitly configured and generic only; never draw an
overlay over the locker. The desktop notification service can apply its own
display policy, so successful delivery is not proof the user saw the message.
[Desktop notification specification](https://specifications.freedesktop.org/notification/latest/).

## 7. Renderer-neutral visual contract

The core publishes a proposed `cc.presentation/2` snapshot with independent axes:

| Axis | Examples | Owner |
|---|---|---|
| System presence | idle, busy, warning, unknown | Deterministic detector/attention policy |
| Interaction | closed, open, thinking, responding, awaiting_approval, error | Task/interaction service |
| Ambient context | media_playing, focus, quiet | State and user preference |
| Content | Insight/task references and localized text | Presentation broker |
| Motion preference | reduced, standard; intensity cap | User configuration |

The renderer returns a capability declaration (semantic states, click/hover,
text, motion, theme schema, protocol major). The broker maps unsupported states
to an explicit fallback. An unavailable feature never silently becomes an OS
action. Warning severity remains visible while thinking/media cues play; the
character does not oscillate between independent one-winner animations.

Animation owns interpolation/easing/blinking and frame pacing. It does not need
60 telemetry events per second. Use frame callbacks, stop rendering hidden
surfaces, and cap effects/texture memory. Reuse the current authored atlas rate
independently of compositor refresh. Asset validation covers state IDs, duration,
safe bounds, alpha, scale, transition continuity and fallback poses.

Graphic iteration sequence:

1. Preserve v0.12 art; add the panel, stable placement and clear semantic cues.
2. Prove interactive atlas rendering/input on Gentoo, then enable avatar gestures.
3. Add expressions/poses for attention, thinking, confirmation and recovery.
4. Evaluate richer rig/shader effects only against measured CPU/GPU/frame budget.

Themes and assets have versioned manifests and generators; schemas can add new
poses without changing sensor/domain logic. Do not replace reusable generated
source with hand-edited output sprites. Graphic improvements ship independently
from AI providers and capabilities.

## 8. Delivery gates and rollback

| Slice | Observable acceptance | Rollback |
|---|---|---|
| A2a: panel + status/insights | Open via launcher, inspect fresh values, acknowledge/snooze, survive daemon reconnect | Disable UI; CLI and existing avatar remain usable |
| A2b: desktop awareness | Monitor changes, fullscreen, lock and resume follow the table above | Disable desktop adapter; retain explicit safe placement/hidden sensitive output |
| A2c: interactive avatar | Click-through background, hover/click, focus release and monitor selection work | Select Wayland V-Pets backend and launcher-based panel |
| A3/A4: assistance | Exact action choices and evidence-based local explanations | Disable action/model capability; preserve observations and panel |

Target-host acceptance must include both physical monitors, bright/dark/video
wallpapers, 100/125/150% scale where supported, VM fullscreen, Waybar/launcher,
keyboard-only navigation, no pointer interception outside Wisp, output unplug,
lock/unlock, suspend and process restarts. Capture short demonstrations and
measure idle/active CPU, RSS, GPU memory and frame pacing separately from AI.
Compare to current v0.12 on the same host; no performance claim is accepted from
an unmeasured mockup. No automated test replaces the real Wayland focus gate.

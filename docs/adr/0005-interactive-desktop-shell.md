# ADR-0005: Deliver an independent native interaction shell early

- Status: Proposed
- Date: 2026-09-07
- Extends: ADR-0004; refines the A2/A6 delivery split

## Context

The user wants stronger graphics and integration/interactivity with the desktop
as well as reliable system assistance. The v0.13 roadmap delayed a panel and
avatar interaction until A6, while the current renderer only receives a small
set of ambient signal profiles. The useful functional generation needs a place
to read evidence, select an issue and control attention before advanced AI.

## Decision

Bring the native panel, desktop context and an interactive-backend evaluation
into A2. Use a separate Python/GTK4 client with optional gtk4-layer-shell support.
Its first panel may be a normal toplevel. It consumes the versioned local API;
it never reads the database, probes the system or calls model providers directly.

Keep Wayland V-Pets available as ambient compatibility. The new interactive
backend initially paints the existing atlas and owns its own input region.
Select exactly one ambient backend; do not add an invisible input overlay over
the old renderer. New visual poses and richer effects follow input/focus acceptance.

Stateful OS actions still require core capabilities/policy/audit. Explicit
reversible companion preferences such as mute/snooze are allowed without a
second confirmation; model/background proposals receive separate evaluation.

## Consequences

- Functionality becomes visible and usable before optional AI is installed.
- Graphics and GUI dependencies remain replaceable outside the headless core.
- Existing art and native renderer remain valid migration/rollback assets.
- GTK/layer-shell packaging, focus and input behavior need target-host tests.
- Supporting two selectable ambient backends adds compatibility work, but not
  two simultaneously authoritative behavior engines.
- The panel is shipped first; direct Wisp clicking is not promised on the legacy
  renderer or before the interactive backend passes acceptance.

## Alternatives

Waiting until A6 unnecessarily postpones the human interface. Expanding the
upstream C++ animation renderer into a chat/approval shell couples application
features to patches. A full Qt/QML rewrite remains an alternative if the GTK
spike fails measured acceptance; no replacement is selected on aesthetics alone.

## Acceptance

See [desktop interaction](../platform/DESKTOP_INTERACTION.md) for the behavioral
matrix and visual requirements. Losing UI/renderer must not stop monitoring.
An idle avatar never steals keyboard focus, transparent surroundings pass input
through, and all sensitive surfaces obey session-lock policy. Renderer changes
must require no domain, capability or provider implementation changes.

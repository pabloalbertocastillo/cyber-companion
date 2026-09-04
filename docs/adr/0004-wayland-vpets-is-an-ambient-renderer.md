# ADR-0004: Keep Wayland V-Pets as an Ambient Renderer

- Status: Proposed
- Date: 2026-09-04
- Decision owners: Cyber Companion maintainers

## Context

Wayland V-Pets has proven that Wisp can run as a lightweight Hyprland overlay,
accept a custom atlas and react through patched native signals. Wisp Visual
v0.12 substantially improves visual quality while preserving that adapter.

The renderer still exposes only a small animation-state surface. A helpful
assistant also needs explanations, history, notification actions, progress,
approvals and cancellation. Encoding every product function as another sprite
row or POSIX signal would couple functionality to one renderer and make critical
information inaccessible as text.

## Decision

Wayland V-Pets remains the initial **ambient avatar renderer**. It receives
renderer-neutral semantic presentation states through a compatibility adapter.
It is not responsible for system observation, attention decisions, text,
interaction, action approval or AI state.

The platform introduces a presentation broker with independent output ports:

- ambient avatar;
- textual desktop notification/message;
- terminal/control surface;
- optional voice;
- future rich layer-shell UI.

Critical alerts and approvals always have an inspectable textual surface. The
avatar may reinforce them but never be the only channel.

A custom `wlr-layer-shell` renderer can be evaluated later for hover/click,
speech bubbles and richer live animation. It must consume the same semantic
presentation contract and may not query system adapters or state directly.

## Consequences

Positive:

- current visual investment and known-good runtime remain usable;
- functionality can advance without a renderer rewrite;
- explanations and approvals are not constrained by sprite mechanics;
- renderer failure degrades ambience, not system assistance;
- a future richer renderer can replace the adapter cleanly.

Negative:

- multiple presentation processes/channels require coordination;
- the current avatar cannot initially display rich inline interaction;
- some semantic states map approximately onto existing compatibility rows;
- a custom renderer remains future work.

## Alternatives rejected

### Extend the patched renderer for every UI function now

Rejected because it would turn an upstream animation overlay into the
application shell and increase patch maintenance before product contracts are
stable.

### Replace Wayland V-Pets immediately

Rejected because it delays functional work and discards a stable, visually
successful adapter without architectural necessity.

### Use desktop notifications only

Rejected because the ambient character is the project's distinctive interface.
The correct design is multiple coordinated channels.

## Fitness checks

- stopping Wayland V-Pets does not stop state, insights, local API or audit;
- no adapter/detector imports a renderer module;
- all critical insights and approval requests have a textual representation;
- semantic presentation fixtures can be applied to a fake renderer;
- replacing the ambient renderer changes no domain, action, AI or policy code.

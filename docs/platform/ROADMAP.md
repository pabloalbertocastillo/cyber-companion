# Functional Platform Roadmap

Status: **proposed delivery sequence**

Updated **2026-09-07**: [reviewed state](REVIEW_2026-09-07.md),
[runtime contract](RUNTIME_INTEGRATION_CONTRACT.md) and
[desktop interaction](DESKTOP_INTERACTION.md) refine the gates below.
PR #4 implements only the initial envelope/compatibility portion of A1.
All four preceding PRs remain drafts at this review; none is a host acceptance.

## Delivery principle

Implementation follows small vertical slices. Every slice must be useful,
reversible, tested on the target Gentoo + Hyprland host and independently
reviewable. The project does not pause functionality for a long platform
rewrite, and it does not add an AI provider before the capability/policy
boundary exists.

Each release preserves the current Wisp v0.12 ambient behavior through a
compatibility adapter until a replacement renderer is explicitly accepted.

## Phase A0 — Architecture v0.13

Scope of this documentation-only change:

- audit the current v0.11/v0.12 implementation;
- define the modular-monolith target;
- specify Event Envelope v2 and delivery/retention classes;
- define typed state, insight and attention contracts;
- define capability, plan, approval, execution and audit boundaries;
- define local/cloud AI provider and context/memory boundaries;
- place MCP at the interoperability edge;
- record ADRs and implementation gates.

Acceptance:

- no runtime code or dependency changes;
- all design documents versioned in one stacked branch/PR;
- explicit migration path from the current branch;
- unresolved choices identified as implementation decisions, not hidden
  assumptions.

## Phase A1 — Core v2 foundation

Goal: replace prototype runtime mechanics without changing visible behavior.

First gate, before adding persistence or connecting v2 to the controller:

- close review findings F03–F06/F08: deep payload immutability, actual runtime
  type/enum validation, payload schemas, component failures and privacy labels;
- fix the existing sprite-test expectation for v0.12 (F10);
- validate thermal/sensor-loss transition semantics before allowing coalescing;
- record a green relevant baseline with the new rejection/mutation scenarios.

Deliverables:

- Event Envelope v2 types and schema registry;
- compatibility ingress for current v1 MPRIS/system events;
- asynchronous bounded event backbone;
- single ordered reducer lane and isolated consumer queues;
- delivery classes and latest-value telemetry coalescing;
- SQLite WAL store with migrations, durable event positions and snapshots;
- component supervisor, health states, graceful cancellation and backoff;
- generated JSON diagnostic snapshot for compatibility;
- current behavior rules and Wayland V-Pets signals connected through adapters;
- scenario replay test harness.

Acceptance gate:

- Wisp idle/media/system-busy behavior is visually unchanged;
- existing Python and renderer contract tests pass;
- one deliberately blocked consumer cannot delay reducers;
- telemetry flooding remains memory-bounded and newest data wins;
- a killed optional adapter enters degraded/backoff without terminating core;
- state reconstructed after restart matches deterministic replay fixtures;
- no AI/model dependency is introduced.

## Phase A2 — System awareness and proactive attention

Goal: make the companion observably useful before adding AI.

Deliverables:

- typed reducers for system, storage, network, media, session, desktop,
  virtualization and component health;
- freshness/TTL and source-quality metadata;
- adapters for storage, network, Hyprland context, libvirt and session state;
- deterministic detectors and correlated insight lifecycle;
- attention manager with cooldown, dedupe, quiet hours, snooze and resolution;
- presentation broker with ambient avatar + textual desktop notification;
- local Unix control socket and first `ccctl` commands:

```text
ccctl status
ccctl health
ccctl insights
ccctl insight show <id>
ccctl insight acknowledge <id>
ccctl insight snooze <id> --for 30m
ccctl mute --for 1h
```

Deliver A2 in user-visible slices rather than waiting for every integration:

| Slice | Functional scope | Acceptance |
|---|---|---|
| A2a | System/storage insight, textual output, status/health API and native GTK panel | Inspect evidence, acknowledge/snooze; useful with AI off and legacy avatar selected |
| A2b | Hyprland/session context, network and libvirt adapters, each independently optional | Correct monitor/fullscreen/lock/resume behavior; explicit unavailable sources |
| A2c | Optional interactive Wisp backend using existing atlas; hover/click/monitor placement | Input/focus, output/scale and performance gate on actual Gentoo desktop |

The panel/CLI is the first interface even if A2c needs more work. A2 preferences
use narrow core policy and event audit; external OS mutations wait for A3.
See [desktop interaction](DESKTOP_INTERACTION.md) for controls, native stack,
visual evolution, unsupported-feature behavior and rollback.

Initial scenarios:

1. sustained CPU pressure and recovery;
2. thermal warning and recovery;
3. filesystem free-space pressure;
4. network connectivity lost/restored;
5. Windows VM state transition/failure;
6. adapter/renderer health degradation;
7. media playback as ambient, noninterrupting context.

Acceptance gate:

- every insight has evidence, dedupe key, severity, lifecycle and expiry;
- repeated samples do not create notification storms;
- critical/warning information has a textual channel, not animation alone;
- session lock and quiet-hour behavior is deterministic;
- no adapter chooses presentation or notification directly;
- all core usefulness works with renderer stopped and AI disabled.
- sensitive surfaces hide on locked/unknown sessions; the notification server's
  delivery policy is not treated as proof that the user saw an alert;
- new GUI dependencies remain optional and outside core imports.

## Phase A3 — Safe queries and action framework

Goal: let the companion investigate and later help without providing generic
machine control.

Deliverables:

- capability registry and versioned descriptors;
- first bounded read-only queries:

```text
system.summary
system.processes.top_cpu
storage.filesystems.summary
network.diagnose_local
virtualization.vm.inspect
component.health.list
```

- typed intents, task state machine and deterministic diagnostic workflows;
- policy broker and privacy/risk classifications;
- action-plan, approval and execution/audit schemas;
- executor with deadlines, cancellation, output limits and idempotency;
- approval methods and exact request digests in local API;
- first low-risk actions only after read-only path is proven, candidates:

```text
media.pause
media.resume
insight.snooze
virtualization.vm.start
virtualization.vm.shutdown
```

Acceptance gate:

- no generic shell/code capability;
- read-only diagnostic output is bounded and redacted;
- all actions pass registry -> policy -> approval -> executor;
- argument mutation invalidates approval;
- non-idempotent ambiguous outcomes are not automatically retried;
- complete terminal audit record exists for every attempted action;
- destructive and privileged actions remain denied.

## Phase A4 — Local AI, read-only first

Goal: give Wisp useful natural-language explanations while keeping all context
and inference local.

Deliverables:

- provider-neutral AI gateway and `ModelProvider` port;
- context broker with classification, freshness, redaction and budgets;
- explicit conversation/task memory in SQLite;
- one local provider adapter selected after target-host comparison:
  Ollama or llama.cpp;
- health, cancellation, request concurrency and resource telemetry;
- structured assistant response contract;
- `ccctl ask` and `ccctl insight explain`;
- presentation states for listening/thinking/streaming/error;
- deterministic fallback explanations when provider is unavailable;
- provider/model evaluation fixtures.

First interactions:

```text
What is happening?
How is my system?
Why are you warning me?
Diagnose the network and explain the result.
What changed in the last ten minutes?
```

Acceptance gate:

- default operating mode is local-only or AI-off;
- no model receives secrets or unrestricted raw state;
- the first release supplies no action tools to the model;
- factual claims in explanations can be traced to fresh context items;
- malformed structured output is rejected safely;
- model outage cannot delay or suppress deterministic alerts;
- changing local provider does not change application/domain contracts.

## Phase A5 — Plan proposals, OpenAI and MCP

Goal: add optional higher-quality/cloud reasoning and ecosystem integration
without weakening local control.

Deliverables:

- proposed-plan output and planner validation;
- optional bounded read-only query loop for evaluated models;
- OpenAI Responses provider with `store: false` default, secret-provider key,
  budgets and disclosure audit;
- local-only/local-first/cloud-allowed routing modes;
- no silent local-to-cloud fallback;
- MCP client adapter for allowlisted local stdio servers;
- local wrapping of MCP tools as capability descriptors;
- exact policy/approval/executor path for all imported side-effect tools;
- optional read-only Cyber Companion MCP server for external hosts;
- provider and MCP version pinning/compatibility tests.

Acceptance gate:

- OpenAI API can be completely disabled without config/code changes elsewhere;
- cloud egress tests prove policy and disclosure logging;
- provider-native conversation state is not required;
- model plans reference only registered capabilities and validated arguments;
- an MCP annotation cannot lower locally assigned risk;
- remote MCP remains disabled until authorization/TLS threat model is tested;
- action approval remains visible and local regardless of provider/host.

## Phase A6 — Rich interaction and renderer evolution

Goal: improve the human interface after functionality and safety contracts are
stable. The basic native panel and interactive-avatar evaluation now belong to
A2 under ADR-0005; A6 expands them after real desktop acceptance.

Candidates:

- command palette launched by a Hyprland binding;
- richer history and accessible approval presentation beyond the A2 panel;
- actionable notification buttons;
- optional speech-to-text/TTS adapters with explicit activation;
- richer manipulation/animation beyond the accepted A2 click/hover backend;
- richer live animation state and lip/status synchronization;
- multiple manifestations (Core, Wisp, Sentinel, Guardian, Swarm) driven by
  semantic presentation, not app-specific logic.

Acceptance gate:

- interaction clients use the same local API;
- the daemon still requires no global input capture;
- voice is opt-in and clearly indicates recording/listening;
- replacing Wayland V-Pets changes no domain, insight, plan or policy code;
- accessibility and textual alternatives exist for critical information.

## First implementation PR sequence

To avoid large mixed PRs, Phase A1 should be split approximately as follows:

1. `core/event-v2-contracts` — initial types/mapping exist in PR #4; complete
   strict schemas, immutability, failure identities and relevant test baseline
   in a focused follow-up before connecting the runtime;
2. `core/sqlite-store` — migrations, event/snapshot repositories and tests;
3. `core/async-backbone` — bounded queues, ordered reducer lane and coalescing;
4. `runtime/component-supervisor` — health, lifecycle, backoff and diagnostics;
5. `compat/v011-runtime` — current adapters/director/renderer over Core v2;
6. `test/scenario-replay` — fixtures, failure injection and fitness tests.

No PR should simultaneously redesign events, add an AI SDK and introduce OS
actions.

Minimal first demonstration after A1/A2a: observe a controlled CPU/storage
condition, show one insight in Wisp + panel, inspect its evidence, snooze it,
observe real recovery, stop the renderer and continue querying status. Include
a sensor-loss scenario to prove unknown does not masquerade as recovery. This
is the first release outcome; a general plugin SDK or all integrations are not
prerequisites for that demonstration.

## Versioning and migration policy

- Event envelope, payload schemas, component API, capabilities, action plans,
  local API and database schema have independent versions.
- Breaking contract changes receive a new major schema and a compatibility
  adapter or explicit migration.
- Repository defaults are versioned; user config stays under XDG paths and has
  validated migrations.
- Secrets never appear in repository defaults.
- Generated artifacts remain reproducible and are not treated as source of
  truth.
- Feature flags permit old and new paths to coexist during target-host
  acceptance.
- A compatibility bridge is removed only after its replacement passes replay,
  failure and live Gentoo tests.

## Definition of done for every functional slice

A slice is complete only when it includes:

- contract/schema and migration impact;
- unit and scenario tests;
- failure/cancellation behavior;
- privacy and permission analysis;
- observability/health behavior;
- target Gentoo + Hyprland validation steps;
- rollback instructions;
- updated architecture/ADR when a decision changes;
- no undocumented machine-specific absolute paths;
- a focused PR description with evidence.

## Product outcome

After A4, Cyber Companion is already meaningfully useful: it notices important
system conditions, avoids pestering the user, gathers bounded diagnostics and
explains what is happening locally. A5 adds optional cloud intelligence and MCP;
it is not required to make the companion functional.

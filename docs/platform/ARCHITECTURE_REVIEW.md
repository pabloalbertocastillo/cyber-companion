# Architecture Review: v0.11 Core + Wisp Visual v0.12

Status: **review complete**  
Reviewed ref: `codex/wisp-visual-v0.12` at `1c823ffb42a46ff445470ce0f5a344503d1b2873`

## Executive assessment

The current repository is a strong vertical slice. It has already avoided the
most damaging early mistake: system integrations do not manipulate sprite rows
directly. Adapters publish normalized events, state is reduced centrally,
behavior policy is declarative, and a renderer adapter translates a neutral
presentation command into Wayland V-Pets signals.

That design should be preserved, but it is not yet a platform. The current
controller assumes one process, one synchronous bus, one mutable state document,
one behavior winner, one renderer PID and no user-facing command/action path.
Adding an LLM directly to this shape would create a monolithic agent with weak
failure isolation and an unsafe path from model output to the operating system.

The correct next step is therefore not another adapter and not an AI SDK. It is
to establish stable contracts for events, state, attention, capabilities,
actions, approvals, providers and presentation outputs.

## What is already correct

### 1. Integrations produce facts, not animations

`SystemAdapter` exposes a common lifecycle and publishes through `EventBus`.
MPRIS and Linux telemetry do not know about renderer signals. This is the right
dependency direction.

### 2. Behavior selection is centralized

`BehaviorDirector` is the single presentation authority, while
`BehaviorEngine` loads deterministic priority rules from configuration. A
thermal condition can therefore supersede system load, which can supersede
media, without embedding priority logic in each adapter.

### 3. Presentation is renderer-neutral at the core boundary

`PresentationCommand` carries profile, behavior, intensity and transition.
The concrete SIGRTMIN mapping is isolated in the Wayland V-Pets adapter.

### 4. The initial privacy boundary is conservative

The project does not require root, `/dev/input/event*`, microphone capture or
screen capture. This must remain the default as functionality grows.

### 5. The generated visual pipeline is independent from system logic

Wisp Visual v0.12 can continue improving without changing event or domain
semantics. That separation is valuable and should become a formal renderer
contract rather than an implementation convention.

## Gaps that must be addressed before adding AI actions

### Synchronous event delivery

The current bus invokes every subscriber while holding one re-entrant lock. A
slow subscriber blocks all publishers and all other subscribers. An exception
can interrupt delivery. There is no bounded queue, backpressure policy,
coalescing, subscriber lifecycle, health state or dead-letter path.

**Required evolution:** one ordered reducer lane plus isolated bounded consumer
queues. Critical transitions and audit records must never be silently dropped;
high-frequency latest-value telemetry may be coalesced.

### Thin event identity and causality

The v1 envelope contains version, source, type, timestamp and data. It lacks an
event ID, schema identity, subject, source instance, core sequence, occurrence
versus observation time, correlation, causation, privacy class, freshness and
retention policy.

**Required evolution:** Event Envelope v2, documented separately, with strict
schema validation at ingress.

### Untyped state merging

`StateStore` derives a domain from the event-name prefix and blindly updates a
dictionary with arbitrary payload fields. Old fields never expire, source
quality is not represented, and a malformed but syntactically valid event can
silently reshape domain state.

**Required evolution:** one typed reducer per domain. Domain snapshots include
source, `updated_at`, `expires_at`, freshness and quality. Stale values cannot
silently drive actions.

### Persistence amplification

The complete JSON snapshot is atomically rewritten for every event, including
the two-second telemetry sample. This is acceptable for the prototype but does
not provide history, queryability, retention, migrations or efficient writes.

**Required evolution:** SQLite in WAL mode for journal, snapshots, insights,
plans, approvals and audit. The JSON snapshot remains an optional generated
diagnostic view, not the source of truth.

### Controller as composition root and runtime supervisor

`controller.py` constructs concrete adapters, a concrete signal renderer,
state, rules, logging and threads. The renderer PID is mandatory. Adapter
exceptions become an event, but there is no restart policy, exponential
backoff, circuit breaker, heartbeat, readiness or degraded mode.

**Required evolution:** a small composition root plus a component supervisor.
The core remains healthy when an optional adapter, renderer or AI provider is
unavailable.

### Hard-coded plugin registry

Adding an adapter type requires editing the central factory dictionary. There
is no plugin manifest, API compatibility declaration, configuration schema,
permission declaration or process-isolation option.

**Required evolution:** versioned component manifests and registries. Built-in
plugins can use Python entry points; brittle or less-trusted integrations can
run behind a local stdio protocol in a child process.

### Behavior rules can only select one avatar presentation

A rule supports one `path == value` condition and returns one presentation.
There are no temporal predicates, AND/OR composition, cooldowns, suppression,
deduplication, notification policy, insight lifecycle or action proposal.

**Required evolution:** split three concerns:

1. domain reducers establish facts;
2. detectors create insight candidates;
3. an attention manager decides whether and how to interrupt the user.

The avatar presentation is one output of the attention decision, not the whole
decision.

### No interaction or action boundary

The current system is output-only. It has no local API for `status`, `ask`,
`explain`, `mute`, `approve` or `cancel`; no capability registry; no typed action
plan; no policy decision; no executor; and no audit lifecycle.

**Required evolution:** a versioned Unix-socket API, a `ccctl` client, typed
capabilities and a single policy-controlled executor. This boundary must exist
before a model is allowed to propose any operation.

### Renderer limitations are becoming product limitations

The current renderer adapter can switch among three native signal profiles. It
cannot present explanations, choices, progress, confirmations or actionable
messages. Expanding sprite rows for every function would couple product
capability to animation mechanics.

**Required evolution:** a presentation broker with independent outputs:
ambient avatar, desktop notification/message, CLI/control surface, and optional
voice. Wayland V-Pets remains the ambient animation adapter.

### No AI, context, memory or egress contracts

There is no provider-neutral model port, context minimization, privacy labels,
structured response schema, local/cloud routing, token/cost budget, memory
policy, tool approval or model evaluation harness.

**Required evolution:** AI Gateway + Context Broker + Memory Store behind
application ports. Model output is untrusted data and can only propose typed
plans.

## Risks of adding an LLM now

Adding a provider call directly inside `BehaviorDirector` or `controller.py`
would create the following failure modes:

- event processing waits on network or inference latency;
- critical alerts disappear when the model is unavailable;
- raw telemetry and window/media metadata can leak to a cloud provider;
- model-specific conversation IDs contaminate the core state model;
- hallucinated commands have no independent schema, permission or approval
  boundary;
- changing from OpenAI to a local provider requires application rewrites;
- a prompt injection arriving through external text can influence actions;
- renderer behavior becomes entangled with conversational state.

The v0.13 target architecture explicitly eliminates these paths.

## Preserve, refactor, replace

| Current element | Decision | Reason |
|---|---|---|
| Normalized adapter output | Preserve and version | Correct boundary; envelope needs richer metadata |
| Declarative behavior priorities | Preserve as presentation policy | Deterministic and testable; not sufficient for insights/actions |
| Behavior director | Refactor into attention + presentation services | One avatar winner is too narrow |
| In-process event bus | Replace internals, preserve concept | Needs queues, isolation, delivery classes and replay |
| StateStore dictionaries | Replace with typed reducers/projections | Prevent schema drift and stale state |
| JSON runtime snapshot | Keep as exported diagnostic view | Useful to inspect; inefficient as authoritative storage |
| Hard-coded registries | Replace with manifests/registries | Extensibility and compatibility |
| Wayland V-Pets adapter | Preserve as ambient output | Stable and lightweight; not suitable for rich interaction |
| Renderer signals | Preserve through compatibility adapter | Allows staged migration without breaking v0.12 |
| `run-system.sh` lifecycle | Preserve during migration | Known-good launcher until daemon/control API replaces it |

## Review conclusion

The current project should not be discarded or rewritten in a big bang. The
best path is a compatibility-preserving sequence of vertical slices:

1. install Event v2, async delivery and SQLite beneath compatibility adapters;
2. add typed reducers and system insight/attention services;
3. add local IPC, queries, capabilities, policy and audit;
4. add local AI as a read-only explanation provider;
5. add approved plans/actions and optional cloud routing;
6. expose/import capabilities through MCP only after the native boundary is
   proven.

Each stage remains useful and releasable even if later stages are never enabled.

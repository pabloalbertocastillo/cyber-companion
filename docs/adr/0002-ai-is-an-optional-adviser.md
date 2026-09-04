# ADR-0002: AI Is an Optional Adviser, Not the Control Plane

- Status: Proposed
- Date: 2026-09-04
- Decision owners: Cyber Companion maintainers

## Context

The companion should explain system behavior, answer questions and eventually
help perform approved operations. Language models are useful for interpretation
and planning, but they are probabilistic, provider-specific, latency-sensitive
and vulnerable to untrusted input. Local models can also vary substantially in
structured-output and tool-selection quality.

If model calls become part of reducers, alert detection, permission decisions or
direct execution, provider failure or hallucination becomes a system-control
failure.

## Decision

AI providers are optional infrastructure adapters behind an application port.
They may:

- explain verified insights;
- summarize bounded fresh context;
- interpret a message into a typed intent;
- request allowlisted read-only queries in evaluated modes;
- propose a typed action plan.

They may not:

- mutate domain state;
- decide whether critical facts are true;
- grant permission or approval;
- invoke capability implementations directly;
- suppress deterministic critical alerts;
- write long-term memory directly;
- receive secrets or unrestricted local context.

Every side effect follows capability registry -> deterministic policy -> exact
approval when required -> executor -> audit, regardless of provider.

The companion owns conversation and memory state. Provider-native conversation
objects are optional transport optimizations, never authoritative state.

## Consequences

Positive:

- useful offline and with AI disabled;
- local/cloud providers are replaceable;
- deterministic safety and alerting remain testable;
- model failure degrades explanation, not system awareness;
- prompts and model upgrades do not silently change permissions;
- privacy routing can select or reject providers per task.

Negative:

- the application must implement context, task, policy and execution loops;
- some provider-native agent features cannot be used as the sole orchestration
  layer;
- model tool calls require normalization and evaluation;
- more explicit schemas are required.

## Alternatives rejected

### Let the model continuously watch raw telemetry

Rejected because it increases cost, latency, noise and disclosure while
providing weaker threshold/hysteresis behavior than deterministic detectors.

### Let an agent SDK own tools and memory end to end

Rejected as the platform architecture because it couples core behavior and
security to one provider/runtime. An SDK may be used behind an adapter only if
it preserves local contracts.

### Disable actions forever

Rejected because safe, narrow, approved capabilities can provide real value.
The solution is a strong execution boundary, not eliminating assistance.

## Fitness checks

- removing every model dependency leaves tests for monitoring and alerts green;
- malformed model output cannot create an executable request;
- switching provider adapters changes no domain or capability schema;
- destructive action proposals always reach deterministic policy/approval;
- a model result is labeled provider-generated and cannot overwrite observed
  state;
- local-only mode has a testable zero-cloud-egress property.

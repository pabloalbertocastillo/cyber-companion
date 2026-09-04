# ADR-0001: Use a Local Modular Monolith

- Status: Proposed
- Date: 2026-09-04
- Decision owners: Cyber Companion maintainers

## Context

Cyber Companion runs for one desktop user and must integrate many local event
sources, outputs, model providers and capabilities. The current prototype is one
Python process plus an external Wayland renderer. As functionality grows it
needs stronger module boundaries, bounded concurrency, persistence, supervision
and selective failure isolation.

A distributed architecture would introduce network discovery, multiple service
lifecycles, credentials, protocol drift and operations dependencies without a
current scaling or ownership need.

## Decision

The core will be a local modular monolith:

- one daemon owns event ordering, reducers, state, policy and audit;
- modules communicate through typed internal ports/contracts;
- an asynchronous bounded event backbone isolates consumers;
- SQLite is the local journal/projection store;
- local model servers, renderers and brittle/less-trusted plugins may run as
  supervised external processes;
- no Redis, Kafka, NATS, container orchestrator or mandatory systemd service is
  introduced.

Module boundaries are enforced by dependency tests and contracts rather than by
network calls.

## Consequences

Positive:

- simple installation and rollback on Gentoo;
- deterministic event ordering and transactions;
- low idle resource usage;
- easy local debugging and replay;
- no distributed consistency problem;
- components remain extractable later because ports are explicit.

Negative:

- a severe bug in trusted in-process code can affect the daemon;
- module boundaries require discipline and architecture tests;
- long-running/blocking work must be deliberately moved off the reducer lane;
- process isolation is selective rather than universal.

## Alternatives rejected

### Keep the current single controller without formal modules

Rejected because the composition root already owns too many responsibilities
and would become the natural location for every new integration and AI call.

### Microservices with an external broker

Rejected because one-user desktop scale does not justify the operational and
security surface. It can be reconsidered only if Cyber Companion becomes a
multi-host or multi-user platform.

### Plugin-everything in separate processes

Rejected for the initial core because serialization and lifecycle complexity
would slow development. Separate processes remain available for high-risk or
volatile components.

## Fitness checks

- core state/alerts work with renderer and AI processes stopped;
- a blocked optional consumer does not block reducers;
- no infrastructure SDK is imported by domain modules;
- one local database transaction can advance durable event position and state;
- all required runtime components can start without systemd.

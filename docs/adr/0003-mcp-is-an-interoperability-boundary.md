# ADR-0003: Use MCP Only as an Interoperability Boundary

- Status: Proposed
- Date: 2026-09-04
- Decision owners: Cyber Companion maintainers

## Context

Model Context Protocol provides a standard way for AI hosts to discover and use
tools, resources and prompts. Cyber Companion should eventually consume useful
external capabilities and expose selected companion capabilities to other AI
clients.

MCP does not replace a desktop application's domain event model, durable state,
component supervision, policy language or audit system. Making it the internal
backbone would bind non-AI system behavior to an AI interoperability protocol
and still leave core concerns unsolved.

## Decision

MCP is placed at the platform edge in two optional directions:

1. an MCP client adapter imports allowlisted server tools/resources/prompts;
2. a later MCP server exports selected Cyber Companion resources/capabilities.

Every imported tool is normalized into a local capability descriptor and passes
through local schema validation, privacy classification, policy, approval,
executor and audit. Server annotations are untrusted hints and cannot lower
local risk.

Local stdio servers are implemented first. Remote HTTP servers remain disabled
until TLS, authorization, token audience, egress and lifecycle tests are in
place.

MCP is not used for:

- the internal event bus;
- reducer-to-state communication;
- persistence or replay;
- plugin supervision;
- permission decisions;
- direct renderer control;
- unrestricted tool exposure to a model.

## Consequences

Positive:

- external AI ecosystems can integrate without controlling the architecture;
- native and MCP capabilities receive identical safety treatment;
- the core remains useful without MCP;
- protocol upgrades are isolated in adapters;
- Cyber Companion can later be used by multiple AI hosts.

Negative:

- MCP tools require a normalization layer;
- some remote-server metadata must be overridden locally;
- authorization and transport support add work when remote MCP is enabled;
- imported results remain untrusted and require size/privacy controls.

## Alternatives rejected

### MCP as the internal plugin protocol for every component

Rejected because sensor event throughput, ordered reducers, state replay and
component lifecycle have different semantics. A restricted stdio plugin protocol
may resemble JSON-RPC but is owned/versioned by Cyber Companion.

### Give the model direct access to remote MCP servers

Rejected as the default because it can bypass local capability policy, context
minimization, approval and audit. Provider-native remote MCP may be evaluated
only behind the same allowlist and policy facade.

### Avoid MCP entirely

Rejected because interoperable import/export is strategically useful once the
native boundary is stable.

## Fitness checks

- disabling MCP changes no native monitoring or capability behavior;
- an imported destructive tool cannot auto-run;
- a malicious tool description cannot modify local risk or hidden policy;
- remote credentials never enter model context;
- every imported invocation has a local correlation and audit trail;
- protocol version changes are confined to MCP provider/transport modules.

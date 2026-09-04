# Cyber Companion Platform Architecture v0.13

Status: **proposed architecture; implementation has not started**  
Date: **2026-09-04**  
Target: a local-first, extensible desktop companion that can observe, explain,
notify and safely assist without coupling the system to one avatar renderer or
one AI provider.

This package defines the architectural step from the current v0.11 behavior
vertical slice plus Wisp Visual v0.12 into a durable companion platform.
It intentionally contains design and migration decisions only. Runtime code
must be introduced in later, independently reviewable vertical slices.

## Core decision

Cyber Companion will evolve as a **modular monolith with explicit ports and
adapters**, an asynchronous internal event backbone, typed domain reducers, a
capability and policy boundary for every side effect, and optional AI providers.

The model is never the control plane. The avatar is never the application.

```text
observations -> normalized facts -> domain state -> insights / intents
                                                -> policy / plans
                                                -> presentations
                                                -> approved actions
```

## Documentation map

| Document | Purpose |
|---|---|
| [Architecture review](ARCHITECTURE_REVIEW.md) | What is strong today, what will fail as integrations grow, and what must change |
| [Target architecture](TARGET_ARCHITECTURE.md) | Components, boundaries, dependency rules, deployment and reliability model |
| [Events, state and attention](EVENTS_STATE_AND_ATTENTION.md) | Event v2 envelope, delivery classes, reducers, freshness, insights and interruption policy |
| [Capabilities, actions and security](CAPABILITIES_SECURITY_AND_ACTIONS.md) | Read/write boundary, approvals, executor, secrets, privacy and threat model |
| [AI and MCP](AI_AND_MCP.md) | Local/cloud providers, context and memory, OpenAI integration and MCP placement |
| [Roadmap](ROADMAP.md) | Small implementation slices and acceptance gates |

The key decisions are also recorded as Architecture Decision Records:

- [ADR-0001: modular monolith](../adr/0001-modular-monolith.md)
- [ADR-0002: AI is an optional adviser, not the control plane](../adr/0002-ai-is-an-optional-adviser.md)
- [ADR-0003: MCP is an interoperability boundary](../adr/0003-mcp-is-an-interoperability-boundary.md)
- [ADR-0004: Wayland V-Pets remains an ambient renderer](../adr/0004-wayland-vpets-is-an-ambient-renderer.md)

## Architectural invariants

Every implementation PR must preserve these invariants:

1. **Useful without AI.** Monitoring, critical alerts, state transitions and
   safe fallback messages work when every model provider is disabled.
2. **No direct side effects.** Sensors, rules, renderers and model providers
   cannot execute actions. Only the policy-controlled executor can do so.
3. **No direct rendering from integrations.** Adapters emit facts; they never
   select sprite rows, signals, notifications or voice output.
4. **Provider neutrality.** Domain and application modules import neither
   OpenAI nor a local inference implementation.
5. **Renderer neutrality.** Functional behavior survives with the avatar
   renderer stopped or replaced.
6. **Local-first privacy.** No context leaves the machine unless an explicit
   egress policy permits it. Cloud fallback is never silent.
7. **Typed, versioned contracts.** Events, capabilities, commands, plans,
   results, plugin manifests and persisted schemas are independently versioned.
8. **Deterministic safety.** Permission decisions, rate limits, deduplication,
   critical detections and execution validation do not depend on an LLM.
9. **Failure isolation.** One slow adapter, provider, renderer or output cannot
   block the reducer path or take down the daemon.
10. **Auditable assistance.** Every proposed, approved, denied, started and
    completed side effect has a correlated local audit record.

## Scope of the first functional generation

The first platform generation should make Wisp genuinely useful through:

- sustained CPU, memory, temperature and storage awareness;
- network connectivity and recovery awareness;
- Hyprland session/workspace context without screen capture;
- libvirt VM lifecycle awareness;
- MPRIS media awareness;
- deduplicated, rate-limited proactive insights;
- a local control socket and `ccctl` client;
- read-only diagnostic capabilities;
- optional local AI explanations;
- optional OpenAI explanations and planning under explicit privacy policy;
- explicit approval before any meaningful side effect.

Always-on microphone capture, screen capture, generic autonomous shell access,
privileged remediation and unrestricted remote MCP servers are explicitly out
of scope for this generation.

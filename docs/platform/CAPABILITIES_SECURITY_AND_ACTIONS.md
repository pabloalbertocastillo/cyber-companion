# Capabilities, Actions and Security

Status: **proposed security and execution contract**

## 1. Security objective

Cyber Companion should become helpful without becoming an ambient root shell.
The architecture therefore separates observation, reasoning, authorization and
execution. No adapter, detector, renderer, UI or model provider may perform a
side effect merely because it can describe one.

The trusted computing base for actions is intentionally small:

```text
validated intent / proposed plan
             -> capability registry
             -> deterministic policy
             -> exact user approval when required
             -> executor
             -> typed result + audit events
```

Everything before policy is allowed to be wrong. Policy and executor must remain
correct when a model hallucinates, a plugin is buggy or external text contains a
prompt injection.

## 2. Capability taxonomy

### Sensor

Continuously or periodically observes an external system and publishes facts.
It is read-only and does not run on demand as a tool.

Examples:

```text
system.telemetry
network.state
media.events
session.state
virtualization.events
```

### Query

Runs on demand, is bounded and has no intended external side effect. Queries can
still be sensitive or expensive and therefore carry privacy/cost metadata.

Examples:

```text
system.summary
system.processes.top_cpu
storage.filesystems.summary
network.diagnose_local
virtualization.vm.inspect
media.current_track
component.health.list
```

### Action

Changes external state, communicates externally or exercises a privilege.
Actions always pass through policy and executor.

Examples for later slices:

```text
media.pause
media.resume
virtualization.vm.start
virtualization.vm.shutdown
notification.dismiss
insight.snooze
session.lock
```

A generic `shell.execute`, `python.eval`, arbitrary DB query or unrestricted
filesystem tool is not part of the default capability set.

## 3. Capability descriptor

Discovery is metadata, not permission. Every capability publishes a versioned
descriptor:

```json
{
  "api_version": "cc.capability/v1",
  "id": "system.processes.top_cpu",
  "implementation_version": "1.0.0",
  "kind": "query",
  "description": "Return a bounded snapshot of the processes using most CPU",
  "input_schema": "cc.capability.system.top_cpu.input@1",
  "output_schema": "cc.capability.system.top_cpu.output@1",
  "risk": "read_only",
  "privacy": {
    "input": "local_private",
    "output": "sensitive"
  },
  "side_effects": [],
  "requires": ["proc.read"],
  "network": "none",
  "privilege": "user",
  "reversible": false,
  "idempotent": true,
  "default_timeout_ms": 1500,
  "max_output_bytes": 32768,
  "approval_hint": "none",
  "availability": "healthy"
}
```

Required descriptor properties:

- stable semantic ID and independent implementation version;
- strict input/output schemas;
- `sensor`, `query` or `action` kind;
- risk and expected side effects;
- input/output privacy class;
- required local permissions and network behavior;
- user/root privilege expectation;
- reversibility and idempotency;
- default and maximum timeout/output constraints;
- current health/availability;
- human-readable consequence text for approval surfaces.

Imported MCP tools receive a locally generated descriptor. Remote annotations
are hints and cannot lower local risk.

## 4. Action plans

A model, deterministic workflow or user interface may propose a plan, but the
plan contains no executable strings:

```json
{
  "api_version": "cc.action-plan/v1",
  "id": "plan_01J9ABXAMK1G87H7KW2N7T21SC",
  "intent_id": "intent_01J9ABVZP84VQ5D8CPABKMZ12D",
  "correlation_id": "corr_01J9ABVZP84VQ5D8CPABKMZ12D",
  "summary": "Pause media while the user investigates high CPU",
  "proposed_by": {
    "kind": "model_provider",
    "id": "provider.local.default"
  },
  "steps": [
    {
      "id": "step_1",
      "capability": "media.pause",
      "capability_version": "1",
      "arguments": {"player": "active"},
      "depends_on": [],
      "on_failure": "stop"
    }
  ],
  "created_at": "2026-09-04T18:22:00Z",
  "expires_at": "2026-09-04T18:24:00Z"
}
```

Before policy evaluation the planner service validates:

- plan and capability schema versions;
- capability existence and health;
- argument schemas and output bindings;
- maximum step count and dependency acyclicity;
- no undeclared interpolation or free-form command expansion;
- plan freshness;
- internally consistent risk summary.

A plan can be explained or edited without execution.

## 5. Risk model

Initial risk levels:

| Risk | Meaning | Examples |
|---|---|---|
| `read_only` | No intended state change | Inspect CPU, routes, VM state |
| `local_reversible` | User-level local change with known inverse | Pause media, snooze insight |
| `local_stateful` | Local change not automatically reversible | Stop an app, shut down a VM |
| `external` | Sends data or changes a remote service | Send message, cloud API mutation |
| `destructive` | Deletes, overwrites or can cause material loss | Remove files, force-stop VM |
| `privileged` | Requires elevated OS privilege | Package changes, service/network reconfiguration |

Risk is the maximum of descriptor risk, arguments, context and policy override.
A local plugin cannot mark deletion as `read_only` and bypass policy.

## 6. Default policy matrix

| Request | Default decision |
|---|---|
| Local read-only query with allowed privacy | Allow and audit summary |
| Sensitive read-only query requested by user | Allow locally; redact model context according to policy |
| Background read-only enrichment from an allowlisted detector | Allow with strict timeout/rate/output limits |
| Reversible user-level action explicitly requested in the current interaction | Require concise confirmation initially; policy may later remember a narrow preference |
| Stateful local action | Require exact approval |
| External communication or cloud data disclosure | Require configured egress policy and, when sensitive, exact approval |
| Destructive action | Require exact approval; no background execution |
| Privileged action | Deny in initial releases; later require isolated helper plus exact approval |
| Unknown/unhealthy capability or stale preconditions | Deny |
| Generic shell/code execution proposed by a model | Deny |

The policy language must support explicit deny rules that override allow rules.
The most restrictive applicable rule wins.

## 7. Approval contract

Approval is scoped to an immutable request digest containing:

- plan and step IDs;
- capability semantic ID and major version;
- exact normalized arguments;
- expected side effects and risk;
- data that will leave the machine and destination;
- preconditions and expiration;
- proposed provider/workflow identity.

The UI must show what will happen, not a vague “allow Wisp?” prompt. Any change
to capability, arguments, destination or expired precondition invalidates the
approval.

Approval results:

```text
approved_once | denied | cancelled | expired
```

Future policies may support narrowly scoped grants such as “allow pausing the
active media player without prompting,” but never conversationally inferred
blanket consent.

## 8. Executor state machine

```text
validated
   -> awaiting_approval
   -> authorized
   -> preconditions_checked
   -> running
   -> succeeded
      | failed
      | timed_out
      | cancelled
      | outcome_unknown
```

`outcome_unknown` is essential when the daemon or external process disappears
after dispatch but before a result. Restart logic must not blindly repeat a
non-idempotent action.

The executor:

1. verifies the signed/digested policy decision;
2. refreshes required stale preconditions;
3. acquires any capability concurrency lock;
4. writes `execution_started` durably;
5. invokes the typed capability with a deadline;
6. limits and redacts outputs;
7. writes a terminal result durably;
8. publishes the action-result fact;
9. exposes rollback only when the descriptor provides a tested inverse.

## 9. Idempotency and concurrency

Every execution receives an idempotency key derived from intent, plan, step and
normalized arguments. Capabilities declare one of:

```text
idempotent | conditionally_idempotent | non_idempotent
```

The executor prevents duplicate concurrent execution and records prior terminal
results. Non-idempotent actions are never automatically retried. Stateful
resources may define lock scopes such as `vm:win11` or `media:active`.

## 10. Privacy classes

| Class | Examples | Model/provider policy |
|---|---|---|
| `public` | Generic capability descriptions, public docs | Any enabled provider |
| `local_private` | CPU ratios, local device names, non-sensitive preferences | Local provider by default; cloud only under configured egress policy |
| `sensitive` | Process command lines, window titles, filenames, network identifiers, conversation content | Minimize/redact; local by default; cloud only with explicit task policy or approval |
| `secret` | API keys, tokens, passwords, private keys, credential material | Never logged, journaled, rendered or placed in model context |

Classification is attached at schema-field and context-item level. The context
broker computes the maximum classification of an outbound bundle.

## 11. Secrets

Secrets are referenced by opaque names, never stored in repository configuration
or SQLite event payloads:

```text
secret://openai/api-key
secret://mcp/example/token
```

A `SecretProvider` port resolves them only in the infrastructure adapter that
needs them. Initial implementations may use protected environment variables or
a desktop secret service. Diagnostic exports contain reference names and
availability only.

Plugin subprocesses receive the minimum required secrets through their
supervised environment or a one-time channel; unrelated plugins do not inherit
the daemon’s full environment.

## 12. Local API security

The default control surface is a Unix-domain socket:

- path under `$XDG_RUNTIME_DIR`;
- owner-only mode `0600`;
- local peer credential validation where supported;
- no default TCP listener;
- request size, concurrency and rate limits;
- versioned methods and schemas;
- request IDs and correlated audit;
- separate read and action methods;
- session-bound approval tokens with short expiry.

Remote access is out of scope until a separate authenticated transport and threat
model are approved.

## 13. Prompt-injection boundary

All external content is untrusted, including:

- media titles and metadata;
- filenames and process arguments;
- notifications and web content;
- MCP tool descriptions/results;
- model output from any provider;
- future email/calendar/document content.

Controls:

- data is clearly separated from system instructions in model requests;
- external text cannot register capabilities or modify policy;
- the model receives only allowlisted capability descriptors;
- tool/plan output must satisfy strict schemas;
- policy recomputes risk independently;
- exact approval is required where policy says so;
- tool results are size-limited and marked untrusted before reuse;
- secrets and hidden policy are never included in tool output;
- suspicious content can disable model planning while deterministic monitoring
  remains available.

## 14. Plugin isolation

In-process plugins are reserved for small, trusted, reviewed components. A
plugin that loads a native library, has a volatile dependency, connects to a
remote service or handles broader credentials should run as a supervised child
process behind a framed local protocol.

Isolation levels:

```text
in_process_trusted
subprocess_restricted
external_local_service
remote_service
```

The manifest states isolation, permissions, network and secret requirements.
The supervisor enforces lifecycle and output limits. Process isolation does not
replace capability policy.

## 15. Audit and diagnostics

Action and egress audit records include:

- who/what initiated the intent;
- evidence/context references, not unnecessary raw secret data;
- planner/provider identity and version;
- proposed plan and normalized arguments;
- policy rules evaluated and decision;
- approval identity/time/scope;
- execution start/end/outcome and bounded result;
- external destination and disclosed privacy classes;
- correlation and causation IDs.

Audit storage is local and queryable through `ccctl`. Export produces a redacted
diagnostic bundle by default.

## 16. Initial threat model

| Threat | Required control |
|---|---|
| Buggy adapter floods events | Bounded queues, latest-value coalescing, rate/health limits |
| Slow renderer blocks system | Independent output queue and supervisor isolation |
| Model hallucinates an action | Strict plan schema, registry lookup, policy and exact approval |
| Prompt injection requests secrets | Context isolation, secret exclusion, capability allowlist, policy |
| Malicious MCP tool description lowers risk | Local descriptor/risk override; remote metadata is untrusted |
| Cloud provider receives excessive context | Context broker minimization, classification and egress audit |
| Duplicate request repeats stateful operation | Idempotency records and resource locks |
| Crash creates unknown action outcome | Durable start record and `outcome_unknown`, no blind retry |
| Local process impersonates UI client | Owner-only socket and peer credential checks |
| Credentials leak through repo/logs | Secret references, redaction and minimal subprocess environment |
| Stale state justifies remediation | TTL/freshness validation before policy/execution |

## 17. Security acceptance gates

No action-capable release is acceptable until tests prove:

1. model output cannot call implementations directly;
2. malformed/unknown capability arguments are rejected;
3. destructive and privileged requests cannot auto-run;
4. approval is invalid after argument or precondition changes;
5. secret-class fields never enter logs, journal or model fixtures;
6. local-only mode prevents all provider/MCP network egress;
7. non-idempotent actions are not retried after ambiguous failure;
8. a killed renderer/provider does not interrupt policy or audit;
9. MCP-imported tools pass through the same registry, policy and executor;
10. every completed side effect has a terminal audit record.

# Building Enterprise Agents That Survive Production

*A practitioner's playbook for enterprise leaders and architects. November 2026.*

For the last couple of years I have built agents that run inside real enterprises. Some read production systems. Some draft decisions for a human to sign off. The same thing happens every time. Getting an agent to work in a prototype takes days. Getting one that security, audit, finance and operations will all sign off for production takes months, and most teams never get there.

This playbook is the framework I use to close that gap. It treats an agent as a small reasoning core wrapped in production controls, and it lays that out as a layered reference architecture. I have checked each part against what changed in standards, research and platforms over the past eighteen months. Throughout, I compare it with the **first-generation (2023–24) agent patterns** that many teams across the industry still run. Where one of those patterns should be retired, I say so.

**On vendors.** I don't recommend products. Where an example helps, I name two or three side by side, as illustrations only. I do name open standards and specifications (MCP, A2A, OpenTelemetry, OWASP, NIST, ISO/IEC, the EU AI Act, SLSA), because they aren't vendors. They are the shared language you should build to. A short glossary near the end explains the acronyms.

---

## 1. Why agent pilots stall before production

The 2025 data all points the same way. One analyst firm predicts that more than 40% of agentic AI projects will be cancelled by the end of 2027, because of rising costs, unclear business value or weak risk controls [1]. An MIT study reported that about 95% of enterprise generative-AI pilots showed no measurable P&L impact [2]. Its sample wasn't random, so treat the exact figure with care. Its diagnosis still rings true: the failures came from a "learning gap" and poor fit with how work actually gets done, not from model quality. A late-2025 enterprise survey found 11% of organisations using agentic AI in production, 38% piloting, and 35% with no formal strategy [3]. Another study put only 5% of companies in the group getting value at scale, while 60% reported hardly any material value [4].

Practitioners are more upbeat, but they name the same bottleneck. In a survey of 1,340 people building agents, 57.3% said they had agents in production, and quality was the top barrier (about 32%). The telling detail: 89% had observability, but only 52.4% ran offline evaluations and 37.3% ran online evaluations [5]. Teams can see what their agents do. Far fewer can prove the agents do it well.

From my own projects, pilots stall in five places:

1. **Quality can't be proven.** "It looked right in the playground" won't get past a risk committee.
2. **Controls arrive late.** Security review happens after the build, and hardening turns into a rewrite.
3. **It only works on one instance.** In-memory rate-limit counters, approval queues, circuit breakers and audit records quietly break once you run three replicas.
4. **Cost is modelled per request.** Real spend comes from tokens, reasoning, retries and agents calling other agents.
5. **Nobody owns life after launch.** There is no registry, no plan for when the model is retired, and no way to decommission the agent.

<div class="callout callout-key" role="note" markdown="1">
<p class="callout-label">Key takeaway</p>

**The core idea: a small reasoning core inside a deterministic shell.** An enterprise agent is a small, non-deterministic reasoning core inside a large, deterministic and deliberately boring shell. Most of the engineering, and nearly all of the risk reduction, lives in the shell. First-generation frameworks already put production capabilities in layers around the model, so that part holds up. What has changed is *where* those layers should sit.

</div>

---

## 2. The reference architecture: layers of an enterprise agent

<figure class="pb-fig" aria-labelledby="fig-arch-cap">
<div class="pb-fig-frame">
<svg class="pb-arch pb-arch-wide" viewBox="0 0 760 468" role="img" aria-labelledby="fig-arch-title fig-arch-desc">
<title id="fig-arch-title">Reference architecture: layers of an enterprise agent</title>
<desc id="fig-arch-desc">Six stacked layers: 1 channels and experience, 2 orchestration, 3 agent harness, 4 model access, 5 tools and interoperability, 6 knowledge and state. A cross-cutting control plane (layer 7: identity, policy-as-code, audit, telemetry, evals, agent registry, kill switch) spans all six. A delivery plane (CI/CD, supply chain, GitOps, eval gates) runs underneath.</desc>
<g class="arch-node"><rect x="16" y="16" width="540" height="50" rx="9"/><text class="arch-num" x="38" y="41" dominant-baseline="middle">1</text><text class="nlabel" x="62" y="33" dominant-baseline="middle">Channels &amp; experience</text><text class="nsub" x="62" y="52" dominant-baseline="middle">chat · embedded UI · email · tickets · event and schedule triggers · streaming</text></g>
<g class="arch-node"><rect x="16" y="76" width="540" height="50" rx="9"/><text class="arch-num" x="38" y="101" dominant-baseline="middle">2</text><text class="nlabel" x="62" y="93" dominant-baseline="middle">Orchestration</text><text class="nsub" x="62" y="112" dominant-baseline="middle">deterministic workflow · routing · durable execution · waiting for a human</text></g>
<g class="arch-node"><rect x="16" y="136" width="540" height="50" rx="9"/><text class="arch-num" x="38" y="161" dominant-baseline="middle">3</text><text class="nlabel" x="62" y="153" dominant-baseline="middle">Agent harness</text><text class="nsub" x="62" y="172" dominant-baseline="middle">reasoning loop · context assembly · memory access · budgets · structured output</text></g>
<g class="arch-node"><rect x="16" y="196" width="540" height="50" rx="9"/><text class="arch-num" x="38" y="221" dominant-baseline="middle">4</text><text class="nlabel" x="62" y="213" dominant-baseline="middle">Model access</text><text class="nsub" x="62" y="232" dominant-baseline="middle">model gateway · identity · routing · version pinning · quotas · failover · chargeback</text></g>
<g class="arch-node"><rect x="16" y="256" width="540" height="50" rx="9"/><text class="arch-num" x="38" y="281" dominant-baseline="middle">5</text><text class="nlabel" x="62" y="273" dominant-baseline="middle">Tools &amp; interoperability</text><text class="nsub" x="62" y="292" dominant-baseline="middle">tool gateway · MCP servers · A2A agents · code sandboxes · curated registry</text></g>
<g class="arch-node"><rect x="16" y="316" width="540" height="50" rx="9"/><text class="arch-num" x="38" y="341" dominant-baseline="middle">6</text><text class="nlabel" x="62" y="333" dominant-baseline="middle">Knowledge &amp; state</text><text class="nsub" x="62" y="352" dominant-baseline="middle">session event log · long-term memory · artifacts · permission-aware retrieval</text></g>
<path class="arch-edge dashed" d="M 556 41 H 584 M 556 101 H 584 M 556 161 H 584 M 556 221 H 584 M 556 281 H 584 M 556 341 H 584"/>
<g class="arch-plane"><rect x="584" y="16" width="160" height="350" rx="12"/><text class="arch-plane-label" x="664" y="40" text-anchor="middle">7 · Control plane</text><text class="arch-plane-sub" x="664" y="58" text-anchor="middle">cross-cutting</text><text class="nsub" x="664" y="100" text-anchor="middle">identity</text><text class="nsub" x="664" y="132" text-anchor="middle">policy-as-code</text><text class="nsub" x="664" y="164" text-anchor="middle">audit</text><text class="nsub" x="664" y="196" text-anchor="middle">telemetry</text><text class="nsub" x="664" y="228" text-anchor="middle">evals</text><text class="nsub" x="664" y="260" text-anchor="middle">agent registry</text><text class="nsub" x="664" y="292" text-anchor="middle">kill switch</text></g>
<path class="arch-edge dashed" d="M 120 366 V 392 M 286 366 V 392 M 452 366 V 392 M 664 366 V 392"/>
<g class="arch-plane delivery"><rect x="16" y="392" width="728" height="60" rx="12"/><text class="arch-plane-label" x="38" y="416">Delivery plane</text><text class="nsub" x="38" y="437">CI/CD · supply chain · GitOps · eval gates · AI-BOMs · signed artefacts</text></g>
</svg>
<svg class="pb-arch pb-arch-tall" viewBox="0 0 400 612" role="img" aria-labelledby="fig-arch-title-m fig-arch-desc-m">
<title id="fig-arch-title-m">Reference architecture: layers of an enterprise agent</title>
<desc id="fig-arch-desc-m">A cross-cutting control plane (layer 7: identity, policy-as-code, audit, telemetry, evals, agent registry, kill switch) encloses six stacked layers: 1 channels and experience, 2 orchestration, 3 agent harness, 4 model access, 5 tools and interoperability, 6 knowledge and state. A delivery plane (CI/CD, supply chain, GitOps, eval gates) runs underneath.</desc>
<g class="arch-plane"><rect x="6" y="6" width="388" height="508" rx="12"/><text class="arch-plane-label" x="20" y="28">7 · Control plane · cross-cutting</text><text class="nsub" x="20" y="50">identity · policy-as-code · audit · telemetry</text><text class="nsub" x="20" y="67">evals · agent registry · kill switch</text></g>
<g class="arch-node"><rect x="18" y="84" width="364" height="62" rx="9"/><text class="arch-num" x="36" y="115" dominant-baseline="middle">1</text><text class="nlabel" x="58" y="104" dominant-baseline="middle">Channels &amp; experience</text><text class="nsub" x="58" y="122" dominant-baseline="middle">chat · embedded UI · email · tickets</text><text class="nsub" x="58" y="137" dominant-baseline="middle">event and schedule triggers · streaming</text></g>
<g class="arch-node"><rect x="18" y="154" width="364" height="62" rx="9"/><text class="arch-num" x="36" y="185" dominant-baseline="middle">2</text><text class="nlabel" x="58" y="174" dominant-baseline="middle">Orchestration</text><text class="nsub" x="58" y="192" dominant-baseline="middle">deterministic workflow · routing</text><text class="nsub" x="58" y="207" dominant-baseline="middle">durable execution · waiting for a human</text></g>
<g class="arch-node"><rect x="18" y="224" width="364" height="62" rx="9"/><text class="arch-num" x="36" y="255" dominant-baseline="middle">3</text><text class="nlabel" x="58" y="244" dominant-baseline="middle">Agent harness</text><text class="nsub" x="58" y="262" dominant-baseline="middle">reasoning loop · context assembly</text><text class="nsub" x="58" y="277" dominant-baseline="middle">memory access · budgets · structured output</text></g>
<g class="arch-node"><rect x="18" y="294" width="364" height="62" rx="9"/><text class="arch-num" x="36" y="325" dominant-baseline="middle">4</text><text class="nlabel" x="58" y="314" dominant-baseline="middle">Model access</text><text class="nsub" x="58" y="332" dominant-baseline="middle">model gateway · identity · routing · quotas</text><text class="nsub" x="58" y="347" dominant-baseline="middle">version pinning · failover · chargeback</text></g>
<g class="arch-node"><rect x="18" y="364" width="364" height="62" rx="9"/><text class="arch-num" x="36" y="395" dominant-baseline="middle">5</text><text class="nlabel" x="58" y="384" dominant-baseline="middle">Tools &amp; interoperability</text><text class="nsub" x="58" y="402" dominant-baseline="middle">tool gateway · MCP servers · A2A agents</text><text class="nsub" x="58" y="417" dominant-baseline="middle">code sandboxes · curated registry</text></g>
<g class="arch-node"><rect x="18" y="434" width="364" height="62" rx="9"/><text class="arch-num" x="36" y="465" dominant-baseline="middle">6</text><text class="nlabel" x="58" y="454" dominant-baseline="middle">Knowledge &amp; state</text><text class="nsub" x="58" y="472" dominant-baseline="middle">session event log · long-term memory</text><text class="nsub" x="58" y="487" dominant-baseline="middle">artifacts · permission-aware retrieval</text></g>
<path class="arch-edge dashed" d="M 120 514 V 532 M 280 514 V 532"/>
<g class="arch-plane delivery"><rect x="6" y="532" width="388" height="74" rx="12"/><text class="arch-plane-label" x="20" y="555">Delivery plane</text><text class="nsub" x="20" y="576">CI/CD · supply chain · GitOps · eval gates</text><text class="nsub" x="20" y="593">AI-BOMs · signed artefacts</text></g>
</svg>
</div>
<figcaption id="fig-arch-cap">The layers from the table below. The control plane cuts across every layer (see <a href="#the-production-control-stack">the production control stack</a>); the delivery plane ships all of them (see <a href="#the-delivery-pipeline-commit-to-production">the delivery pipeline</a>).</figcaption>
</figure>

| Layer | Responsibility | What changed by 2026 |
|---|---|---|
| **1. Channels & experience** | Chat, embedded UI, email, tickets, event and schedule triggers; streaming; telling users they are dealing with an AI | Streaming that resumes after a disconnect; a stable event contract for clients; AI-disclosure duties now apply [63] |
| **2. Orchestration** | Deterministic workflow, routing, durable execution, waiting for a human | Durable execution (checkpoint, replay, resume) is now the baseline, not an extra [8][15] |
| **3. Agent harness** | Reasoning loop, context assembly, memory access, budgets, structured output, sub-agents | Context engineering is the main discipline; harness features are set per agent [12][16] |
| **4. Model access** | A model gateway: identity, routing, version pinning, token and cost quotas, caching, failover, chargeback (billing usage back to the team or tenant that caused it) | Token-based quotas, failover and chargeback at the gateway [76]; tracking each model's retirement date [80] |
| **5. Tools & interoperability** | Tool gateway, MCP servers, A2A agents, code sandboxes, a curated registry | Stateless MCP [24]; A2A 1.0 with signed Agent Cards [30]; tool definitions pinned and hashed by your own registry (recommended practice) |
| **6. Knowledge & state** | Session event log, long-term memory, artifacts, permission-aware retrieval | Memory split into separate layers [14], with provenance and defences against poisoning [33] |
| **7. Control plane** *(cross-cutting)* | Identity, policy-as-code, audit, telemetry, evals, the agent registry, the kill switch | Enforcement moves out of the agent process [42][44] |
| **Delivery plane** | CI/CD, supply chain, GitOps, eval gates | AI bills of materials (AI-BOMs: an inventory of the models, prompts, tools and datasets in each release), signed artefacts, promotion gated on evals [69][71] |

<div class="callout callout-key" role="note" markdown="1">
<p class="callout-label">Key takeaway</p>

**Keep deterministic work deterministic.** Triggers, scheduling, data clean-up and routing belong in an ordinary workflow layer. The agent receives a typed request and returns a typed result that downstream systems can act on without parsing prose. This is the "own your control flow" idea from the 12-factor agents work [17]. It also matches the long-standing advice to use a fixed workflow wherever the steps are known in advance [6].

</div>

Three structural moves separate a 2026 architecture from a first-generation one.

**Enforcement moves out of process.** First-generation frameworks usually put guardrails in library code inside the agent process. That is easy to teach. But anything inside the process can be misconfigured, skipped, or switched off by the very code it is meant to constrain. Keep in the process only what has to be there, such as context assembly and output validation, and use explicit middleware hooks for it. Policy, quotas, credential injection and audit belong in gateways and *policy decision points* (services that answer "is this action allowed?"), which the agent can't disable. OWASP's Agent Control Standard is an early attempt to standardise those hooks around tool calls and other agent steps [44][84]. CoSAI recommends centralising enforcement in a gateway at its higher assurance levels [42].

**State moves out of memory.** The session becomes a durable, append-only event log. Memory and large artifacts are stored separately, and the working context is rebuilt for every model call [14]. One model provider moved the session log outside both the harness and the model's context window, which turned the harness into a restartable, stateless process. It reported median (p50) time-to-first-token falling by about 60%, and 95th-percentile (p95) by more than 90% [15]. Every counter, breaker, approval and audit record belongs in a shared store.

**The harness becomes configurable.** Compaction, context resets, planning modes and evaluator passes each assume something the model can't yet do well. Those assumptions expire as models improve [16]. The length of tasks agents can complete keeps growing exponentially, and METR reports no evidence of the trend slowing [81]. Make each harness feature a per-agent setting, and re-run your evals after every model upgrade to decide which ones to keep.

---

## 3. Build principles

1. **Use the lowest complexity that reliably works.** If a function can do the job, write the function. If a fixed workflow with one LLM step can do it, build that. A single agent with tools is the usual enterprise default. Go multi-agent only for a clear reason: parallel breadth-first work, separate security boundaries, or tool overload that better tool design can't fix [6][7][8].
2. **Least agency.** OWASP now pairs least privilege with *least agency*: don't give a system autonomy it doesn't need, because extra autonomy widens the attack surface without adding value [33].
3. **Treat context as an engineered budget.** Reliability falls as input grows. A study of 18 models found that every one did better on short, focused prompts than on very long ones [13]. The goal is the smallest set of high-signal tokens that gets the outcome you want [12]. Build context assembly as a testable pipeline step, with a token budget, ordering rules and a stable prefix that can be cached.
4. **Stateless harness, durable state.** Write the agent as a stateless function over an event log [17][14].
5. **Put business rules in code, not prompts.** A system prompt is neither a secret nor a security control [34]. Authorisation must never be handed to the model [43].
6. **Typed contracts everywhere.** Major model providers now offer schema-constrained structured output (for example [20][89]). A schema-valid answer can still be wrong, so keep business validation in code, and validate each agent's output before it goes to the next step [8][89].
7. **Keep the model layer provider-neutral but reasoning-aware.** For reasoning models, write short, direct prompts with clear success criteria, drop the "think step by step" scaffolding, and pass the model's opaque reasoning state back across tool calls [19]. Where a provider offers a reasoning-effort setting, expose it as per-agent configuration [88].
8. **Own your control flow.** Use frameworks as libraries, not as black boxes that hide your prompts and loop [17][6].
9. **Deny by default and fail closed.** Convenience defaults have a way of reaching production. Make fail-closed the default for every policy check, and have CI reject any bypass or fail-open flag in a production configuration.

---

## 4. The production control stack

<figure class="pb-fig" aria-labelledby="fig-stack-cap">
<ol class="cs-grid" aria-label="The production control stack">
<li><a href="#resilience"><span class="cs-n">4.1</span><span class="cs-t">Resilience</span><span class="cs-d">Typed retries, one retry budget, idempotency keys, checkpoints</span></a></li>
<li><a href="#limits-and-budgets"><span class="cs-n">4.2</span><span class="cs-t">Limits and budgets</span><span class="cs-d">Tokens and money per run, user and tenant; an operating envelope</span></a></li>
<li><a href="#audit"><span class="cs-n">4.3</span><span class="cs-t">Audit</span><span class="cs-d">Signed, externally anchored, central, keyed to one workflow ID</span></a></li>
<li><a href="#policy"><span class="cs-n">4.4</span><span class="cs-t">Policy</span><span class="cs-d">Authorise every tool call and its arguments; graded outcomes</span></a></li>
<li><a href="#kill-switch-preflight-and-dry-run"><span class="cs-n">4.5</span><span class="cs-t">Kill switch, preflight, dry-run</span><span class="cs-d">Suspend at fleet, tenant, agent and tool level; plan → approve → apply</span></a></li>
<li><a href="#health-and-telemetry"><span class="cs-n">4.6</span><span class="cs-t">Health and telemetry</span><span class="cs-d">Local-only readiness; OpenTelemetry GenAI conventions</span></a></li>
<li><a href="#multi-tenancy"><span class="cs-n">4.7</span><span class="cs-t">Multi-tenancy</span><span class="cs-d">Tenant from authenticated context only, carried end to end</span></a></li>
<li><a href="#secrets-and-identity"><span class="cs-n">4.8</span><span class="cs-t">Secrets and identity</span><span class="cs-d">Its own non-human identity per agent; short-lived credentials</span></a></li>
<li><a href="#pii-and-dlp"><span class="cs-n">4.9</span><span class="cs-t">PII and DLP</span><span class="cs-d">Wrap every context source; egress control</span></a></li>
</ol>
<figcaption id="fig-stack-cap">The nine controls in this section, at a glance. Each tile jumps to its subsection.</figcaption>
</figure>

### 4.1 Resilience

**The established baseline** is standard distributed-systems practice. Split errors into ones worth retrying and ones that aren't. Retry with exponential backoff and jitter. Put a circuit breaker on each dependency. Degrade gracefully when a source fails. The agent-specific twist: when the agent falls back to cached or static information, it must say so. Tag every piece of data with its source and freshness, so the model can't present stale data as current and the user knows what they are looking at.

**What 2026 practice adds.** Decide what to retry from typed errors and status codes, not from exception text, and honour `Retry-After`. Set one retry budget across the SDK, the framework and the gateway. Otherwise the three layers multiply into retry storms. Put an *idempotency key* on every tool that has side effects, so a repeated call doesn't repeat the action, and never let the model choose the retry count. For long tasks, checkpoint and resume from the point of failure instead of starting over. One provider's research-agent team found that because agents carry state across many tool calls, "minor system failures can be catastrophic" [11]. Fail over between models and providers at the gateway [76].

### 4.2 Limits and budgets

First-generation agents usually limited requests per minute and capped loop iterations. Requests and steps are poor proxies for spend. Today, budgets are set in **tokens and money**, per run, per user and per tenant, and enforced at the gateway. Add wall-clock deadlines, and detect real loops, such as the same tool call repeating or a state that flips back and forth. For consequential workflows, set an *operating envelope* before the run starts. That means caps on records changed, money at stake, recipients, sub-agents, delegation depth and credential lifetime [46]. Government guidance now frames managing token consumption as an operational-resilience issue, and names *denial-of-wallet* attacks (running up your bill) [79]. OWASP lists unbounded consumption as a top-ten LLM risk [34].

### 4.3 Audit

**The established baseline:** keep two separate records. One is an operational log of what happened. The other is tamper-evident evidence that the log wasn't altered.

**What 2026 practice adds.** A hash chain with no external anchor only catches naive edits, because anyone with write access can recompute every hash. Sign entries with keys held outside the system. Periodically anchor the latest hash in a separate trust domain. Write to one central, serialised sink so replicas can't produce diverging records. Each record should capture the originating human, the agent's identity, the delegated authority, the model and prompt versions, every tool call and policy decision, and the budget consumed, all keyed to one workflow ID [46]. Redact by content before you store anything, not just by field name. For high-risk systems, the EU AI Act requires automatic logging over the system's lifetime, and deployers must keep logs for at least six months [65][66]. And don't claim a logging library "satisfies" a compliance regime. Auditors want evidence of process, not code.

### 4.4 Policy

**The established baseline:** deny by default, and decide before the model runs, so a blocked request costs nothing.

**What 2026 practice adds.** Authorise *every tool call and its arguments*, not just the incoming request. Ship policies as signed, versioned bundles with unit tests in CI. Go beyond allow and deny. OWASP's Agent Control Standard (still a v0.1 specification) defines five outcomes: allow, deny, *modify*, *ask* (send to an approver) and *defer* (decide later) [84]. Another industry body uses a different set: allow, constrain, throttle, require approval and suspend [46]. So the vocabulary isn't settled yet, but the idea of graded outcomes is. Use an LLM judge only as an optional second layer.

### 4.5 Kill switch, preflight and dry-run

- **Suspend at every level: fleet, tenant, agent and tool.** Activation must be authenticated and audited. Suspension must reject new requests, cancel queued work, block new sub-agents and refuse to renew credentials. As one guide puts it, "an alert after 10,000 calls does not stop call 10,001" [46]. Add automatic triggers on velocity, cost and anomalies. The EU AI Act asks for a "stop" procedure that brings a high-risk system to a halt in a safe state [64].
- **Preflight checks** before destructive actions should get their facts from the system of record, not from whatever the tool's caller asserts.
- **Dry-run** becomes plan → approve → apply for each request, with a diff the reviewer can read.

### 4.6 Health and telemetry

Readiness checks should test only local health. If readiness depends on a shared model gateway, one blip takes the whole fleet out of service at once. Handle dependency failures with degradation and circuit breakers instead.

For telemetry, use the **OpenTelemetry GenAI semantic conventions**. They now define `invoke_agent`, `plan` and `execute_tool` spans, MCP spans, and a `gen_ai.evaluation.result` event that attaches quality scores to the trace being scored [53]. They have moved to their own repository, with a first v0.1.0 release, and are still at *Development* stability. Pin a version and normalise attribute names in your collector. Capturing prompts and tool arguments is opt-in, and it should stay that way unless you redact. There is no standard cost metric, so compute cost centrally from token metrics. Alert when telemetry stops arriving. Losing observability silently is an incident in its own right.

### 4.7 Multi-tenancy

**The established baseline:** resolve the tenant on every request; scope thread IDs, cache keys and storage by tenant; check access at resource boundaries; audit cross-tenant attempts.

**What 2026 practice adds.** Take the tenant from authenticated server-side context *only*. Never take it from a tool argument the model fills in, or from the prompt. Carry it end to end: request, agent, tools, MCP and A2A calls, telemetry and billing. A2A 1.0 has a native tenant field [30]. Isolate prompt caches by tenant. One provider recommends separate cache keys per customer, partly to prevent cache-hit probing across users [78]. Scope memory and retrieval by tenant, and decide whether to give each tenant its own stack or share one (silo or pool) according to risk.

### 4.8 Secrets and identity

Keeping secrets in a vault behind a provider-neutral interface is still right.

<div class="callout-pair" markdown="1">

<div class="callout callout-retire" role="note" markdown="1">
<p class="callout-label">Retire</p>

What has to go is agents authenticating with a person's token or with shared static application credentials.

</div>

<div class="callout callout-instead" role="note" markdown="1">
<p class="callout-label">Do instead</p>

Each agent now needs **its own non-human identity**, with a named human sponsor, short-lived credentials, and an explicit choice between acting on its own authority and acting on behalf of a user [52][43].

</div>

</div>

The major clouds now document identity services built for agents. Microsoft Azure, Google Cloud and AWS are examples [90][91][92]. The open standards are still emerging. The IETF has an OAuth working-group draft for identity-provider-brokered "cross-app access" [49], and a Transaction Tokens draft for carrying identity through chains of calls [50]. The NIST agent standards initiative had published no final standards as of November 2026 [51]. Keep credentials out of sandboxes and out of the model's context [41], and never copy vault secrets back into environment variables to keep an SDK happy.

### 4.9 PII and DLP

Many first-generation designs redact personal data only in user input. The gap is everything else: tool results, retrieved documents and memory all flow into the context unredacted. Wrap **every** source that feeds the context. Prefer reversible pseudonymisation backed by a vault, so the model reasons over consistent placeholders and authorised outputs can be re-identified. Scan streamed output as it is produced. Route data by classification, for example sending sensitive data only to in-region endpoints. Treat egress control as a primary data-loss-prevention (DLP) measure. Private data, untrusted content and a way to send data out, all in one session, is the "lethal trifecta" [40].

---

## 5. Integration and interoperability

### 5.1 Tool design

Build a few consolidated, namespaced tools around high-impact workflows instead of wrapping every API endpoint. Have them return high-signal fields, paginate by default, and give error messages the agent can act on [21]. Return structured results with explicit error flags, not plain strings. For large tool catalogues, load tool definitions on demand through a search step. In one provider's test with more than 50 tools, this cut the tokens spent on tool definitions by about 85% [18]. Letting agents call tool APIs from code in a sandbox cut one worked example from about 150,000 tokens to about 2,000 [22]. That is a single case, not a benchmark. Package procedural knowledge as versioned skills, using the open Agent Skills format [23]. Don't split agents on tool count alone. Split them along security, ownership and permission boundaries.

### 5.2 MCP: what's current

The current MCP revision is **2026-07-28**, and it makes the protocol core stateless [24]. The initialize handshake and protocol sessions are gone. Every request carries its own version and capabilities, servers expose a `server/discover` call, and routing headers let gateways meter traffic without parsing request bodies. List results can be cached, and servers should return tools in a fixed order, which helps prompt caching. Broken streams are no longer resumed, so make tool calls idempotent and let clients re-issue them. The legacy HTTP+SSE transport is deprecated, and so are Roots, Sampling and protocol Logging. Route model calls through your own model gateway, and send tool telemetry through OpenTelemetry instead.

**Authorisation** is a hardened OAuth 2.1 profile. Use resource indicators and audience validation, and never pass tokens through to downstream services. Dynamic Client Registration is deprecated in favour of Client ID Metadata Documents, though it is still allowed for backwards compatibility. Clients must validate the `iss` parameter when the authorisation server sends it, which prevents mix-up attacks [24][25]. The **Enterprise-Managed Authorization** extension is stable. It lets the corporate identity provider grant or deny agent access to MCP servers centrally, so users don't click through a consent screen for every server [26].

**Governance:** MCP is now part of the Linux Foundation's Agentic AI Foundation [32]. It ships on a six-month cadence, with the next revision targeted for 2027-03-30 [28]. Under the new feature-lifecycle policy, deprecated features get at least 12 months before removal [24]. Plan an MCP upgrade cycle twice a year.

### 5.3 A2A for agent-to-agent delegation

A2A reached v1.0.0 on 2026-03-12, a breaking release [30]. A v1.0.1 bug-fix release followed in May 2026 [85]. Version 1.0 added Agent Cards signed with JSON Web Signatures (JWS), modern OAuth flows (PKCE and device code; the implicit and password flows are gone), mutual TLS (mTLS, where both sides present certificates), a native tenant field, and three functionally equivalent bindings [30]. A2A joined the Agentic AI Foundation in August 2026 [31]. The division of labour is now clear: **MCP connects agents to tools and context, and A2A delegates work to agents owned by someone else.** Verify card signatures. Pin the minor protocol version and take patch releases. Treat a remote agent's self-description and outputs as untrusted. Pasting a remote card's text straight into your model's tool description is a poisoning vector.

### 5.4 Gateway and registry

Send all agent traffic through a central gateway for authentication, credential injection, policy, audit and tool search [42]. Make a **private, curated registry** your only source of approved MCP servers and agents. The official MCP Registry holds public servers only, is still in preview, and leaves security scanning to others [29]. Pin and hash tool definitions, and re-approve a tool whenever its definition changes. That catches a "rug pull", where a tool approved in one form is quietly changed later. Treat annotations such as "read-only" as hints, not controls [27]. Tool misuse and the agentic supply chain both appear in OWASP's agentic top ten [33].

### 5.5 Multi-agent, used deliberately

Cloud providers' architecture guides describe overlapping patterns (for example [8][86][87]): sequential pipelines, concurrent fan-out, review-and-critique (maker-checker), handoff, and a coordinator or manager agent that routes work dynamically. One model provider's guide separates two ways to delegate: a manager agent that calls other agents as tools, and decentralised handoffs where one agent passes control to another [7]. The evidence calls for restraint. Across 260 configurations, multi-agent setups ranged from 80.8% better to 70.0% worse than a single agent, depending on how the task was structured [9]. A study of more than 1,600 traces catalogued 14 multi-agent failure modes [10]. One provider measured multi-agent systems using about 15 times the tokens of chat [11]. If you do go multi-agent, verify results centrally, use typed handoffs, carry identity, trace context and budget across every hop, and cap delegation depth.

---

## 6. Quality: evals and observability

First-generation test suites mostly checked how an agent was *assembled*: unit tests for each tool, tests that the configuration loads, and a few integration tests that needed real credentials. They said little about how the agent *behaves*. Here is what to add.

- **Start small and real.** Begin with 20–50 tasks taken from real failures. Keep a *capability* suite, which starts with a low pass rate and gives you something to climb, separate from a *regression* suite that should pass at close to 100% [54].
- **Grade the outcome.** Check the end state of the real system (does the booking exist in the database?), not what the agent says it did [54][55]. Grade what the agent produced rather than the exact path it took, because rigid step-sequence checks make tests brittle [54]. My own rule: where the path itself matters, such as a verification step that must come before a payment, add a targeted check that those steps happen in order, and leave the rest of the trajectory flexible.
- **Measure consistency.** Use pass^k (all of k trials succeed) for customer-facing agents. An agent that succeeds 75% of the time per trial succeeds on all three of three trials only about 42% of the time [54]. On one benchmark, top agents fell below 25% at pass^8 [55].
- **Separate the evaluator from the generator.** Same-model self-critique is a weak check. Self-evaluating agents "confidently praise" mediocre work, and a separate, sceptical evaluator was easier to tune [16]. LLM judges also favour their own model's outputs [60]. Use narrow pass/fail judges, one per failure mode, checked against human labels.
- **Apply statistics.** Report standard errors. Cluster them when test items are related, because clustered errors can be more than three times the naive ones. Gate releases on paired comparisons of baseline and candidate [56].
- **Read transcripts.** NIST found agents gaming graders, for example by commenting out assertions [57]. One provider stopped reporting a flagship coding benchmark after finding flawed tests and contamination [58]. Models can often tell when they are being evaluated, more so in agentic settings [62]. Build private eval sets from your own traffic.
- **Evaluate continuously.** Run CI regression gates before deploying and online evaluation of sampled production traces after. Re-run on a schedule to catch drift, and feed new production failures back into the CI dataset [54][59].

<div class="callout-pair" markdown="1">

<div class="callout callout-retire" role="note" markdown="1">
<p class="callout-label">Retire</p>

One more pattern to retire: feeding user ratings or corrections straight back into production prompts or memory. That invites memory poisoning and leaks data across tenants.

</div>

<div class="callout callout-instead" role="note" markdown="1">
<p class="callout-label">Do instead</p>

Curate feedback, scope it to a tenant, have a human review it, and add it to *eval datasets*, not production prompts.

</div>

</div>

**The dashboard I insist on:** task success and pass^k, escalation rate, tool-error rate, tokens per run, cost per successful outcome [75], time to first token, guardrail hits and cache hit rate, all broken down by agent version.

---

## 7. Security for agents

**Threat model.** Use the OWASP Top 10 for Agentic Applications (December 2025) as your agent threat checklist. It covers goal hijack, tool misuse, identity and privilege abuse, the agentic supply chain, unexpected code execution, memory and context poisoning, insecure inter-agent communication, cascading failures, exploitation of human trust in the agent, and rogue agents [33]. Use the LLM Top 10 for model-level risks [34].

**Prompt injection is a residual risk, not a bug you fix.** The UK NCSC says LLMs have no boundary between instructions and data, so injection "may never be totally mitigated" the way SQL injection can [35]. Adaptive attacks bypassed 12 published defences, with success rates above 90% against most of them [36]. A NIST-run competition with more than 250,000 attack attempts found at least one successful hijack against every one of the 13 frontier models tested [37].

<div class="callout-pair" markdown="1">

<div class="callout callout-retire" role="note" markdown="1">
<p class="callout-label">Retire</p>

Pattern-matching deny-lists on user input, the first-generation default, miss the main threat: indirect injection through tool output, documents, email and other agents. They also flag everyday words.

</div>

<div class="callout callout-instead" role="note" markdown="1">
<p class="callout-label">Do instead</p>

Keep classifiers only as one layer that makes attacks harder.

</div>

</div>

**Contain the agent by architecture.** Under the "Rule of Two", within one session an agent should have at most two of three things: untrusted input, access to sensitive data, and the ability to change state or communicate externally. If it needs all three, it needs human supervision [38]. Published design patterns such as plan-then-execute, dual-LLM, action-selector and context minimisation keep untrusted data out of the control flow [39].

**Contain first, approve second.** One provider found users approved about 93% of permission prompts. A sandbox that denies network access by default cut prompts by 84% [41]. Treat egress allowlists as capability grants: in one case, data was exfiltrated through an *approved* domain using an attacker's key. Run agent-generated code in a strongly isolated sandbox: never as root, no `eval`, isolated from the network, and with no direct path to production [33].

**Close the remaining surfaces.** Scan memory writes before committing them, and require provenance [33]. Use zero trust between agents: mutual authentication, signed messages and replay protection. Use agent-aware detection, because host-level endpoint monitoring sees nothing wrong when trusted binaries run under valid credentials [33]. Red-team continuously. In NIST tests, new attacks raised hijack success from 11% to 81%, and simply repeating attacks raised it from 57% to 80% [61].

---

## 8. Governance and the autonomy ladder

**Make autonomy an explicit design decision.** Every agent should have a recorded, approved level of autonomy that is enforced by policy, not just implied by its code. The clearest public scale I know defines five levels by the role the user plays [48]. The level names and descriptions below follow that paper. The controls column is my own mapping.

<figure class="pb-fig" aria-labelledby="fig-ladder-cap">
<div class="al-wrap">
<ol class="al" aria-label="Autonomy ladder, level 1 (operator) to level 5 (observer)">
<li style="--lvl:1"><span class="al-bar"><span class="al-n">L1</span><span class="al-t">Operator</span></span><span class="al-d">The user directs; the agent acts on request</span></li>
<li style="--lvl:2"><span class="al-bar"><span class="al-n">L2</span><span class="al-t">Collaborator</span></span><span class="al-d">User and agent plan and execute together</span></li>
<li style="--lvl:3"><span class="al-bar"><span class="al-n">L3</span><span class="al-t">Consultant</span></span><span class="al-d">The agent leads and asks the user for expertise</span></li>
<li style="--lvl:4"><span class="al-bar"><span class="al-n">L4</span><span class="al-t">Approver</span></span><span class="al-d">The agent acts; asks approval only for high-risk actions or when stuck</span></li>
<li style="--lvl:5"><span class="al-bar"><span class="al-n">L5</span><span class="al-t">Observer</span></span><span class="al-d">The agent runs autonomously; the user monitors and can stop it</span></li>
</ol>
<p class="al-axis" aria-hidden="true"><span>L1 → L5: more autonomy</span><span>more controls and evidence needed</span></p>
</div>
<figcaption id="fig-ladder-cap">The five levels, named by the role the user plays [48]. Raising an agent's level should need re-approval backed by eval evidence.</figcaption>
</figure>

| Level (user role) [48] | How work is shared | Typical controls (my mapping) |
|---|---|---|
| 1. Operator | The user directs; the agent acts on request | Narrow, mostly read-only permissions; the user confirms each action |
| 2. Collaborator | User and agent plan and execute together; either can take over | Typed output with provenance; visible plan; easy hand-back |
| 3. Consultant | The agent leads, and asks the user for expertise or preferences | Token and cost budgets; structured clarifying questions; full audit |
| 4. Approver | The agent acts on its own and asks for approval only for high-risk actions or when it is stuck | Policy that defines "high risk"; durable approval bound to exact arguments; operating envelope; rollback |
| 5. Observer | The agent runs autonomously; the user monitors and can stop it | Continuous monitoring; kill switch tested at fleet, tenant, agent and tool level; red teaming; sign-off from an accountable risk owner |

Pair the autonomy level with an impact assessment: what is the worst plausible outcome, who would be affected, and can it be reversed? Together these form an ordinary risk matrix (impact × autonomy). The higher either one goes, the more controls and evidence you need. Raising an agent's level should need re-approval backed by eval evidence.

**Governance in the loop, not a human on every step.** Requiring approval for everything leads to rubber-stamping. Current guidance makes pre-authorised policy the default. It reserves a named human approver for actions that can't be undone, disrupt production, are visible outside the organisation, or attest to something on the organisation's behalf. It also says to measure how well approvers actually perform [45]. The EU AI Act names automation bias as a risk human overseers must be made aware of [64]. An approval step that only sends a notification is not an approval. A real one pauses durably (for days if needed), binds the approval to a hash of the exact arguments, records the authenticated approver, enforces separation of duties, and has an expiry and an escalation path.

**The agent registry is the system of record.** A spreadsheet doesn't scale. For each agent, record the owner and sponsor, autonomy level, impact rating, impact assessment, allowed tools and MCP servers, the pinned model and its end-of-life date, the AI-BOM, and its signed Agent Card. Replace calendar-based recertification with continuous control monitoring that gathers evidence from CI, runtime policy decisions and evals. Detect unused agents, reduce their privileges, then decommission them, including revoking their credentials. One industry body reports, from its own survey, that 82% of enterprises found previously unknown agents in the past year, and only 21% have formal decommissioning processes [47].

**Regulation, as of November 2026 (not legal advice).** The EU AI Omnibus entered into force on 27 July 2026. It moved high-risk obligations to 2 December 2027 for use cases listed in Annex III (areas such as employment and credit) and to 2 August 2028 for AI in products covered by Annex I (existing EU product-safety law). General-purpose AI obligations have applied since August 2025, and transparency rules since August 2026 [63]. The first harmonised standard, EN 18286 for AI quality management, now gives a presumption of conformity with the Act's Article 17 quality-management-system requirements for providers of high-risk systems, and maps to ISO/IEC 42001 [67]. If you operate in Annex III areas, start building to these requirements now rather than waiting for 2027. NIST's AI RMF 1.0 is under revision [68].

---

## 9. The delivery pipeline: commit to production

Good software delivery practice still applies to agents: separation of duties, review by the code owners for the area being changed, human release approval in proportion to risk, and building an immutable artefact once and promoting that same artefact through every environment, with a GitOps controller reconciling the declared state [74][69]. What's new is evals, the agent's wider supply chain, and the non-code artefacts.

<figure class="pb-fig" aria-labelledby="fig-pipe-cap">
<ol class="pp" aria-label="Delivery pipeline stages, in order">
<li class="pp-step"><span class="pp-n">1</span><span class="pp-t">Pre-commit</span><span class="pp-g">Lint, secret scan, unit tests</span></li>
<li class="pp-step"><span class="pp-n">2</span><span class="pp-t">Pull request CI</span><span class="pp-g">Automated checks</span></li>
<li class="pp-step"><span class="pp-n">3</span><span class="pp-t">Review</span><span class="pp-g">Code-owner approval</span></li>
<li class="pp-step"><span class="pp-n">4</span><span class="pp-t">Build once</span><span class="pp-g">Signed artefact</span></li>
<li class="pp-step"><span class="pp-n">5</span><span class="pp-t">Dev</span><span class="pp-g">Automatic deploy</span></li>
<li class="pp-step is-gate"><span class="pp-n">6</span><span class="pp-t">Staging</span><span class="pp-g">Eval and security gate</span></li>
<li class="pp-step"><span class="pp-n">7</span><span class="pp-t">Production</span><span class="pp-g">Risk-proportionate release approval</span></li>
<li class="pp-step is-loop"><span class="pp-n">8</span><span class="pp-t">Operate</span><span class="pp-g">Continuous</span></li>
</ol>
<figcaption id="fig-pipe-cap">Each stage and its gate, from the table below. The artefact is built once and the same artefact is promoted through every environment.</figcaption>
</figure>

| Stage | Gate | 2026 additions |
|---|---|---|
| Pre-commit | Lint, secret scan, unit tests | A short repository file of instructions for coding agents; skills versioned in the repo |
| Pull request CI | Automated checks | Policy unit tests; offline evals with mocked tools; prompt and tool-schema checks; CI actions pinned to a commit hash; short-lived federated CI credentials |
| Review | Code-owner approval | AI reviewers get read-only access and treat pull-request text as untrusted input |
| Build once | Signed artefact | SLSA Build L3 (builds run on isolated, hardened builders); AI-BOM covering models, prompts, tools and eval set; signed models |
| Dev | Automatic deploy | Post-deploy verification with synthetic transactions and a fixed test case |
| Staging | **Eval and security gate** | Full regression suite at pass^k; red-team suite; shadow traffic sized by statistics, not a fixed number of days |
| Production | Risk-proportionate release approval | Canary (a small slice of traffic first) judged on LLM signals: eval score, tool errors, cost per outcome; old versions kept running until in-flight sessions finish |
| Operate | Continuous | Online evals, drift checks, model-retirement calendar, continuous control monitoring |

**Supply chain.** SLSA v1.2 added a Source Track [69]. In May 2026 an attack on a package registry shipped malicious packages that carried *valid* provenance from a poisoned pipeline. SLSA's own analysis concluded that Build L3 isolation would have blocked the cache-poisoning step [70]. Ship an AI-BOM with each agent version (CycloneDX ML-BOM is one format) [71], sign your models [72], and raise attestation maturity in stages [73]. NIST SP 800-218A remains the secure-development baseline for generative AI [83].

**Agent definitions as code.** The prompt, model pin, toolbox version, quotas and eval thresholds are kept in Git as declarative state that is pulled and reconciled [74]. Turn off in-place prompt edits in registry UIs, and never point production at a floating "latest" label. Model retirement is a scheduled event. One major provider keeps generally available models for at least 12 months and gives at least 45 days' notice for short-term models [80]. Treat every model swap as an eval-gated, canaried release. For long-running agents, use "rainbow" deployments, which run several versions at once and shift traffic gradually so in-flight sessions survive [11]. Rollback has to cover prompts, model pins and indexes. For side effects that can't be undone, define compensating actions.

---

## 10. Scaling and cost

**Choose the runtime deliberately.** Managed agent runtimes from the major clouds (for example Google Cloud, Microsoft Azure and AWS) now bundle sessions, memory, identity, tool gateways and evals. They are the fastest route to production but also the most opinionated. Serverless containers scale to zero but are stateless and have request timeouts. Kubernetes gives full control at a real operational cost [82]. Decide based on task duration, statefulness, isolation and residency needs, cost model, and whether you must host your own MCP servers. Wherever the agent runs, autoscale on concurrency or queue depth, not CPU. Agents spend most of their time waiting on I/O.

**Make the model gateway the control point.** It handles token-based quotas, priority queues, failover, chargeback per tenant, and centrally managed canaries. Plan for its trade-offs: added latency, a possible single point of failure, and prompts that now fall within compliance scope [76]. For self-hosted models, Kubernetes now has model-aware inference routing [77].

**Model cost per task.** One provider measured agents using about 4 times the tokens of chat, and multi-agent systems about 15 times [11]. The levers:

- **Tier your models.** Use small models for classification and extraction, and reasoning models only where they earn their cost [8].
- **Design for prompt caching.** Put stable content first, keep tool definitions in the same order, and keep per-user data out of the prefix. Cached input tokens are heavily discounted. One provider now advertises discounts of up to 95% [78], but rates vary by provider and model generation, so check current pricing. Track cache hit rate as a KPI.
- **Batch non-interactive work.** Evals and back-office runs rarely need instant answers. Two major providers price their batch APIs at 50% of standard rates [93][94].
- **Report cost per successful outcome,** not cost per call, and attribute spend by key, team and tenant [75].

**Scaling the organisation.** A platform team owns the shell: gateways, control plane, golden-path templates (pre-approved starter projects with the controls already wired in) and pipelines. Product teams own the reasoning core: context, tools and evals. That split is what lets you go from three agents to thirty without thirty separate security reviews.

---

## 11. Getting started: crawl, walk, run

<div class="callout callout-key" role="note" markdown="1">
<p class="callout-label">Key takeaway</p>

You don't need the whole architecture before your first agent ships. You need the parts that are expensive to retrofit.

</div>

<figure class="pb-fig" aria-labelledby="fig-cwr-cap">
<ol class="cwr" aria-label="Crawl, walk, run">
<li><span class="cwr-k">Crawl</span><span class="cwr-t">One agent, done properly</span><span class="cwr-lvl">Autonomy: operator or collaborator</span><ul class="cwr-d"><li>Model gateway from day one</li><li>Its own identity</li><li>Tenant from authenticated context</li><li>Token and cost budgets</li><li>OpenTelemetry GenAI traces</li><li>20–50 real eval tasks</li><li>Registered with a named owner</li></ul></li>
<li><span class="cwr-k">Walk</span><span class="cwr-t">Let agents act, safely</span><span class="cwr-lvl">Autonomy: approver, for a narrow set of actions</span><ul class="cwr-d"><li>Policy-as-code on every tool call</li><li>Durable approvals bound to arguments</li><li>Curated tool registry behind a tool gateway</li><li>Eval gates in CI</li><li>PII protection on every context source</li></ul></li>
<li><span class="cwr-k">Run</span><span class="cwr-t">Make it a platform</span><span class="cwr-lvl">Owner: a platform team, with golden paths</span><ul class="cwr-d"><li>Agent registry as the system of record</li><li>Continuous control monitoring</li><li>Online evals</li><li>Standing red team</li><li>Multi-agent and A2A only where justified</li><li>Per-tenant chargeback</li></ul></li>
</ol>
<figcaption id="fig-cwr-cap">The three stages described below, at a glance.</figcaption>
</figure>

**Crawl: one agent, done properly.** Pick one agent at the operator or collaborator level: read-only, or drafting for a human. Put it behind a model gateway from day one, with its own identity, the tenant taken from authenticated context, and token and cost budgets. Emit OpenTelemetry GenAI traces. Build an eval set of 20–50 real tasks before launch, and register the agent with a named owner, even if the registry is simple at first.

**Walk: let agents act, safely.** Add policy-as-code on every tool call, durable approvals bound to arguments, a curated tool registry behind a tool gateway, and eval gates in CI. Extend PII protection to every context source. Move your first agent to the approver level for a narrow set of actions, backed by eval evidence.

**Run: make it a platform.** Stand up a platform team, golden-path templates, an agent registry that is the system of record, continuous control monitoring, online evals and a standing red-team programme. Add multi-agent designs and A2A delegation only where the evidence justifies them. Bring in per-tenant chargeback.

**A worked example (illustrative).** Take a finance agent that handles supplier invoices that fail automatic matching against purchase orders.

- *Channel and orchestration:* the accounts-payable system emits an event. A workflow cleans up the invoice, purchase order and goods receipt into a typed request, and later waits durably for approval.
- *Harness:* context assembly pulls the mismatched lines, the supplier's recent exception history and the relevant policy extract, within a token budget. The agent returns a typed result: likely cause, proposed action, evidence, and confidence derived from checks on that evidence.
- *Model access:* a small model classifies the exception type, and a reasoning model is used only for multi-line mismatches. Budgets are set per business unit.
- *Tools:* three read-only tools (purchase orders, receipts, supplier history) and one write tool that posts an adjustment, all from the curated registry and called through the tool gateway.
- *State:* a session event log and permission-aware retrieval over finance policy. No long-term memory until there is a clear need.
- *Control plane:* the agent has its own identity, sponsored by the process owner. Policy allows the write tool only below a value threshold and only with an approval bound to the exact amounts. Every step is audited under the invoice's workflow ID.
- *Quality and delivery:* an eval set of about 40 historical exceptions with known resolutions, graded on the end state and run at pass^3, then a canary on one business unit.
- *Autonomy:* it launches at collaborator level (it proposes, a clerk decides), moves to approver level for small adjustments once eval and production evidence supports it, and never goes to observer level.

---

## 12. What's outdated, what's new

<p class="chip-legend"><span><span class="chip chip-retire">retire</span> stop doing it</span> <span><span class="chip chip-update">update</span> keep the intent, change how it is done</span> <span><span class="chip chip-new">new</span> the current approach</span></p>

| First-generation pattern (2023–24) | Current approach <span class="chip chip-new">new</span> |
|---|---|
| <span class="chip chip-update">update</span> Prompt engineering as the main quality lever | Context engineering: rebuild a minimal, budgeted context on every call from durable state [12][14] |
| <span class="chip chip-update">update</span> Guardrails as library code inside the agent process | Explicit in-process hooks, with enforcement at gateways and policy decision points [42][44] |
| <span class="chip chip-retire">retire</span> Pattern-matching deny-lists on user input as the injection defence | Architectural containment (Rule of Two, plan-then-execute); classifiers as one layer [35][38][39] |
| <span class="chip chip-retire">retire</span> Tenant or approver identity taken from tool arguments or chat text | Identity from authenticated context only, carried end to end [30][43] |
| <span class="chip chip-retire">retire</span> Agents using a person's token or shared static keys | A non-human identity per agent, with short-lived, delegated credentials [52][49] |
| <span class="chip chip-update">update</span> Request-count rate limits and loop caps | Token and cost budgets per run and tenant at the gateway, plus operating envelopes [46][79] |
| <span class="chip chip-update">update</span> Local log files, sometimes hash-chained, with no external anchor | Signed, externally anchored, central audit keyed to a workflow ID [46][65] |
| <span class="chip chip-retire">retire</span> Approval as a notification or chat confirmation | Durable, argument-bound, risk-tiered approval with an authenticated approver [45] |
| <span class="chip chip-update">update</span> A single on/off switch, not authenticated or audited | Authenticated, audited suspension at fleet, tenant, agent and tool level that halts in a safe state [46][64] |
| <span class="chip chip-update">update</span> Vendor-specific tracing SDKs | OpenTelemetry GenAI conventions with opt-in content capture [53] |
| <span class="chip chip-update">update</span> Tests of how the agent is assembled; same-model self-critique | End-state evals, pass^k, separate validated judges, transcript review [54][57] |
| <span class="chip chip-retire">retire</span> User feedback written into production prompts | Feedback curated into eval datasets, with a human gate [33][54] |
| <span class="chip chip-retire">retire</span> Early MCP over HTTP+SSE with long-lived static tokens | Stateless MCP 2026-07-28, OAuth 2.1, enterprise-managed authorisation [24][26] |
| <span class="chip chip-update">update</span> Multi-agent by default, passing plain text | Single agent by default; A2A 1.0 with signed cards for cross-team delegation [9][30] |
| <span class="chip chip-retire">retire</span> Floating "latest" labels for frameworks, models and prompts | Pinned versions, a model-retirement calendar, eval-gated promotion [80] |
| <span class="chip chip-update">update</span> SBOM plus image signing | SLSA Build L3, AI-BOM, signed models; tool definitions pinned in your registry [69][71][72] |
| <span class="chip chip-retire">retire</span> Autoscaling on CPU | Scaling on concurrency or queue depth; durable execution for long runs [8][82] |
| <span class="chip chip-retire">retire</span> Waiting for AI Act standards | Building the AI management system on ISO/IEC 42001 plus EN 18286 now [67] |
| <span class="chip chip-update">update</span> Each team building its own stack, pilot by pilot | A platform-owned shell, golden paths and a crawl-walk-run rollout |

---

## 13. Production-readiness checklist

Controls should scale with autonomy and impact. A read-only summariser doesn't need the same bar as an agent that moves money. Apply each tier on top of the ones before it.

**Baseline: every agent**
- [ ] Simplest viable pattern chosen and written down (workflow, single agent or multi-agent)
- [ ] Registry entry with owner, sponsor, autonomy level and impact rating
- [ ] Its own identity, with short-lived credentials
- [ ] Tenant and user taken from authenticated context only
- [ ] Token, cost and time budgets enforced at the gateway
- [ ] Central audit trail keyed by workflow ID, with retention set
- [ ] Prompt, model, tools and protocol versions (MCP revision, A2A minor version) pinned in Git; model end-of-life date tracked
- [ ] Regression eval suite in CI; OpenTelemetry GenAI spans emitted
- [ ] Policy checks fail closed; no bypass flags in production
- [ ] AI-disclosure and regulatory obligations reviewed for the jurisdiction

**Add for agents that take actions (approver level, or any write access)**
- [ ] Every tool call authorised by policy-as-code, including its arguments
- [ ] Durable approval bound to exact arguments, with an authenticated approver and separation of duties
- [ ] Idempotency keys on side-effecting tools; one retry budget; durable checkpoints
- [ ] PII and DLP applied to every context source and to streamed output
- [ ] Tools and MCP servers come only from the curated registry, pinned and hashed
- [ ] Rule-of-Two analysis done; code execution sandboxed with egress allowlists
- [ ] Results at the agreed pass^k, with a paired comparison against baseline; canary criteria include LLM signals
- [ ] Signed artefact; AI-BOM published

**Add for high-autonomy or high-impact agents (observer level, or wide impact)**
- [ ] Operating envelope defined and enforced (records, money, recipients, sub-agents, delegation depth)
- [ ] Kill switch drilled at fleet, tenant, agent and tool level, with automatic triggers
- [ ] Red-team suite mapped to the OWASP agentic top ten, run continuously
- [ ] Online evaluation of sampled traces and continuous control monitoring
- [ ] Build on isolated (SLSA Build L3) builders
- [ ] Rehearsed runbooks for suspending the agent, revoking its credentials, rolling back prompt, model and tool versions, switching to a manual process, and notifying affected users

---

## 14. Glossary

- **A2A (Agent2Agent):** an open protocol for one agent to delegate work to another, independently owned agent.
- **AI-BOM:** an AI bill of materials, an inventory of the models, prompts, tools and datasets in a release.
- **Annex I / Annex III (EU AI Act):** the two routes by which a system counts as high-risk. Annex I covers AI in products under existing EU product-safety law; Annex III lists use-case areas such as employment and credit.
- **Canary / rainbow deployment:** a canary sends a small slice of traffic to a new version first. A rainbow deployment runs several versions at once and shifts traffic gradually.
- **Chargeback:** billing usage back to the team or tenant that caused it.
- **Denial of wallet:** an attack, or a runaway loop, that drives up usage costs rather than taking a service down.
- **Idempotency key:** an identifier that makes a repeated request safe, so it doesn't repeat the action.
- **JWS / PKCE / mTLS:** JSON Web Signature (signing structured data); Proof Key for Code Exchange (an OAuth safeguard against intercepted codes); mutual TLS (both sides authenticate with certificates).
- **MCP (Model Context Protocol):** an open protocol for connecting agents to tools and data.
- **p50 / p95:** the median and the 95th-percentile values of a measurement such as latency.
- **pass^k:** the share of tasks an agent completes successfully on all k repeated attempts.
- **Policy decision point:** a service that answers "is this action allowed?" so the application doesn't decide for itself.
- **Rug pull:** a tool that is approved in one form and changed later without re-approval.
- **SLSA Build L3:** a supply-chain security level where builds run on isolated, hardened builders that produce verifiable provenance.

---

## 15. Sources

1. The Register, "AI agents get office tasks wrong around 70% of the time, and a lot of them aren't AI at all" (reports Gartner's 2025-06-25 prediction that over 40% of agentic AI projects will be cancelled by end of 2027), 2025-06-29. https://www.theregister.com/2025/06/29/ai_agents_fail_a_lot/
2. Fortune (reporting MIT NANDA), "MIT report: 95% of generative AI pilots at companies are failing", 2025-08-18. https://fortune.com/2025/08/18/mit-report-95-percent-generative-ai-pilots-at-companies-failing-cfo/
3. Deloitte Insights, "Agentic AI strategy (Tech Trends 2026)", 2025-12-10. https://www.deloitte.com/us/en/insights/topics/technology-management/tech-trends/2026/agentic-ai-strategy.html
4. BCG, "Are You Generating Value from AI? The Widening Gap", 2025-09-30. https://www.bcg.com/publications/2025/are-you-generating-value-from-ai-the-widening-gap
5. LangChain, "State of Agent Engineering" (survey fielded 2025-11-18 to 2025-12-02). https://www.langchain.com/state-of-agent-engineering
6. Anthropic Engineering, "Building effective agents", 2024-12-19. https://www.anthropic.com/engineering/building-effective-agents
7. OpenAI, "A practical guide to building agents" (page dated 2026-01-15). https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
8. Microsoft Azure Architecture Center, "AI agent orchestration patterns", updated 2026-09-21. https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns
9. arXiv:2512.08296, "Towards a Science of Scaling Agent Systems", 2025-12-09 (v3 2026-04-08). https://arxiv.org/abs/2512.08296
10. arXiv:2503.13657, "Why Do Multi-Agent LLM Systems Fail?", 2025-03-17. https://arxiv.org/abs/2503.13657
11. Anthropic Engineering, "How we built our multi-agent research system", 2025-06-13. https://www.anthropic.com/engineering/multi-agent-research-system
12. Anthropic Engineering, "Effective context engineering for AI agents", 2025-09-29. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
13. Chroma, "Context Rot: How Increasing Input Tokens Impacts LLM Performance", 2025-07-14. https://www.trychroma.com/research/context-rot
14. Google Developers Blog, "Architecting an efficient, context-aware multi-agent framework for production", 2025-12-04. https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/
15. Anthropic Engineering, "Scaling Managed Agents: Decoupling the brain from the hands", 2026-04-08. https://www.anthropic.com/engineering/managed-agents
16. Anthropic Engineering, "Harness design for long-running application development", 2026-03-24. https://www.anthropic.com/engineering/harness-design-long-running-apps
17. HumanLayer, "12-Factor Agents" (open source, 2025, ongoing). https://github.com/humanlayer/12-factor-agents
18. Anthropic Engineering, "Introducing advanced tool use on the Claude Developer Platform" (Tool Search Tool section), 2025-11-24. https://www.anthropic.com/engineering/advanced-tool-use
19. OpenAI, "Reasoning best practices" (accessed 2026-11-25). https://developers.openai.com/api/docs/guides/reasoning-best-practices
20. OpenAI, "Structured Outputs" (accessed 2026-11-25). https://developers.openai.com/api/docs/guides/structured-outputs
21. Anthropic Engineering, "Writing effective tools for agents — with agents", 2025-09-11. https://www.anthropic.com/engineering/writing-tools-for-agents
22. Anthropic Engineering, "Code execution with MCP", 2025-11-04. https://www.anthropic.com/engineering/code-execution-with-mcp
23. Agent Skills open format (accessed 2026-11-25). https://agentskills.io/
24. Model Context Protocol, "Specification 2026-07-28 – Key Changes" (includes the feature-lifecycle policy), 2026-07-28. https://modelcontextprotocol.io/specification/2026-07-28/changelog
25. Model Context Protocol, "Authorization (2026-07-28)", 2026-07-28. https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
26. MCP Blog, "Enterprise-Managed Authorization: Zero-touch OAuth for MCP", 2026-06-18. https://blog.modelcontextprotocol.io/posts/enterprise-managed-auth/
27. MCP Blog, "Tool Annotations as Risk Vocabulary", 2026-03-16. https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/
28. MCP Blog, "A More Predictable Release Cycle for MCP", 2026-11-11. https://blog.modelcontextprotocol.io/posts/mcp-release-cycle/
29. Model Context Protocol, "The MCP Registry (About)" (accessed 2026-11-25). https://modelcontextprotocol.io/registry/about
30. A2A Project, "What's New in A2A v1.0" (v1.0.0 released 2026-03-12). https://a2a-protocol.org/latest/whats-new-v1/
31. A2A Project, "A new chapter for A2A: joining the Agentic AI Foundation", 2026-08-27. https://a2a-protocol.org/latest/blog/2026/08/27/a-new-chapter-for-a2a-joining-the-agentic-ai-foundation/
32. Linux Foundation, "Linux Foundation Announces the Formation of the Agentic AI Foundation", 2025-12-09. https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation
33. OWASP GenAI Security Project, "OWASP Top 10 for Agentic Applications for 2026", 2025-12-09. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
34. OWASP GenAI Security Project, "OWASP Top 10 for LLM Applications 2025" (LLM06, LLM07, LLM10). https://genai.owasp.org/llm-top-10/
35. UK NCSC, "Prompt injection is not SQL injection (it may be worse)", 2025-12-08. https://www.ncsc.gov.uk/blog-post/prompt-injection-is-not-sql-injection
36. arXiv:2510.09023, "The Attacker Moves Second", 2025-10-10. https://arxiv.org/abs/2510.09023
37. NIST CAISI, "Insights into AI Agent Security from a Large-Scale Red-Teaming Competition", 2026-03-23. https://www.nist.gov/blogs/caissi-research-blog/insights-ai-agent-security-large-scale-red-teaming-competition
38. Meta AI, "Agents Rule of Two: A Practical Approach to AI Agent Security", 2025-10-31. https://ai.meta.com/blog/practical-ai-agent-security/
39. arXiv:2506.08837, "Design Patterns for Securing LLM Agents against Prompt Injections", 2025-06-10. https://arxiv.org/abs/2506.08837
40. Simon Willison, "The lethal trifecta for AI agents", 2025-06-16. https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
41. Anthropic, "How we contain Claude across products", 2026-05-25. https://www.anthropic.com/research/how-we-contain-claude
42. Coalition for Secure AI, "MCP Security, Version 2.0", 2026-09-25. https://www.coalitionforsecureai.org/mcp-security-version-2-0-from-threat-taxonomy-to-a-model-you-can-actually-audit-against/
43. Coalition for Secure AI, "Zero Trust for AI Systems: Why Authorization Can't Live Inside the Model", 2026-09-16. https://www.coalitionforsecureai.org/zero-trust-for-ai-systems-why-authorization-cant-live-inside-the-model/
44. OWASP GenAI Security Project, "Agent Control Standard (ACS)", 2026-09-01. https://genai.owasp.org/resource/agent-control-standard-acs/
45. Cloud Security Alliance, "Human-in-the-Loop: When Should a Human Approve an AI Action?", 2026-11-19. https://cloudsecurityalliance.org/articles/human-in-the-loop-when-should-a-human-approve-an-ai-action
46. Cloud Security Alliance, "When Valid Agent Actions Become a Security Incident", 2026-11-25. https://cloudsecurityalliance.org/articles/when-valid-agent-actions-become-a-security-incident-governing-ai-agents-at-machine-speed
47. Cloud Security Alliance, "Lost in Delegation", 2026-11-23. https://cloudsecurityalliance.org/articles/lost-in-delegation
48. arXiv:2506.12469, "Levels of Autonomy for AI Agents", 2025-06-14 (v2 2025-07-28). https://arxiv.org/abs/2506.12469
49. IETF OAuth WG, draft-ietf-oauth-identity-assertion-authz-grant-06, October 2026. https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/
50. IETF OAuth WG, draft-ietf-oauth-transaction-tokens-11, 2026-07-30. https://datatracker.ietf.org/doc/draft-ietf-oauth-transaction-tokens/
51. NIST CAISI, "AI Agent Standards Initiative", created 2026-02-17, updated 2026-11-09. https://www.nist.gov/caisi/ai-agent-standards-initiative
52. OWASP, "Non-Human Identities Top 10 – 2025". https://owasp.github.io/www-project-non-human-identities-top-10/2025
53. OpenTelemetry, "semantic-conventions-genai" repository (v0.1.0, Development stability; accessed 2026-11-25). https://github.com/open-telemetry/semantic-conventions-genai
54. Anthropic Engineering, "Demystifying evals for AI agents", 2026-01-09. https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
55. arXiv:2406.12045, "τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains", 2024-06-17. https://arxiv.org/abs/2406.12045
56. Anthropic, "A statistical approach to model evaluations", 2024-11-19. https://www.anthropic.com/research/statistical-approach-to-model-evals
57. NIST CAISI, "Cheating On AI Agent Evaluations", 2025-12-02. https://www.nist.gov/blogs/caissi-research-blog/cheating-ai-agent-evaluations
58. OpenAI, "Why we no longer evaluate SWE-bench Verified", 2026-02-23. https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
59. Hamel Husain & Shreya Shankar, "LLM Evals: Everything You Need to Know (Evals FAQ)", 2026-09-18. https://hamel.dev/blog/posts/evals-faq/
60. arXiv:2404.13076, "LLM Evaluators Recognize and Favor Their Own Generations", 2024-04-15. https://arxiv.org/abs/2404.13076
61. NIST CAISI, "Technical Blog: Strengthening AI Agent Hijacking Evaluations", 2025-01-17 (updated 2025-12-19). https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations
62. arXiv:2505.23836, "Large Language Models Often Know When They Are Being Evaluated", 2025-05-28 (v3 2025-07-16). https://arxiv.org/abs/2505.23836
63. European Commission, "AI Act – Regulatory framework for AI", last updated 2026-11-25. https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
64. AI Act Explorer, "Article 14: Human oversight" (accessed 2026-11-25). https://artificialintelligenceact.eu/article/14/
65. AI Act Explorer, "Article 12: Record-keeping" (accessed 2026-11-25). https://artificialintelligenceact.eu/article/12/
66. AI Act Explorer, "Article 26: Obligations of deployers" (accessed 2026-11-25). https://artificialintelligenceact.eu/article/26/
67. CEN-CENELEC JTC 21, "EN 18286 becomes the first harmonised standard under the EU AI Act", 2026-10-14. https://jtc21.eu/en-18286-becomes-the-first-harmonised-standard-under-the-eu-ai-act/
68. NIST, "AI Risk Management Framework" (accessed 2026-11-25). https://www.nist.gov/itl/ai-risk-management-framework
69. SLSA / OpenSSF, "Announcing SLSA v1.2", 2025-11-24. https://slsa.dev/blog/2025/11/announce-slsa-v1.2
70. SLSA / OpenSSF, "Mini Shai-Hulud: Where SLSA's Boundaries Fall", 2026-05-15. https://slsa.dev/blog/2026/05/mini-shai-hulud-what-slsa-can-and-cannot-do
71. OWASP CycloneDX, "Machine Learning Bill of Materials (ML-BOM)" (accessed 2026-11-25). https://cyclonedx.org/capabilities/mlbom/
72. OpenSSF, "Launch of Model Signing v1.0", 2025-04-04. https://openssf.org/blog/2025/04/04/launch-of-model-signing-v1-0-openssf-ai-ml-working-group-secures-the-machine-learning-supply-chain/
73. Coalition for Secure AI, "How Much Assurance Does Your AI Supply Chain Need?", 2026-10-05. https://www.coalitionforsecureai.org/how-much-assurance-does-your-ai-supply-chain-need/
74. OpenGitOps (CNCF), "OpenGitOps Principles v1.0.0". https://opengitops.dev/
75. FinOps Foundation, "FinOps for AI Overview", updated 2026-10-28. https://www.finops.org/wg/finops-for-ai-overview/
76. Microsoft Azure Architecture Center, "Access Foundry Models and Other Language Models Through a Gateway", 2026-04-30 (updated 2026-11-23). https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/generative-ai-gateway
77. Kubernetes SIGs, "Gateway API Inference Extension" (accessed 2026-11-25). https://gateway-api-inference-extension.sigs.k8s.io/
78. OpenAI, "Prompt caching" (accessed 2026-11-25). https://developers.openai.com/api/docs/guides/prompt-caching
79. CISA / Canadian Centre for Cyber Security, "Managing AI Token Consumption for Operational Resilience", 2026-10-22. https://www.cisa.gov/resources-tools/resources/managing-ai-token-consumption-operational-resilience
80. Google Cloud, "Model versions and lifecycle" (accessed 2026-11-25). https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
81. METR, "Time horizons", updated 2026-09-08. https://metr.org/time-horizons/
82. Google Cloud Architecture Center, "Choose your agentic AI architecture components" (accessed 2026-11-25). https://docs.cloud.google.com/architecture/choose-agentic-ai-architecture-components
83. NIST, "SP 800-218A: Secure Software Development Practices for Generative AI and Dual-Use Foundation Models", 2024-07-26. https://csrc.nist.gov/pubs/sp/800/218/a/final
84. OWASP GenAI Security Project, "agent-control-standard" GitHub repository (release 0.1.5 implementing specification v0.1.0; five dispositions, nineteen lifecycle hooks; accessed 2026-11-25). https://github.com/GenAI-Security-Project/agent-control-standard
85. A2A Project, GitHub releases (v1.0.1, 2026-05-28; v1.0.0, 2026-03-12; accessed 2026-11-25). https://github.com/a2aproject/A2A/releases
86. Google Cloud Architecture Center, "Choose a design pattern for your agentic AI system" (accessed 2026-11-25). https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system
87. AWS Prescriptive Guidance, "Agentic AI patterns and workflows on AWS" (accessed 2026-11-25). https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/introduction.html
88. OpenAI, "Reasoning models" (reasoning.effort parameter; accessed 2026-11-25). https://developers.openai.com/api/docs/guides/reasoning
89. Google AI for Developers, "Structured outputs" (accessed 2026-11-25). https://aistudio.google.com/docs/structured-output
90. Microsoft Learn, "Microsoft Entra Agent ID documentation", updated 2026-11-17. https://learn.microsoft.com/en-us/entra/agent-id/
91. Google Cloud, "Agent Identity overview" (accessed 2026-11-25). https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview
92. AWS, "Provide identity and credential management for agent applications with Amazon Bedrock AgentCore Identity" (accessed 2026-11-25). https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html
93. OpenAI, "Batch API" ("50% cost discount compared to synchronous APIs"; accessed 2026-11-25). https://developers.openai.com/api/docs/guides/batch
94. Google AI for Developers, "Batch API" ("50% of the standard cost"; accessed 2026-11-25). https://aistudio.google.com/docs/batch-api

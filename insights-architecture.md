# Insights / DORA — Architecture

How the pieces fit together: from the control-plane CRDs that emit delivery
signals, through a normalize-and-store module in the observability plane, to the
Backstage Insights UI and external analytics backends. Grounded in the real
components — `Workload` / `ComponentRelease` / `ReleaseBinding` CRDs, the observer
SQL store (`postgresql` / `sqlite`), and the `openchoreo-observability` portal
plugin.

> **The shape in one line:** producers (control plane) **push** normalized
> delivery events across the plane boundary into the observer store; the observer
> **computes** DORA on read by joining those events with the incidents it already
> holds; Backstage **reads** the metrics with the end-user's JWT. Write path and
> read path are fully decoupled.

---

## 1. High-level (three zones)

```
 ┌──────────────────────────── CONTROL PLANE ─────────────────────────────┐
 │                                                                         │
 │   Workload ──frozen copy──▶ ComponentRelease ◀──binds── ReleaseBinding  │
 │   .spec.source              .spec.workload.source         status.Ready  │
 │   {commit,branch,            (immutable snapshot)        False ─▶ True   │
 │    repo,authoredAt}                                      = DEPLOY moment │
 │        ▲                                                      │          │
 │        │ set by producer                                     │ watches   │
 │        │ (build OR external CI)                              ▼          │
 │   ┌────┴─────────┐                              ┌───────────────────────┐│
 │   │ OpenChoreo   │   git provider lookup        │  Delivery Emitter      ││
 │   │ build  /  CI │   (authoredAt, best-effort)  │  (controller)          ││
 │   └──────────────┘                              │  builds 1 normalized   ││
 │                                                 │  DeploymentEvent       ││
 │                                                 └───────────┬───────────┘│
 └─────────────────────────────────────────────────────────────│───────────┘
                                                                │
                          HMAC-signed, idempotent, async        │  POST /insights/events
                          (off deployment critical path)        ▼
 ┌─────────────────────── OBSERVABILITY PLANE (observer service) ───────────────────────┐
 │                                                                                       │
 │   ┌─ Ingestion API ─┐      ┌──────────── SQL store (postgres / sqlite) ────────────┐  │
 │   │ /insights/events │────▶│  deployment_events        incident_entries (existing) │  │
 │   │  (HMAC auth)     │     │  {scope, result,          {scope, triggered_at,       │  │
 │   └──────────────────┘     │   deploy_finished_at,      resolved_at, status}        │  │
 │                            │   authored_at, lead_time,            ▲                 │  │
 │                            │   commit, …}                         │ local join      │  │
 │                            └──────────────┬───────────────────────┘ (CFR / MTTR)    │  │
 │                                           │                                          │  │
 │   ┌─ DORA Query API ─────────────┐        │ compute on read                          │  │
 │   │ /insights/dora/query         │◀───────┘ DF · LT(median) · CFR(join) · MTTR       │  │
 │   │ /insights/dora/trends/query  │   scope = {namespace[,project[,component]][,env]} │  │
 │   │ /insights/deployments/query  │   (JWT + scope authz)                             │  │
 │   └───────────────┬──────────────┘                                                   │  │
 └───────────────────│──────────────────────────────────────────────────────────────────┘
                     │  user JWT (forwarded from Backstage) + scope authz
                     ▼
 ┌──────────────────────────────── CONSUMERS ──────────────────────────────────────────┐
 │                                                                                       │
 │   Backstage portal  (openchoreo-observability plugin)                                 │
 │     • Insights tab ▸ DORA sub-tab   — org / project / component scorecards + history  │
 │     • Portal Assistant  — read-only `insights` MCP tool wrapping dora/query           │
 │                                                                                       │
 │   External analytics backends (optional fan-out, same normalized events):             │
 │     DevLake · DX · Datadog · …   (keep their own long-term stores)                    │
 └───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Write path (ingestion) — how a deploy becomes a row

```
 ReleaseBinding.status.Ready: False ─▶ True
        │
        │ 1. controller observes the transition (the deploy moment)
        ▼
 Delivery Emitter
        │ 2. resolve linked ComponentRelease (spec.releaseName)
        │    read owner.{project,component} + workload.source.{commit,…,authoredAt}
        │ 3. build normalized DeploymentEvent
        │    idempotencyKey = deploy:<component>:<env>:gen-<n>
        ▼
 POST /api/v1alpha1/insights/events   (HMAC-signed, service-to-service)
        │ 4. upsert by idempotencyKey  → safe on retry / re-observe
        ▼
 deployment_events row  (lead_time_ns precomputed = deploy_finished − authored)
```

Properties that matter:
- **Off the critical path** — the deploy completes regardless; the emitter buffers
  and retries if the observer is briefly unavailable.
- **Idempotent** — the `Ready` condition can be re-observed; `idempotencyKey`
  dedupes.
- **Cross-plane push** — producers are control-plane CRDs, the store is in the obs
  plane, so the control plane *pushes* (same pattern as the existing alerts
  webhook). Captures the fact durably **before the CRD is pruned**.

---

## 3. Read path (query) — how the UI gets metrics

```
 Backstage Insights ▸ DORA sub-tab
        │ 1. user opens org / project / component view
        ▼
 openchoreo-observability plugin  (generated client)
        │ 2. POST /insights/dora/query  { searchScope, window }
        │    forwards the end-user JWT
        ▼
 DORA Query API  (observer)
        │ 3. scope authz on {namespace[,project[,component]][,env]}
        │ 4. compute over the store for that scope + window:
        │      DF   = count(success) / window_days
        │      LT   = median(lead_time_ns)
        │      CFR  = (failed ∪ incident-linked) / total      ← join incident_entries
        │      MTTR = avg(resolved − triggered)               ← over incident_entries
        ▼
 { metrics + classification + delta }  → scorecards / leaderboard / history
```

The **level is just the scope breadth** — same endpoint, same compute, wider or
narrower `searchScope`. No per-level pipeline.

---

## 4. Component responsibilities

| Component | Plane | Responsibility |
| --- | --- | --- |
| `Workload.spec.source` | control | carries commit/branch/repo/authoredAt from the producer (build or CI) |
| `ComponentRelease.spec.workload.source` | control | immutable frozen snapshot of the above (source of truth for LT) |
| `ReleaseBinding.status.Ready` | control | the deployment moment (False→True) + success/failure |
| **Delivery Emitter** | control | watches Ready, normalizes, HMAC-POSTs the event (off critical path) |
| **Ingestion API** `/insights/events` | obs | validates HMAC, idempotent upsert into `deployment_events` |
| **SQL store** (`deployment_events` + `incident_entries`) | obs | durable, scope-indexed event history (postgres prod / sqlite dev) |
| **DORA Query API** `/insights/dora/*` | obs | compute DF/LT/CFR/MTTR on read; JWT + scope authz |
| **observability plugin** | portal | renders scorecards / leaderboard / history; forwards user JWT |
| **Portal Assistant + MCP tool** | portal | "Investigate with AI" — read-only wrapper over dora/query |
| **External backends** (fan-out) | external | DevLake/DX/Datadog consume the same normalized events |

---

## 5. Why this topology

1. **Decoupled write/read** — ingestion (HMAC, service-to-service, async) and query
   (user JWT, scope authz) share only the store. Either can evolve independently.
2. **DORA lives in the obs plane** because **CFR/MTTR are a local join** on the
   incidents the observer already holds — co-locating the data makes the join a
   same-database query instead of a cross-service call.
3. **Source-of-truth on the Workload** covers both internal builds and external CI
   (no `WorkflowRun` required) and freezes into the immutable release copy.
4. **One store, three altitudes** — org/project/component are scope filters, so
   there is a single ingestion path and a single query shape.
5. **Backend-agnostic** — the in-product view reads OpenChoreo's own metrics, so it
   works with no external tool configured; DevLake/DX/Datadog get the same events
   via fan-out, not via these APIs.

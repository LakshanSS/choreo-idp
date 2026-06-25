# DORA Metrics — Data Sources, Storage & Calculation

How the four DORA metrics are computed in OpenChoreo: **which control-plane CRD
fields feed them, what we persist in the Insights store, and how the same query
rolls up at organization, project, and component level.**

> **High-level definitions**
>
> | Metric | Definition |
> | --- | --- |
> | **Deployment Frequency (DF)** | count of successful deployments over a time window |
> | **Lead Time for Changes (LT)** | `deploy_finished_at − source_commit_authored_at` |
> | **Change Failure Rate (CFR)** | (failed ∪ incident-linked deployments) ÷ total deployments |
> | **Mean Time to Recovery (MTTR)** | `incident_resolved_at − incident_triggered_at` |
>
> The rest of this doc is *where each of those fields comes from* and *how the
> aggregation works per scope level*.

---

## 1. Where the data comes from (control-plane CRDs)

Every DORA input is already produced by an existing CRD or the observer incident
store. Only one additive field (`workload.source`) is new.

| Signal needed | Source object | Exact field | Notes |
| --- | --- | --- | --- |
| **A deployment happened** | `ReleaseBinding` | `status.conditions[type=Ready]` transitions to `True` | This transition **is** the deployment event. |
| **When it finished** | `ReleaseBinding` | `status.conditions[Ready].lastTransitionTime` | → `deploy_finished_at` |
| **Which env** | `ReleaseBinding` | `spec.environment` | → `environment_name` |
| **Which release** | `ReleaseBinding` | `spec.releaseName` | links the binding to its `ComponentRelease` |
| **Which project / component** | `ComponentRelease` | `spec.owner.projectName`, `spec.owner.componentName` | → `project_name`, `component_name` |
| **Commit / branch / repo** | `ComponentRelease` | `spec.workload.source.{commit,branch,repository}` | **new** field on `WorkloadTemplateSpec`, frozen immutably into the release copy (see `insights-source-on-workload.md`) |
| **Commit author time** | `ComponentRelease` | `spec.workload.source.authoredAt` | → basis for Lead Time |
| **Success / failure** | `ReleaseBinding` | terminal `Ready` condition `status` / `reason` | `True` → success, terminal `False` → failed |
| **Incidents (for CFR/MTTR)** | observer **`incident_entries`** store | `triggered_at_ns`, `resolved_at_ns`, `project_id`, `environment_id`, `component_id` | already persisted; powers the Incidents tab today |

**Why `workload.source` and not `WorkflowRun`:** a `WorkflowRun` only exists when
OpenChoreo ran the build. External-CI users register an image directly, so they
have no `WorkflowRun`. Both flows converge on the `Workload`, and
`ComponentRelease.spec.workload` is a frozen immutable copy of it — so putting
`source` on the workload makes it work for *both* paths and freezes it for free.

### From CRD → deployment fact

```
 ReleaseBinding (status.Ready: False → True)        ← the deploy moment
    │  spec.environment            → environment_name
    │  spec.releaseName ───────────┐
    │  status…Ready.lastTransition  │ → deploy_finished_at
    ▼                               ▼
 ComponentRelease (spec.releaseName match)
       spec.owner.projectName       → project_name
       spec.owner.componentName     → component_name
       spec.workload.source.commit  → commit
       spec.workload.source.authoredAt → source_commit_authored_at
                                     │
                                     ▼
                       one normalized DeploymentEvent row
```

A control-plane **delivery emitter** watches that `Ready` transition, resolves the
linked `ComponentRelease`, builds one normalized event, and HMAC-POSTs it to the
Insights ingestion endpoint (`POST /api/v1alpha1/insights/events`). This is
off the deployment critical path and idempotent on a deterministic key.

---

## 2. What we store (the Insights store)

DORA is a **time series over past events**; CRDs are live and prunable, so we
persist each deployment fact durably the moment it happens. The table mirrors the
existing `incident_entries` conventions (same scope columns, same `*_ns` BIGINT
timestamps, same `(project_id, environment_id, timestamp_ns)` index) so it lives
natively next to incidents in the observer SQL store and the CFR/MTTR join is
trivial.

### `deployment_events`

```sql
CREATE TABLE IF NOT EXISTS deployment_events (
    id                  TEXT PRIMARY KEY,     -- de_...
    idempotency_key     TEXT NOT NULL UNIQUE, -- deploy:<component>:<env>:gen-<n>

    -- scope (same columns/semantics as incident_entries)
    namespace_name      TEXT NOT NULL,        -- = organization
    project_name        TEXT NOT NULL,
    component_name      TEXT NOT NULL,
    environment_name    TEXT NOT NULL,
    project_id          TEXT,
    component_id        TEXT,
    environment_id      TEXT,

    -- delivery facts
    result              TEXT NOT NULL,        -- 'success' | 'failed'
    deploy_finished_at_ns BIGINT NOT NULL,    -- from Ready.lastTransitionTime
    authored_at_ns      BIGINT,               -- from workload.source.authoredAt (nullable)
    lead_time_ns        BIGINT,               -- deploy_finished_at_ns - authored_at_ns (nullable)

    -- linkage / drill-down
    commit              TEXT,
    branch              TEXT,
    repository          TEXT,
    release_name        TEXT,
    generation          BIGINT,

    timestamp_ns        BIGINT NOT NULL       -- ingest time
);

CREATE INDEX IF NOT EXISTS idx_deployment_events_scope_ts
ON deployment_events(project_id, environment_id, deploy_finished_at_ns);
```

Notes:

- **`lead_time_ns` is precomputed at write time** (`deploy_finished − authored`)
  so the read path never has to do per-row arithmetic; it's `NULL` when
  `authoredAt` was unavailable (e.g. external CI didn't pass it), and such rows
  are simply excluded from LT but still count for DF/CFR.
- **Incidents are not copied here.** CFR/MTTR join live against `incident_entries`
  on the shared scope columns — that local join is the concrete reason Insights
  belongs in the observability plane.
- `idempotency_key` makes re-emits safe (the `Ready` condition can be re-observed).

---

## 3. The scope hierarchy (org / project / component)

The three "levels" are just **which scope columns the WHERE clause fixes**. The
metric formulas are identical at every level — only the filter changes.

| Level | Fixed columns | Aggregates across |
| --- | --- | --- |
| **Organization** | `namespace_name = :org` | all projects, all components |
| **Project** | `namespace_name`, `project_name` | all components in the project |
| **Component** | `namespace_name`, `project_name`, `component_name` | one component |

`environment_name` is an **orthogonal optional filter** at every level (e.g.
"prod only"). This is exactly the `ComponentSearchScope { namespace, project,
component, environment }` already used by Incidents/Traces — reused verbatim, so
authz and scoping come for free.

```
 org (namespace)                 WHERE namespace_name = :org
   └─ project                    AND project_name   = :project
        └─ component             AND component_name = :component
   (any level) AND environment_name = :env   -- optional
```

---

## 4. How each metric is calculated

All four are computed server-side over a `[startTime, endTime]` window. Let
`Δdays = (endTime − startTime) / 1 day`. Below, the **scope predicate** is
whichever WHERE clause from §3 applies — that's the *only* thing that differs
between org/project/component.

### 4.1 Deployment Frequency (DF)

> successful deployments ÷ window length

```sql
SELECT COUNT(*) * 1.0 / :window_days AS deployment_frequency
FROM deployment_events
WHERE <scope predicate>
  AND result = 'success'
  AND deploy_finished_at_ns BETWEEN :start_ns AND :end_ns;
```

- **Org level** → counts every successful deploy in the namespace.
- **Project level** → counts successful deploys across the project's components.
- **Component level** → one component's successful deploys.
- Unit `per_day`; classified into Elite/High/Medium/Low by the 2024 DORA bands.

### 4.2 Lead Time for Changes (LT)

> median of `deploy_finished_at − commit_authored_at` across deploys in window

Because `lead_time_ns` is precomputed per row, this is a median over a column:

```sql
SELECT median(lead_time_ns) AS lead_time_ns      -- PERCENTILE_CONT(0.5) on Postgres
FROM deployment_events
WHERE <scope predicate>
  AND result = 'success'
  AND lead_time_ns IS NOT NULL
  AND deploy_finished_at_ns BETWEEN :start_ns AND :end_ns;
```

- Rows where `authoredAt` is unknown (`lead_time_ns IS NULL`) are excluded — they
  don't distort the median.
- **Median, not mean**, so a single long-lived feature branch doesn't skew it.
- Roll-up at project/org is a median over the larger row set — naturally weighted
  by deploy volume, which is the desired behaviour.

### 4.3 Change Failure Rate (CFR)

> (failed deploys ∪ deploys later linked to an incident) ÷ total deploys

This is the one metric that **joins the deployment store to the incident store**.
A deploy is a "failure" if it either failed outright (`result='failed'`) **or** a
prod incident was triggered in its blast window. Conceptually:

```sql
WITH deploys AS (
  SELECT * FROM deployment_events
  WHERE <scope predicate>
    AND deploy_finished_at_ns BETWEEN :start_ns AND :end_ns
),
linked AS (                                  -- deploys correlated to an incident
  SELECT DISTINCT d.id
  FROM deploys d
  JOIN incident_entries i
    ON  i.project_id     = d.project_id
    AND i.environment_id = d.environment_id
    AND (i.component_id  = d.component_id OR i.component_id IS NULL)
    AND i.triggered_at_ns >= d.deploy_finished_at_ns          -- incident after deploy
    AND i.triggered_at_ns <  d.deploy_finished_at_ns + :attribution_window_ns
)
SELECT
  (SELECT COUNT(*) FROM deploys
     WHERE result='failed'
        OR id IN (SELECT id FROM linked)) * 1.0
  / NULLIF((SELECT COUNT(*) FROM deploys), 0) AS change_failure_rate;
```

- The incident join uses the **same scope columns** at every level, so CFR rolls
  up org/project/component with no special casing.
- `:attribution_window` (e.g. the proposal's "incident triggered shortly after a
  deploy") is how an incident is attributed to the deploy that likely caused it.
- Unit `ratio`; bands Elite ≤5% … Low >15%.

### 4.4 Mean Time to Recovery (MTTR)

> mean of `incident_resolved_at − incident_triggered_at` for incidents in scope

MTTR is computed **purely over the incident store** (it's a property of incidents,
not deploys), filtered to the same scope:

```sql
SELECT AVG(resolved_at_ns - triggered_at_ns) AS mttr_ns
FROM incident_entries
WHERE <scope predicate>                      -- same namespace/project/component/env cols
  AND status = 'resolved'
  AND resolved_at_ns IS NOT NULL
  AND triggered_at_ns BETWEEN :start_ns AND :end_ns;
```

- Only **resolved** incidents contribute (open ones have no recovery time yet).
- Org level = mean recovery time across every project's incidents; component level
  = that one component's incidents. Same predicate switch as everything else.

---

## 5. Putting it together — one query shape, three levels

The DORA query endpoint (`POST /api/v1alpha1/insights/dora/query`) takes a
`searchScope` and a window and runs the four computations above. The scope is
what selects the level:

| Request `searchScope` | Resulting level |
| --- | --- |
| `{ namespace }` | **Organization** — all projects |
| `{ namespace, project }` | **Project** — all components |
| `{ namespace, project, component }` | **Component** |
| `… + environment` | any of the above, narrowed to one environment |

Response is the four metrics, each with value, unit, DORA classification, and a
delta vs. the previous equal-length window:

```json
{
  "scope": { "namespace": "default", "project": "patient-management-project" },
  "window": { "startTime": "2026-05-18T00:00:00Z", "endTime": "2026-06-17T00:00:00Z" },
  "metrics": {
    "deploymentFrequency": { "value": 4.2,   "unit": "per_day", "classification": "Elite" },
    "leadTimeForChanges":  { "value": 11520, "unit": "seconds", "classification": "High"  },
    "changeFailureRate":   { "value": 0.065, "unit": "ratio",   "classification": "Elite" },
    "meanTimeToRecovery":  { "value": 1680,  "unit": "seconds", "classification": "Elite" }
  },
  "totals": { "deployments": 126, "failedDeployments": 8, "incidents": 5 }
}
```

---

## 6. Summary

| Metric | Stored from | Computed by | Scope roll-up |
| --- | --- | --- | --- |
| **DF** | `ReleaseBinding` Ready→True (`result=success`) | `COUNT ÷ window_days` | filter columns only |
| **LT** | `deploy_finished_at_ns − workload.source.authoredAt` (precomputed `lead_time_ns`) | `median(lead_time_ns)` | filter columns only |
| **CFR** | `deployment_events` + `incident_entries` | `(failed ∪ incident-linked) ÷ total` | filter columns only |
| **MTTR** | `incident_entries` (existing) | `avg(resolved − triggered)` | filter columns only |

The key design property: **the level (org / project / component) is purely a
WHERE-clause decision over a shared, scope-indexed event store.** One ingestion
path, one query shape, three altitudes — no per-level pipelines.
</content>

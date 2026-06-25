# Delivery Insights / DORA — REST API Design

The API lives in the **Observability Plane** (observer service) and deliberately
mirrors the observer's existing HTTP conventions, so DORA reads like a native
obs-plane capability alongside logs / metrics / traces / incidents:

| Convention | Existing observer | DORA follows |
| --- | --- | --- |
| Path prefix | `/api/v1alpha1/...` (traces, alerts, incidents) | `/api/v1alpha1/...` |
| Query style | `POST /{resource}/query` with JSON body + `searchScope` | same |
| Scope object | `ComponentSearchScope { namespace, project, component, environment }` (req: `namespace`) | reused verbatim |
| Read auth | user JWT forwarded from Backstage → scope authz | same (project/component/env authz) |
| Ingestion | `POST /api/v1alpha1/alerts/webhook` (HMAC, service-to-service) | `POST /api/v1alpha1/delivery/events` (HMAC) |
| Errors | `ErrorResponse { error, code, message }` | same |
| Pagination | `limit` + `sortOrder` (+ cursor for history) | same |

Two surfaces:
- **Write (ingestion)** — the control-plane *delivery emitter* POSTs normalized
  events; HMAC-signed, idempotent, off the user-auth path.
- **Read (query + DORA)** — Backstage's generated client calls these with the
  end-user JWT; scope-authz enforces project/component/environment access.

---

## Endpoint catalog (overview slide)

| # | Method & path | Auth | Purpose | Powers (UI) |
| --- | --- | --- | --- | --- |
| 1 | `POST /api/v1alpha1/delivery/events` | HMAC (service) | Ingest a normalized DeliveryEvent (idempotent upsert) | — (write path) |
| 2 | `POST /api/v1alpha1/dora/metrics/query` | user JWT + scope | The 4 DORA metrics + classification + deltas for a scope/window | 4 scorecards |
| 3 | `POST /api/v1alpha1/dora/trends/query` | user JWT + scope | Time-bucketed series for one metric | trend chart + sparklines |
| 4 | `POST /api/v1alpha1/delivery/deployments/query` | user JWT + scope | Paginated deployment history (with linked incident) | history table |

> Incidents are **not** a new endpoint — they already arrive via
> `POST /api/v1alpha1/alerts/webhook` and live in the observer incident store.
> CFR / MTTR are computed by **joining locally** against that store, which is the
> core reason DORA belongs in the obs plane.

---

## 1 — Ingest delivery events (write path)

`POST /api/v1alpha1/delivery/events` · **HMAC-signed**, no user JWT.

The control-plane emitter watches `WorkflowRun` / `ComponentRelease` /
`ReleaseBinding`; when a `ReleaseBinding` first reaches `Ready=True` for a
generation, it builds and posts this event. Idempotent on `idempotencyKey`, so
retries are safe and deployments are never on the critical path.

**Request**
```json
{
  "idempotencyKey": "deploy:patient-management-service:prod:gen-7",
  "eventType": "deployment",
  "scope": {
    "namespace": "default",
    "project": "patient-management-project",
    "component": "patient-management-service",
    "environment": "prod"
  },
  "source": {
    "commit": "a1b2c3d4",
    "branch": "main",
    "repository": "https://github.com/acme/patient-mgmt",
    "authoredAt": "2026-06-16T07:10:00Z"
  },
  "deployStartedAt": "2026-06-16T09:48:00Z",
  "deployFinishedAt": "2026-06-16T09:50:40Z",
  "result": "success",
  "releaseName": "patient-management-service-7",
  "workflowRunName": "build-patient-mgmt-1421",
  "generation": 7
}
```

**Response `202 Accepted`**
```json
{ "id": "de_01J8...", "accepted": true, "deduplicated": false }
```

- `result`: `success | failed`.
- `source.authoredAt` is the commit author timestamp (fetched via the git
  provider at release time — the basis for Lead Time).
- `deduplicated: true` when the `idempotencyKey` was already stored.

---

## 2 — DORA metrics (scorecards)

`POST /api/v1alpha1/dora/metrics/query` · user JWT + scope authz.

Project-level rollup → omit `component`. Component drill-down → include it.
`environment` is an optional filter.

**Request**
```json
{
  "searchScope": {
    "namespace": "default",
    "project": "patient-management-project",
    "environment": "prod"
  },
  "startTime": "2026-05-18T00:00:00Z",
  "endTime": "2026-06-17T00:00:00Z",
  "compareToPrevious": true
}
```

**Response `200 OK`**
```json
{
  "window": { "startTime": "2026-05-18T00:00:00Z", "endTime": "2026-06-17T00:00:00Z" },
  "scope": { "namespace": "default", "project": "patient-management-project", "environment": "prod" },
  "metrics": {
    "deploymentFrequency": { "value": 4.2,    "unit": "per_day", "classification": "Elite", "deltaPct": 12,  "trend": "up" },
    "leadTimeForChanges":  { "value": 11520,  "unit": "seconds", "classification": "High",  "deltaPct": -18, "trend": "down" },
    "changeFailureRate":   { "value": 0.065,  "unit": "ratio",   "classification": "Elite", "deltaPct": 0,   "trend": "flat" },
    "meanTimeToRecovery":  { "value": 1680,   "unit": "seconds", "classification": "Elite", "deltaPct": -22, "trend": "down" }
  },
  "totals": { "deployments": 126, "failedDeployments": 8, "incidents": 5 }
}
```

- `classification`: `Elite | High | Medium | Low` (2024 DORA bands).
- `trend` + `deltaPct` are metric-aware (lower lead time / MTTR is "better"),
  driving the ▲/▼ colouring on the scorecards.
- `compareToPrevious` computes deltas against the immediately preceding window of
  equal length.

**Computation (native, over the delivery + incident stores):**
- **DF** = count(`result=success`) ÷ window-days.
- **LT** = median(`deployFinishedAt − source.authoredAt`) across deploys in window.
- **CFR** = (failed ∪ incident-linked deploys) ÷ total deploys.
- **MTTR** = mean(`incident.resolvedAt − incident.triggeredAt`) for incidents
  attributed to deploys in window (local join on the observer incident store).

---

## 3 — Metric trends (chart + sparklines)

`POST /api/v1alpha1/dora/trends/query` · user JWT + scope authz.

**Request**
```json
{
  "searchScope": { "namespace": "default", "project": "patient-management-project", "environment": "prod" },
  "startTime": "2026-04-20T00:00:00Z",
  "endTime": "2026-06-17T00:00:00Z",
  "metric": "deploymentFrequency",
  "interval": "week"
}
```

**Response `200 OK`**
```json
{
  "metric": "deploymentFrequency",
  "interval": "week",
  "unit": "per_day",
  "points": [
    { "bucketStart": "2026-04-20T00:00:00Z", "value": 2.1 },
    { "bucketStart": "2026-04-27T00:00:00Z", "value": 3.0 },
    { "bucketStart": "2026-05-04T00:00:00Z", "value": 3.8 },
    { "bucketStart": "2026-05-11T00:00:00Z", "value": 4.2 }
  ]
}
```

- `metric`: `deploymentFrequency | leadTimeForChanges | changeFailureRate | meanTimeToRecovery`.
- `interval`: `day | week | month`. The same endpoint feeds the big trend chart
  and the small scorecard sparklines (just a shorter window).

---

## 4 — Deployment history (table)

`POST /api/v1alpha1/delivery/deployments/query` · user JWT + scope authz.

**Request**
```json
{
  "searchScope": { "namespace": "default", "project": "patient-management-project" },
  "startTime": "2026-05-18T00:00:00Z",
  "endTime": "2026-06-17T00:00:00Z",
  "result": "all",
  "limit": 25,
  "cursor": null,
  "sortOrder": "desc"
}
```

**Response `200 OK`**
```json
{
  "items": [
    {
      "id": "de_01J8...",
      "deployedAt": "2026-06-16T09:50:40Z",
      "component": "patient-management-service",
      "environment": "prod",
      "commit": "a1b2c3d4",
      "author": "p.fernando",
      "result": "success",
      "buildDurationSeconds": 252,
      "leadTimeSeconds": 9600,
      "releaseName": "patient-management-service-7",
      "workflowRunName": "build-patient-mgmt-1421",
      "incident": null
    },
    {
      "id": "de_01J7...",
      "deployedAt": "2026-06-16T05:30:00Z",
      "component": "billing-service",
      "environment": "prod",
      "commit": "f4e5d6a7",
      "author": "a.perera",
      "result": "failed",
      "buildDurationSeconds": 390,
      "leadTimeSeconds": null,
      "releaseName": "billing-service-12",
      "workflowRunName": "build-billing-1402",
      "incident": { "id": "INC-204", "mttrSeconds": 1680, "status": "resolved" }
    }
  ],
  "nextCursor": "eyJvZmZzZXQiOjI1fQ==",
  "totalCount": 126
}
```

- `result` filter: `all | success | failed`.
- `incident` is the locally-joined incident (drives the table's Incident column +
  the ⤷ link into the existing Project Incidents tab).
- `commit` → links to the Build-tab `WorkflowRun`; `workflowRunName` makes that
  deterministic.

---

## UI ↔ endpoint mapping (ties to the wireframes)

| Wireframe element | Endpoint |
| --- | --- |
| 4 DORA scorecards (value + band + ▲/▼) | `POST /dora/metrics/query` |
| scorecard sparklines | `POST /dora/trends/query` (short window) |
| "over time" trend chart | `POST /dora/trends/query` |
| deployment-history table | `POST /delivery/deployments/query` |
| Incident column / ⤷ link | joined from observer incident store (existing) |
| "Investigate with AI" | portal-assistant `/chat` → new read-only `dora_insights` MCP tool wrapping #2 & #4 |

---

## Auth & safety model

| Endpoint | Caller | Auth | Notes |
| --- | --- | --- | --- |
| `/delivery/events` | control-plane emitter | HMAC signature | service-to-service; off user-auth path; idempotent |
| `/dora/metrics/query` | Backstage (user) | user JWT + scope authz | same authz as incidents/alerts |
| `/dora/trends/query` | Backstage (user) | user JWT + scope authz | |
| `/delivery/deployments/query` | Backstage (user) | user JWT + scope authz | |

- Reads enforce the same project/component/environment scope resolution the
  observer already applies to incidents/alerts (`ErrAuthzForbidden`,
  `ErrAuthzUnauthorized`, scope-not-found → 400).
- The write path is **off the critical path of a deployment**: if the observer is
  unavailable the emitter buffers and retries; idempotency keys make retries safe.

**Error envelope** (unchanged from observer):
```json
{ "error": "BAD_REQUEST", "code": "VALIDATION_ERROR", "message": "searchScope.namespace is required" }
```

---

## OpenAPI delta (paste targets for `openapi/observer-api.yaml`)

Add 4 paths + these schemas, then `make openapi-codegen` regenerates the
server/client/models (same flow used for every other observer endpoint).

```yaml
components:
  schemas:
    DeliveryEvent:
      type: object
      required: [idempotencyKey, eventType, scope, result]
      properties:
        idempotencyKey: { type: string }
        eventType: { type: string, enum: [deployment] }
        scope: { $ref: "#/components/schemas/ComponentSearchScope" }
        source:
          type: object
          properties:
            commit: { type: string }
            branch: { type: string }
            repository: { type: string }
            authoredAt: { type: string, format: date-time }
        deployStartedAt: { type: string, format: date-time }
        deployFinishedAt: { type: string, format: date-time }
        result: { type: string, enum: [success, failed] }
        releaseName: { type: string }
        workflowRunName: { type: string }
        generation: { type: integer }

    DoraMetricsQueryRequest:
      type: object
      required: [searchScope, startTime, endTime]
      properties:
        searchScope: { $ref: "#/components/schemas/ComponentSearchScope" }
        startTime: { type: string, format: date-time }
        endTime: { type: string, format: date-time }
        compareToPrevious: { type: boolean, default: true }

    DoraMetric:
      type: object
      properties:
        value: { type: number }
        unit: { type: string }                # per_day | seconds | ratio
        classification: { type: string, enum: [Elite, High, Medium, Low] }
        deltaPct: { type: number }
        trend: { type: string, enum: [up, down, flat] }

    DoraMetricsQueryResponse:
      type: object
      properties:
        window:
          type: object
          properties:
            startTime: { type: string, format: date-time }
            endTime: { type: string, format: date-time }
        scope: { $ref: "#/components/schemas/ComponentSearchScope" }
        metrics:
          type: object
          properties:
            deploymentFrequency: { $ref: "#/components/schemas/DoraMetric" }
            leadTimeForChanges:  { $ref: "#/components/schemas/DoraMetric" }
            changeFailureRate:   { $ref: "#/components/schemas/DoraMetric" }
            meanTimeToRecovery:  { $ref: "#/components/schemas/DoraMetric" }
        totals:
          type: object
          properties:
            deployments: { type: integer }
            failedDeployments: { type: integer }
            incidents: { type: integer }

    DoraTrendsQueryRequest:
      type: object
      required: [searchScope, startTime, endTime, metric, interval]
      properties:
        searchScope: { $ref: "#/components/schemas/ComponentSearchScope" }
        startTime: { type: string, format: date-time }
        endTime: { type: string, format: date-time }
        metric:
          type: string
          enum: [deploymentFrequency, leadTimeForChanges, changeFailureRate, meanTimeToRecovery]
        interval: { type: string, enum: [day, week, month] }

    DoraTrendsQueryResponse:
      type: object
      properties:
        metric: { type: string }
        interval: { type: string }
        unit: { type: string }
        points:
          type: array
          items:
            type: object
            properties:
              bucketStart: { type: string, format: date-time }
              value: { type: number }

    DeploymentsQueryRequest:
      type: object
      required: [searchScope, startTime, endTime]
      properties:
        searchScope: { $ref: "#/components/schemas/ComponentSearchScope" }
        startTime: { type: string, format: date-time }
        endTime: { type: string, format: date-time }
        result: { type: string, enum: [all, success, failed], default: all }
        limit: { type: integer, default: 25, minimum: 1, maximum: 200 }
        cursor: { type: string, nullable: true }
        sortOrder: { type: string, enum: [asc, desc], default: desc }

    DeploymentRecord:
      type: object
      properties:
        id: { type: string }
        deployedAt: { type: string, format: date-time }
        component: { type: string }
        environment: { type: string }
        commit: { type: string }
        author: { type: string }
        result: { type: string, enum: [success, failed] }
        buildDurationSeconds: { type: integer, nullable: true }
        leadTimeSeconds: { type: integer, nullable: true }
        releaseName: { type: string }
        workflowRunName: { type: string }
        incident:
          type: object
          nullable: true
          properties:
            id: { type: string }
            mttrSeconds: { type: integer }
            status: { type: string }

    DeploymentsQueryResponse:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/DeploymentRecord" }
        nextCursor: { type: string, nullable: true }
        totalCount: { type: integer }
```

---

## What to present (talking points)

1. **It's native, not bolted-on** — same `/api/v1alpha1/.../query` + `searchScope`
   + scope-authz shape as logs/metrics/traces/incidents.
2. **One write endpoint, three read endpoints** — minimal surface; each read maps
   1:1 to a piece of the Insights UI.
3. **CFR/MTTR are a local join** on the existing incident store — the concrete
   payoff of putting DORA in the obs plane.
4. **Backend-agnostic** — Backstage reads endpoints #2–#4 directly, so the
   in-product view works with no external tool; DX/Datadog/DevLake get the same
   normalized events via the fan-out, not via these APIs.
5. **Off the deployment critical path** — HMAC ingestion, idempotent, buffered +
   retried.
6. **Assistant-ready** — endpoints #2 and #4 are wrapped by a read-only
   `dora_insights` MCP tool, so "Investigate with AI" works with zero assistant
   core changes.
```
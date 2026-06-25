## REST API — Delivery Insights

The Insights API lives in the **Observability Plane** (observer service) and
mirrors the observer's existing HTTP conventions, so it reads as a native
obs-plane capability alongside logs / metrics / traces / incidents:

| Convention | Existing observer | Insights API follows |
| --- | --- | --- |
| Path prefix | `/api/v1alpha1/…` (traces, alerts, incidents) | `/api/v1alpha1/insights/…` |
| Query style | `POST /{resource}/query` with JSON body + `searchScope` | same |
| Scope object | `ComponentSearchScope { namespace, project, component, environment }` (req: `namespace`) | reused verbatim |
| Read auth | end-user JWT forwarded from Backstage → scope authz | same |
| Ingestion | `POST /api/v1alpha1/alerts/webhook` (HMAC, service-to-service) | `POST /api/v1alpha1/insights/events` (HMAC) |
| Errors | `ErrorResponse { error, code, message }` | same |

`insights/` is the namespace (matches the "Insights" portal tab and the
Delivery Insights module, and stays open to non-DORA signals later). The word
**DORA** is kept only where the resource is literally the canonical four metrics
(`insights/dora/…`), leaving room for future families (`insights/<family>/…`).

For the first iteration the surface is intentionally **two endpoints** — one
write, one read:

- **Write (ingestion)** — the control-plane *delivery emitter* POSTs normalized
  events; HMAC-signed, idempotent, off the user-auth path and off the deployment
  critical path.
- **Read (DORA metrics)** — Backstage's generated client calls this with the
  end-user JWT; scope-authz enforces project/component/environment access.

### Endpoint catalog

| # | Method & path | Auth | Purpose | Powers (UI) |
| --- | --- | --- | --- | --- |
| 1 | `POST /api/v1alpha1/insights/events` | HMAC (service) | Ingest a normalized delivery event (idempotent upsert) | — (write path) |
| 2 | `POST /api/v1alpha1/insights/dora/query` | user JWT + scope | The four DORA metrics + classification + deltas for a scope/window | 4 scorecards |

> Incidents are **not** a new endpoint — they already arrive via
> `POST /api/v1alpha1/alerts/webhook` and live in the observer incident store.
> Change Failure Rate and MTTR are computed by **joining locally** against that
> store — the concrete reason Insights belongs in the observability plane.

> **Future iterations** (same `insights/` namespace, same patterns): a trends
> endpoint (`insights/dora/trends/query`) for the time-series chart + sparklines,
> and a deployment-history endpoint (`insights/deployments/query`) for the
> drill-down table. Scoped out of the first cut to keep the surface minimal.

---

### 1 · Ingest delivery events (write path)

`POST /api/v1alpha1/insights/events` · **HMAC-signed**, no user JWT.

The control-plane emitter watches `WorkflowRun` / `ComponentRelease` /
`ReleaseBinding`; when a `ReleaseBinding` first reaches `Ready=True` for a
generation, it posts this event. Idempotent on `idempotencyKey`, so retries are
safe and deployments never wait on the obs plane.

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

**Why it exists:** the producers are control-plane CRDs while the store lives in
the obs plane, so the control plane must *push* normalized events across the
plane boundary (same pattern as the alerts webhook). It also captures each
deployment fact durably **before the CRD is pruned** (CRDs are live/prunable;
DORA is a time-series over past events), and normalizes three CRD shapes into one
event that both the read API and external backends consume.

---

### 2 · DORA metrics (scorecards)

`POST /api/v1alpha1/insights/dora/query` · end-user JWT + scope authz.

Project-level rollup → omit `component`; component drill-down → include it;
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
    "deploymentFrequency": { "value": 4.2,   "unit": "per_day", "classification": "Elite", "deltaPct": 12,  "trend": "up" },
    "leadTimeForChanges":  { "value": 11520, "unit": "seconds", "classification": "High",  "deltaPct": -18, "trend": "down" },
    "changeFailureRate":   { "value": 0.065, "unit": "ratio",   "classification": "Elite", "deltaPct": 0,   "trend": "flat" },
    "meanTimeToRecovery":  { "value": 1680,  "unit": "seconds", "classification": "Elite", "deltaPct": -22, "trend": "down" }
  },
  "totals": { "deployments": 126, "failedDeployments": 8, "incidents": 5 }
}
```

- `classification`: `Elite | High | Medium | Low` (2024 DORA bands).
- `trend` + `deltaPct` are metric-aware (lower lead time / MTTR is "better"),
  driving the ▲/▼ colouring on the scorecards.
- `compareToPrevious` computes deltas against the immediately preceding window of
  equal length.

**Computation (native, over the delivery + incident stores)**
- **Deployment Frequency** = count(`result=success`) ÷ window-days.
- **Lead Time** = median(`deployFinishedAt − source.authoredAt`) across deploys.
- **Change Failure Rate** = (failed ∪ incident-linked deploys) ÷ total deploys.
- **MTTR** = mean(`incident.resolvedAt − incident.triggeredAt`) for incidents
  attributed to deploys in the window (local join on the observer incident store).

**Why it exists:** it computes OpenChoreo's *own* DORA metrics server-side —
running the medians/ratios and the incident join the browser can't do — and
returns a tiny, fixed-shape payload that maps 1:1 to the scorecards. Because the
portal reads OpenChoreo's own metrics, the in-product view works regardless of
which external backend is configured, or none at all.

---

### Auth & safety model

| Endpoint | Caller | Auth | Notes |
| --- | --- | --- | --- |
| `insights/events` | control-plane emitter | HMAC signature | service-to-service; off user-auth + deployment critical path; idempotent |
| `insights/dora/query` | Backstage (user) | user JWT + scope authz | same scope resolution as incidents/alerts |

Reads enforce the same project/component/environment scope authz the observer
already applies to incidents/alerts (`403` forbidden, `401` unauthorized,
scope-not-found → `400`). Error envelope is unchanged:

```json
{ "error": "BAD_REQUEST", "code": "VALIDATION_ERROR", "message": "searchScope.namespace is required" }
```

---

### UI ↔ endpoint mapping

| Insights UI element | Endpoint |
| --- | --- |
| 4 DORA scorecards (value + band + ▲/▼) | `POST /insights/dora/query` |
| trend chart + sparklines | *future* — `insights/dora/trends/query` |
| deployment-history table | *future* — `insights/deployments/query` |
| Incident column / link | joined from observer incident store (existing) |
| "Investigate with AI" | portal-assistant `/chat` → read-only `insights` MCP tool wrapping `dora/query` |

---

### OpenAPI delta (paste targets for `openapi/observer-api.yaml`)

Add the two paths (`operationId`s `ingestDeliveryEvent`, `queryInsightsDora`)
plus these schemas, then `make openapi-codegen` regenerates the
server/client/models — same flow as every other observer endpoint.

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

    DeliveryEventAck:
      type: object
      properties:
        id: { type: string }
        accepted: { type: boolean }
        deduplicated: { type: boolean }

    InsightsDoraQueryRequest:
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

    InsightsDoraQueryResponse:
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
```

---

### Why this shape (talking points)

1. **Native, not bolted-on** — same `/api/v1alpha1/…/query` + `searchScope` +
   scope-authz shape as logs / metrics / traces / incidents.
2. **Minimal first surface** — one write endpoint to capture delivery facts, one
   read endpoint to serve the four metrics; trends + history follow later behind
   the same namespace.
3. **CFR / MTTR are a local join** on the existing incident store — the concrete
   payoff of putting Insights in the obs plane.
4. **`insights/` namespace, `dora` only where it's the literal four** — extensible
   to SPACE / DevEx / AI-assist signals without renaming.
5. **Backend-agnostic** — Backstage reads `dora/query` directly, so the in-product
   view works with no external tool; DX / Datadog / DevLake get the same
   normalized events via fan-out, not via these APIs.
6. **Off the deployment critical path** — HMAC ingestion, idempotent, buffered +
   retried.

# Insights — Storage: do we need Postgres, and what are the alternatives?

**Short answer:** reuse the observer's existing SQL store. It already supports
**PostgreSQL** (production) and **SQLite** (local/dev) behind one backend
abstraction, and already persists the `incident_entries` and `alert_entries`
tables we join against. DORA delivery events are **low-volume event records**, not
high-cardinality telemetry — so a relational DB is the right tool, and Postgres
comfortably holds years of this data. No new database technology is needed.

---

## 1. The key realization: this is *event* data, not *telemetry*

The instinct to reach for a time-series database comes from confusing DORA data
with metrics/logs/traces. They're very different:

| | Logs / Metrics / Traces | DORA delivery events |
| --- | --- | --- |
| Volume | millions–billions of rows/day | **one row per deployment** |
| Cardinality | very high | low (scoped by namespace/project/component/env) |
| Shape | fire-and-forget samples | correlatable facts (commit ↔ deploy ↔ incident) |
| Query | aggregate/scan huge ranges | filter a small, indexed set + a join |

A DORA event is written **once per deployment** and once per incident. That is
orders of magnitude less data than observability telemetry — which is exactly why
it can live in a normal relational table and doesn't need a specialized store.

### Volume math (why Postgres is more than enough)

Each `deployment_events` row is a few hundred bytes.

| Scenario | Deploys/day | Rows/year | 3-year size (incl. indexes) |
| --- | --- | --- | --- |
| Small org | 50 | ~18 K | a few MB |
| Active org | 500 | ~180 K | tens of MB |
| Very busy org | 5,000 | ~1.8 M | ~1–2 GB |

Even the "very busy" case is **single-digit millions of rows over years** — a
workload Postgres handles trivially with the scope index. Incidents are an order
of magnitude fewer still. There is no scale pressure here.

---

## 2. The recommendation: reuse the observer SQL store

The observer already has the abstraction we want
(`internal/observer/store/...`):

- `New(backend, dsn, logger)` with `backend ∈ { "sqlite", "postgresql" }`
- pure-Go drivers already vendored: `modernc.org/sqlite`, `jackc/pgx/v5`
- per-dialect SQL branching already in place for `incident_entries` /
  `alert_entries`

We add **one table, `deployment_events`**, next to those (schema in
`dora-metrics-calculation.md`) using the same conventions: `*_ns` BIGINT
timestamps, the same scope columns, and a `(project_id, environment_id,
deploy_finished_at_ns)` index. Then:

- **Production → PostgreSQL.** Durable, concurrent writers (the observer can run
  multiple replicas), proper indexes, easy backup/PITR, and the CFR join to
  `incident_entries` is a same-database join (no cross-store calls).
- **Local / dev / single-node → SQLite.** Zero-ops, file-backed, already the
  default. Fine for demos and CI; not for multi-replica production.

This is also the decision already recorded in the discussion ("reuse existing SQL
store, observability plane"). Choosing Postgres-or-SQLite is a *config* decision
(`backend` + DSN), not a new dependency.

---

## 3. Alternatives considered (and why not, for the in-product store)

| Option | Verdict | Why |
| --- | --- | --- |
| **Time-series DB** (Prometheus/Thanos/Mimir) | ✗ | Stores *pre-aggregated samples*, not raw correlatable events. Can't model commit↔deploy↔incident linkage and can't do the CFR incident join. Cardinality/retention model fights us. |
| **ClickHouse / columnar OLAP** | ✗ (overkill now) | Built for billions of rows; our volume is millions over *years*. Adds an operational dependency for no benefit. Reconsider only if we later host org-wide analytics over huge fleets. |
| **Object storage as primary** (Parquet/JSON on S3) | ✗ as primary | Cheap and durable, but no interactive scope-filtered queries or joins. Good as a *tier-2 archive*, not the serving store. |
| **A brand-new dedicated database service** | ✗ | New ops surface, new backup story, new failure mode — for data that fits in the store we already run. |
| **PostgreSQL (existing observer backend)** | ✓ **production** | Right volume fit, durable, joins live with incidents, already supported. |
| **SQLite (existing observer backend)** | ✓ **local/dev** | Zero-ops default; already wired. |

The external **fan-out backends** (DevLake, DX, Datadog, …) are a separate axis:
they keep their *own* long-term stores and get the same normalized events via the
emitter. So OpenChoreo's own store is the in-product serving layer — it does not
have to be the only long-term home of the data.

---

## 4. Months-and-years retention — handled inside Postgres

Long retention is a non-issue at this volume, but if/when we want to be explicit:

- **Native partitioning** — range-partition `deployment_events` (and incidents) by
  month on `deploy_finished_at_ns`. Old partitions stay queryable; dropping a
  retention boundary is an instant `DETACH`/`DROP PARTITION`, not a slow `DELETE`.
- **BRIN index on the timestamp** — tiny, ideal for append-only time-ordered data;
  keeps year-spanning range scans cheap.
- **Pre-aggregated rollups (optional, later)** — if org-level dashboards over many
  years ever feel slow, add a daily summary table (deploys/failures/lead-time per
  scope per day) and serve long windows from it while keeping raw events for
  drill-down. Not needed at launch.
- **Tiered archive (optional)** — export partitions older than N months to
  Parquet/object storage for compliance, keep the hot window in Postgres.

None of this is required for v1 — a single Postgres table with the scope index
serves years of data. Partitioning is the first lever we'd pull, and only if
volume ever warrants it.

---

## 5. Summary

1. **DORA data is low-volume event data**, not telemetry — millions of rows over
   *years*, not per day.
2. **Reuse the observer SQL store**: Postgres in production, SQLite locally — both
   already supported, no new dependency.
3. **CFR/MTTR join lives in the same database** as `incident_entries` — a core
   reason to keep it in the observer store rather than a separate system.
4. **Time-series / OLAP / object stores are the wrong tool** for the in-product
   serving layer at this scale; external fan-out backends cover specialized
   long-term analytics if needed.
5. **Years of retention is trivial**; Postgres partitioning + a BRIN timestamp
   index is the answer if we ever want to be explicit about it.
</content>

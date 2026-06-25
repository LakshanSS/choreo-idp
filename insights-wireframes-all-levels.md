# Insights — Backstage Wireframes (Org · Project · Component)

Wireframes for the **Insights** surface at all three altitudes. Inside Insights
there are **two sub-tabs — `DORA` and `Cost`**. These wireframes show the **DORA**
sub-tab only (Cost is a separate effort); the tab bar is drawn at every level so
the structure is clear.

Every element is backed by data we actually collect — the `deployment_events`
store (commit / branch / repo / authoredAt / result / deploy_finished_at, see
`dora-metrics-calculation.md`) and the existing `incident_entries` store (for
CFR / MTTR) — so nothing shown here is speculative.

> **The model in one line:** the *level* (org → project → component) is just a
> wider/narrower scope filter over the same event store, so the **same scorecards
> and the same drill-down** appear at every altitude — only the aggregation
> breadth changes.

---

## Placement & tab structure

| Level | Entity / surface | Where the Insights nav lives | Scope filter |
| --- | --- | --- | --- |
| **Organization** | sidebar page (or `Domain` entity) | global "Insights" nav item | `namespace = org` |
| **Project** | `system` entity | new **Insights** tab (next to Incidents / Cost Analysis) | `namespace, project` |
| **Component** | `component` entity | new **Insights** tab (next to Alerts) | `namespace, project, component` |

Inside every Insights surface, a sub-tab bar selects the module:

```
  Insights ▸   ▟ DORA ▙ │ Cost
               └──┬───┘
            (shown below)   (separate effort — not wireframed here)
```

`Environment` and time-range are filters present on the DORA sub-tab at every
level.

Legend: `● ELITE / HIGH / MEDIUM / LOW` = DORA band · `▲ / ▼ / ▬` = trend vs.
previous window (direction is metric-aware — faster LT / MTTR is better).

---

## 1 — Organization level (the CIO dashboard)

Aggregates every project in the org. Top-line health in one screen, then a
project leaderboard to find the outliers.

```
 OpenChoreo ▸ Insights                                                          Organization
 ════════════════════════════════════════════════════════════════════════════════════════════════
  Insights · Acme Platform                                          ▟ DORA ▙ │ Cost
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  Delivery (DORA) — all 14 projects                        [ Env: All ▾ ]  [ Last 30 days ▾ ]  ⟳ ⤓

  ┌── Deployment Freq ──┐ ┌── Lead Time ───────┐ ┌── Change Fail Rate ┐ ┌──────── MTTR ──────┐
  │    38.6 / day        │ │      6h 04m         │ │       7.8 %         │ │       42m          │
  │  ● ELITE             │ │   ● HIGH            │ │   ● HIGH            │ │   ● ELITE          │
  │  ▁▂▃▄▅▆▇   ▲ 9%      │ │   ▇▆▅▄▃▂   ▼ 14%    │ │   ▃▂▃▄▃▂   ▲ 3%     │ │   ▂▁▃▁▂   ▼ 11%    │
  │  vs prev 30 days     │ │   vs prev 30 days   │ │   vs prev 30 days   │ │   vs prev 30 days  │
  └──────────────────────┘ └─────────────────────┘ └─────────────────────┘ └────────────────────┘

  totals (30d):  4,920 deployments   ·   384 failed   ·   61 incidents

  ┌─ Projects — DORA leaderboard ─────────────────────────────────────────────────  sort: [ CFR ▾ ]┐
  │  Project                    DF/day    Lead time    CFR        MTTR                              │
  │ ────────────────────────────────────────────────────────────────────────────────────────────  │
  │  payments-project            6.1 ●E    3h 10m ●E    12.4% ●M    1h 02m ●H                    ⤷ │
  │  patient-management-project  4.2 ●E    3h 12m ●H     6.5% ●H      28m ●E                      ⤷ │
  │  billing-project             2.0 ●E    9h 40m ●M     9.1% ●H      51m ●E                      ⤷ │
  │  notifications-project       0.6 ●H    1d 04h ●M     4.0% ●E    2h 18m ●H                     ⤷ │
  │  search-project              3.4 ●E    5h 20m ●H    16.2% ●L    1h 47m ●H                     ⤷ │
  │  …  (9 more)                                                                                   │
  │                                                                            ‹ 1 2 … ›  Rows 25 ▾ │
  └───────────────────────────────────────────────────────────────────────────────────────────────┘
        ●E Elite  ●H High  ●M Medium  ●L Low   ·   red badge = a metric in the Low band   ⤷ open project

  ┌─ Org trend ───────────────────────────────────────────────  [ Change Failure Rate ▾ ] [ weekly ▾ ]┐
  │  15%┤                                                                                            │
  │  10%┤              ╭──╮         ╭───╮                                                            │
  │   5%┤   ╭───╮  ╭──╯  ╰────╮╭───╯   ╰────────                                                     │
  │   0%┼───┴───┴──┴──────────┴┴───────────────────────────────────────────────────────────────     │
  │      W1     W2     W3      W4      W5      W6                                                     │
  └─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Drives / data:**
- 4 aggregate scorecards = `dora/query` with `searchScope={namespace}`.
- leaderboard = one `dora/query` per project (or a grouped query); each row's `⤷`
  opens that project's Insights tab.
- org trend = `dora/trends/query` with `searchScope={namespace}`.

---

## 2 — Project level (primary deliverable)

DORA rolled up across the project's components, a trend chart, then the
deployment-history table.

```
 patient-management-project                                              System ▸ Project
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  Overview │ Definition │ Diagram │ Logs │ Traces │ Incidents │ ▟ Insights ▙ │ RCA
 ════════════════════════════════════════════════════════════════════════════════════════════════
  Insights                                                          ▟ DORA ▙ │ Cost
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  Delivery (DORA)                          [ Env: All ▾ ]  [ Component: All ▾ ]  [ Last 30 days ▾ ] ⟳ ⤓

  ┌── Deployment Freq ──┐ ┌── Lead Time ───────┐ ┌── Change Fail Rate ┐ ┌──────── MTTR ──────┐
  │    4.2 / day         │ │      3h 12m         │ │       6.5 %         │ │       28m          │
  │  ● ELITE             │ │   ● HIGH            │ │   ● ELITE           │ │   ● ELITE          │
  │  ▁▂▃▄▅▆▇▆▅  ▲ 12%    │ │   ▇▆▅▄▃▂▁  ▼ 18%    │ │   ▁▂▁▃▂▁▁  ▬ 0%     │ │   ▂▁▃▁▂▁  ▼ 22%    │
  │  vs prev 30 days     │ │   vs prev 30 days   │ │   vs prev 30 days   │ │   vs prev 30 days  │
  └──────────────────────┘ └─────────────────────┘ └─────────────────────┘ └────────────────────┘
        (green = improving · red = worse — direction is metric-aware)

  ┌─ Metric over time ───────────────────────────────────────────  [ DF ▾ ]  [ weekly ▾ ] ────────┐
  │  6 ┤                                 ╭╮                                                         │
  │  4 ┤              ╭─╮      ╭──╮    ╭──╯ ╰╮   ╭───╮                                              │
  │  2 ┤   ╭───╮  ╭──╯  ╰──╮╭─╯   ╰────╯    ╰─────╯ ╰──                                             │
  │  0 ┼───┴───┴──┴───────┴┴────────────────────────────────────────────────────────────────────   │
  │     W1     W2     W3      W4      W5      W6      W7      W8                                     │
  │     ● deploy   ✕ failed deploy   ▮ incident window                                              │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘

  ┌─ Deployment history ──────────────────────────────────────────────────────────────────────────┐
  │  When     Component               Env    Commit    Author      Result   Lead time   Incident   │
  │ ────────────────────────────────────────────────────────────────────────────────────────────── │
  │  2h ago   patient-mgmt-service    prod   a1b2c3d   p.fernando  ✅ ok     2h 40m      —          │
  │  6h ago   billing-service         prod   f4e5d6a   a.perera    ✕ fail    —           INC-204 ⤷ │
  │  1d ago   patient-mgmt-service    stage  9c8b7a6   k.silva     ✅ ok     1h 02m      —          │
  │  1d ago   notifications-worker    prod   3d2e1f0   p.fernando  ✅ ok     5h 18m      —          │
  │                                                                          ‹ 1 2 3 … ›  Rows 25 ▾ │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘
    ↳ commit → Build run · incident → Project Incidents tab · row → component Insights
```

**Drives / data:**
- scorecards = `dora/query` with `searchScope={namespace, project}` (+ env).
- trend = `dora/trends/query` (same scope).
- history = `deployments/query` — `commit`/`author` from `workload.source`,
  `incident` from the local join, `commit→` links to the Build run.

---

## 3 — Component level (drill-down)

A single service: per-env DORA and its recent deploys with full source + incident
linkage.

```
 patient-management-service                                          Component ▸ Service
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  Overview │ Build │ Deploy │ Logs │ Events │ Metrics │ Alerts │ ▟ Insights ▙ │ Wirelogs │ API
 ════════════════════════════════════════════════════════════════════════════════════════════════
  Insights · this component                                         ▟ DORA ▙ │ Cost
 ──────────────────────────────────────────────────────────────────────────────────────────────────
  Delivery (DORA)                                          [ Env: prod ▾ ]   [ Last 30 days ▾ ]  ⟳ ⤓

  ┌── Deployment Freq ──┐ ┌── Lead Time ───────┐ ┌── Change Fail Rate ┐ ┌──────── MTTR ──────┐
  │    1.8 / day         │ │      2h 40m         │ │       4.0 %         │ │       19m          │
  │  ● ELITE             │ │   ● ELITE           │ │   ● ELITE           │ │   ● ELITE          │
  │  ▁▂▃▅▆▇▆▅▄  ▲ 8%     │ │   ▇▆▄▃▂▁▁  ▼ 25%    │ │   ▁▁▂▁▁▁  ▼ 50%     │ │   ▁▂▁▁▂▁  ▬ 0%     │
  └──────────────────────┘ └─────────────────────┘ └─────────────────────┘ └────────────────────┘

  ┌─ Recent deployments — this component ──────────────────────────────────────────────────────────┐
  │  When    Env    Commit    Branch   Author      Result   Build    Lead time   Incident          │
  │ ────────────────────────────────────────────────────────────────────────────────────────────── │
  │  2h ago  prod   a1b2c3d   main     p.fernando  ✅ ok     4m 12s   2h 40m      —                │
  │  1d ago  stage  9c8b7a6   main     k.silva     ✅ ok     3m 50s   1h 02m      —                │
  │  3d ago  prod   5e4d3c2   main     p.fernando  ✕ fail    6m 30s   —           INC-198 · 41m ⤷  │
  │  4d ago  prod   2b1a0f9   main     a.perera    ✅ ok     4m 02s   3h 11m      —                │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘
    ↳ commit → Build run · branch/author from workload.source · incident → Project Incidents

  ↳ "Investigate with AI" pre-scopes the assistant to this component + env + window.
```

**Drives / data:**
- scorecards = `dora/query` with `searchScope={namespace, project, component}`.
- deployments = `deployments/query` scoped to the component — `commit`, `branch`,
  `author`, `result`, `buildDuration`, `leadTime` all come straight off the
  `deployment_events` row; `incident` is the local join.

---

## 4 — Cross-level consistency (why this works)

| | Org | Project | Component |
| --- | --- | --- | --- |
| sub-tabs | DORA · Cost | DORA · Cost | DORA · Cost |
| 4 DORA scorecards | aggregate, all projects | rolled up over components | single component |
| breakdown table | project leaderboard | deployment history | this component's deploys |
| trend chart | org trend | per-metric trend | per-metric trend |
| scope filter | `{namespace}` | `{namespace, project}` | `{namespace, project, component}` |

Drill-down is continuous: an org scorecard → click a project row → project DORA
tab → click a deployment row → component DORA tab → click a commit/incident → the
exact Build run or Incident. **Every top-line number is explainable down to the
deploy that moved it** — which is what makes Insights a dashboard, not four static
charts.

---

## 5 — DORA band reference (for the ● badges)

| Metric | Elite | High | Medium | Low |
| --- | --- | --- | --- | --- |
| Deployment Frequency | on-demand / multiple per day | weekly–monthly | monthly–6mo | < every 6mo |
| Lead Time | < 1 day | 1 day–1 week | 1 week–1 month | > 1 month |
| Change Failure Rate | ≤ 5% | 5–10% | 10–15% | > 15% |
| MTTR | < 1 hour | < 1 day | 1 day–1 week | > 1 week |
</content>

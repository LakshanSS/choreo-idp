# DORA / Engineering Insights — Backstage Portal Wireframes

Placement is grounded in the real Backstage catalog UI
(`packages/app/src/components/catalog/EntityPage.tsx`). The header filters reuse
the existing `IncidentsFilter` pattern (environment selector + time range); the
deployment-history table mirrors `IncidentsTable` / `IncidentRow`.

## Placement summary

| Where | Entity kind | Page var (EntityPage.tsx) | New tab | Scope |
| --- | --- | --- | --- | --- |
| **Project › Insights** (primary) | `system` | `systemPage` (after Incidents, ~L725) | `/insights` | DORA rolled up across the project's components |
| **Component › Insights** (drill-down) | `component` | `serviceEntityPage` (~L367) + `genericComponentEntityPage` (~L474), after Alerts | `/insights` | single component, per-env |
| Component › Overview teaser (optional) | `component` | `OverviewContent` next to DeploymentStatusCard | — | quick scorecard linking into the tab |
| Environment › Delivery (future) | `environment` | `environmentPage` | `/delivery` | per-env DF/CFR |
| Global "Engineering Insights" page (future) | — | `Root.tsx` sidebar | route | across all projects |

All Insights tabs are gated behind `FeatureGatedContent feature="observability"`,
making them siblings of Incidents / Traces / RCA — reinforcing that DORA lives in
the observability plane. The "Investigate with AI" affordance reuses the
portal-assistant composition seam already used by `InvestigateLogButton` on the
Logs tab.

---

## 1 — Project › Insights tab (PRIMARY)

```
 patient-management-project                                            System ▸ Project
 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Overview │ Definition │ Cell Diagram │ Diagram │ Logs │ Traces │ Incidents │ ▟ Insights ▙ │ RCA Reports │ Cost Analysis
 ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

  Engineering Insights · DORA          [ Env: All ▾ ]  [ Component: All ▾ ]  [ Last 30 days ▾ ]  ⟳  ⤓
  ─────────────────────────────────────────────────────────────────────────────────────────────────

  ┌── Deployment Frequency ──┐ ┌── Lead Time for Chg ─┐ ┌── Change Failure Rate ┐ ┌──────── MTTR ───────┐
  │                          │ │                      │ │                       │ │                     │
  │     4.2 / day            │ │      3h 12m          │ │       6.5 %           │ │       28m           │
  │   ● ELITE                │ │   ● HIGH             │ │   ● ELITE             │ │   ● ELITE           │
  │   ▁▂▃▄▅▆▇▆▅   ▲ 12%      │ │   ▇▆▅▄▃▂▁   ▼ 18%    │ │   ▁▂▁▃▂▁▁   ▬ 0%      │ │   ▂▁▃▁▂▁   ▼ 22%    │
  │   vs prev 30 days        │ │   vs prev 30 days    │ │   vs prev 30 days     │ │   vs prev 30 days   │
  └──────────────────────────┘ └──────────────────────┘ └───────────────────────┘ └─────────────────────┘
        (green = improving ▲ · red = worse ▲ — direction is metric-aware; faster LT/MTTR is better)

  ┌─ Deployment frequency over time ───────────────────────────────────  [ DF ▾ ]  [ weekly ▾ ] ─┐
  │  6 ┤                                 ╭╮                                                      │
  │  4 ┤              ╭─╮      ╭──╮    ╭──╯ ╰╮   ╭───╮                                           │
  │  2 ┤   ╭───╮  ╭──╯  ╰──╮╭─╯   ╰────╯    ╰─────╯ ╰──                                          │
  │  0 ┼───┴───┴──┴───────┴┴──────────────────────────────────────────────────────────────────   │
  │     W1     W2     W3      W4      W5      W6      W7      W8                                 │
  │     ● deploy   ✕ failed deploy   ▮ incident window                                           │
  └──────────────────────────────────────────────────────────────────────────────────────────────┘

  ┌─ Deployment history ─────────────────────────────────────────────────────────────────────────────┐
  │  When        Component                 Env    Commit    Result   Lead time   Incident            │
  │ ───────────────────────────────────────────────────────────────────────────────────────────────  │
  │  2h ago      patient-mgmt-service      prod   a1b2c3d   ✅ ok     2h 40m      —                  │
  │  6h ago      billing-service           prod   f4e5d6a   ✕ fail    —           INC-204 · 28m  ⤷   │
  │  1d ago      patient-mgmt-service      stage  9c8b7a6   ✅ ok     1h 02m      —                  │
  │  1d ago      notifications-worker      prod   3d2e1f0   ✅ ok     5h 18m      —                  │
  │  2d ago      billing-service           prod   7a6b5c4   ✅ ok     2h 55m      —                  │
  │                                                                            ‹ 1 2 3 … ›  Rows 25 ▾│
  └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 2 — Component › Insights tab (per-component drill-down)

```
 patient-management-service                                          Component ▸ Service
 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Overview │ Definition │ Build │ Deploy │ Logs │ Events │ Metrics │ Alerts │  ▟ Insights ▙ │ WireLogs │ API 
 ══════════════════════════════════════════════════════════════════════════════════════════════════════════════

  Delivery Insights · DORA                         [ Env: prod ▾ ]   [ Last 30 days ▾ ]   ⟳  ⤓
  ─────────────────────────────────────────────────────────────────────────────────────────────────

  ┌── Deployment Frequency ──┐ ┌── Lead Time for Chg ─┐ ┌── Change Failure Rate ┐ ┌──────── MTTR ───────┐
  │     1.8 / day            │ │      2h 40m          │ │       4.0 %           │ │       19m           │
  │   ● ELITE                │ │   ● ELITE            │ │   ● ELITE             │ │   ● ELITE           │
  │   ▁▂▃▅▆▇▆▅▄   ▲ 8%       │ │   ▇▆▄▃▂▁▁   ▼ 25%    │ │   ▁▁▂▁▁▁   ▼ 50%      │ │   ▁▂▁▁▂▁   ▬ 0%     │
  └──────────────────────────┘ └──────────────────────┘ └───────────────────────┘ └─────────────────────┘

  ┌─ This component — recent deployments ───────────────────────────────────────────────────────────┐
  │  When        Env     Commit    Author         Result    Build    Lead time    Incident          │
  │ ─────────────────────────────────────────────────────────────────────────────────────────────── │
  │  2h ago      prod    a1b2c3d   p.fernando      ✅ ok      4m 12s   2h 40m       —               │
  │  1d ago      stage   9c8b7a6   k.silva         ✅ ok      3m 50s   1h 02m       —               │
  │  3d ago      prod    5e4d3c2   p.fernando      ✕ fail     6m 30s   —            INC-198 · 41m ⤷ │
  │  4d ago      prod    2b1a0f9   a.perera        ✅ ok      4m 02s   3h 11m       —               │
  └─────────────────────────────────────────────────────────────────────────────────────────────────┘

  ↳ commit → Build tab run · incident → Project Incidents · "Investigate" opens the assistant
    pre-scoped to this component + env + window.
```

## 3 — Component › Overview teaser card (optional)

Sits next to `DeploymentStatusCard` / `RuntimeHealthCard` in `OverviewContent`.

```
  ┌─ Delivery health (30d) ──────────────────────┐
  │  Deploy freq   1.8/day      ● ELITE           │
  │  Lead time     2h 40m       ● ELITE           │
  │  Change fail   4.0 %        ● ELITE           │
  │  MTTR          19m          ● ELITE           │
  │                              [ View Insights → ]│
  └───────────────────────────────────────────────┘
```

## 4 — Assistant drawer (opened from "Investigate with AI")

Reuses the existing portal-assistant panel, pre-scoped — same seam as the Logs
"Investigate" button (`InvestigateLogButton`).

```
  ┌─ Portal Assistant ──────────────────────────────────────────── ✕ ┐
  │  scope: patient-management-service · prod · last 30 days          │
  │ ────────────────────────────────────────────────────────────────  │
  │  🧑  Why did change failure rate spike on June 12?                 │
  │                                                                    │
  │  🤖  CFR rose to 12% on Jun 12 driven by 2 failed prod deploys:    │
  │      • commit 5e4d3c2 (p.fernando) → INC-198, recovered in 41m     │
  │      • commit 8f7e6d5 (a.perera)   → rollback, no incident         │
  │      Both touched the billing client. Lead time was normal …       │
  │      [ open INC-198 ]  [ open run 5e4d3c2 ]                        │
  │ ────────────────────────────────────────────────────────────────  │
  │  Ask a follow-up…                                            [ ➤ ] │
  └────────────────────────────────────────────────────────────────────┘
```

---

## DORA band reference (2024 bands — for the ●ELITE/HIGH/MEDIUM/LOW badges)

| Metric | Elite | High | Medium | Low |
| --- | --- | --- | --- | --- |
| Deployment Frequency | on-demand / multiple per day | weekly–monthly | monthly–6mo | < every 6mo |
| Lead Time | < 1 day | 1 day–1 week | 1 week–1 month | > 1 month |
| Change Failure Rate | ≤ 5% | 5–10% | 10–15% | > 15% |
| MTTR | < 1 hour | < 1 day | 1 day–1 week | > 1 week |

## Component → data source mapping (for the build)

| UI element | Source API (observer DORA read API) |
| --- | --- |
| 4 scorecards | `GET /api/v1/dora/metrics?project=&component=&environment=&from=&to=` |
| sparkline / trend chart | `GET /api/v1/dora/trends?metric=DF|LT|CFR|MTTR&interval=day|week` |
| deployment history table | `GET /api/v1/delivery/deployments?...` (paginated) |
| incident column | observer incident store (existing) — joined locally in obs plane |
| "Investigate with AI" | portal-assistant `/chat`, scoped via new `delivery_insights` MCP tool |

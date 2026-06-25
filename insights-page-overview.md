# Insights — the CIO Dashboard for OpenChoreo

*Problem framing, personas, and justification for a unified Insights surface in the
Backstage portal — at organization, project, and component level.*

> **One line:** Today OpenChoreo can *run* software well, but it can't yet *answer
> the questions a CIO asks about it* — "are we shipping faster?", "is it stable?",
> "what is it costing us?" — in one place. **Insights** is that place: a single
> portal surface that rolls delivery performance (DORA) and cloud spend (FinOps /
> Cost) up from a single component to a whole project to the entire organization.

---

## 1. The problem we're solving

OpenChoreo already *produces* the raw signals an executive cares about:

- **Delivery signals** — builds (`WorkflowRun`), releases (`ComponentRelease`),
  deployments (`ReleaseBinding` reaching `Ready`), and incidents (observer
  incident store). These are the inputs to the four DORA metrics.
- **Cost signals** — the FinOps / Cost Analysis capability already surfaces cloud
  spend per project/environment in the portal
  (`openchoreo-observability/.../CostAnalysis`).

But these signals have three problems today:

1. **They're scattered.** In the portal they live as *separate, peer tabs* —
   `Logs`, `Traces`, `Incidents`, `RCA Reports`, `Cost Analysis`, `Alerts`,
   `Metrics`. Each is a deep operational tool aimed at an engineer debugging
   *one* thing. There is no single surface that says "here is how this part of
   the org is doing."
2. **They don't roll up.** Everything is component- or environment-scoped. There
   is no project-wide or organization-wide view. A CIO cannot ask "how is the
   whole platform trending this quarter?" — the data only answers
   "what happened in this one service?"
3. **They're not framed as outcomes.** DF / Lead Time / Change Failure Rate /
   MTTR and cloud spend are *business outcomes* (speed, stability, efficiency).
   Presented as raw operational tabs, they read as engineering plumbing, not as
   the executive-level KPIs they actually are.

**Insights** fixes all three: it consolidates the outcome-level signals into one
named surface, makes that surface exist at three altitudes (org → project →
component), and frames the numbers as the speed/stability/cost story a leader
reads in thirty seconds.

---

## 2. Who needs this — and why

The portal today is built almost entirely for the **person doing the work**
(developer debugging logs, an SRE chasing an incident). Insights is built for the
**person accountable for the work**. That's a different audience with different
questions.

| Persona | The question they walk in with | What Insights gives them |
| --- | --- | --- |
| **CIO / CTO / VP Engineering** | "Are we getting faster, staying stable, and spending efficiently — across the whole org?" | The org-level dashboard: DORA bands + total/trending spend across all projects, in one screen. |
| **Engineering Director / Group lead** | "Which of my projects are healthy and which are dragging?" | Project-level rollups side by side; spot the outlier project. |
| **Project / Team lead, EM** | "Is *my* team shipping well, and is anything regressing?" | Project Insights: the four DORA scorecards with trend + deltas, deployment history, and this project's spend. |
| **Platform / FinOps owner** | "Where is the cloud bill going and is it justified by delivery?" | Cost insights next to delivery insights — efficiency, not just spend in isolation. |
| **Developer / SRE (drill-down)** | "My team's number moved — which component and which deploy caused it?" | Component-level Insights: per-component DORA + the deploy/incident that moved the metric. |

The unifying idea: **this is the CIO dashboard.** It's the view a leader opens to
get a defensible, data-backed answer to "how is engineering doing?" without
asking five teams for five spreadsheets — and the same view a team lead drills
into to act on it. One surface, two altitudes of the same truth.

---

## 3. Why now

Two independent efforts are converging:

- **Delivery Insights / DORA** (proposal [#3668](https://github.com/openchoreo/openchoreo/discussions/3668)) —
  computes and surfaces the four DORA metrics from OpenChoreo's own delivery
  events.
- **Cost Analysis / FinOps** — already shipping in the observability plugin,
  surfacing cloud spend per project/environment.

Shipping these as *two more disconnected tabs* would repeat exactly the
"scattered signals" problem above and miss the obvious synergy: **speed,
stability, and cost are the three axes of the same executive question.** A CIO
never asks about deployment frequency in isolation from what it costs. Bringing
them under one **Insights** roof — now, before either is fully built out — is the
moment to set the information architecture right.

It also gives both efforts a shared, extensible home. Reliability/SLO insights,
security posture, and developer-experience (SPACE) metrics are the natural next
tenants of the same surface — Insights is the container that lets them land
without inventing a new top-level tab each time.

---

## 4. What lives under Insights

Insights is a **container**, not a single chart. Its tenants, in priority order:

| Module | Status | Answers | Headline metrics |
| --- | --- | --- | --- |
| **Delivery (DORA)** | proposed (#3668) | "Are we shipping fast and safely?" | Deployment Frequency, Lead Time for Changes, Change Failure Rate, MTTR |
| **Cost (FinOps)** | shipping | "What is it costing, and is that efficient?" | Spend by project/env, trend, optimization recommendations |
| *Reliability / SLO* | future | "Are we meeting our reliability targets?" | SLO attainment, error budget burn |
| *Security posture* | future | "Are we exposed?" | Vuln counts, policy violations, time-to-remediate |
| *Developer Experience (SPACE)* | future | "Is the team's flow healthy?" | Review latency, WIP, deploy wait time |

The first two are real and in flight; the rest are why "Insights" (not "DORA",
not "Cost") is the right name for the surface.

---

## 5. Information architecture — three altitudes

The lead's ask is Insights at **org, project, and component** level. Each level is
the same idea at a different zoom, and each maps to a real entity in the catalog.

```
 Organization (sidebar / Domain)        ← CIO / VP Eng
   └─ "How is the whole platform doing?"
      DORA bands + total spend, aggregated across every project; project leaderboard
        │
        ▼ drill into a project
 Project  (system entity, new Insights tab)   ← Director / EM / team lead
   └─ "How is this project doing?"
      4 DORA scorecards (trend + Δ) · deployment history · this project's cost
        │
        ▼ drill into a component
 Component (component entity, new Insights tab) ← developer / SRE
   └─ "Which service moved the number, and why?"
      Per-component DORA · recent deploys + linked incidents · component cost
```

- **Organization level** — a global page (Backstage sidebar entry, or a `Domain`
  entity view). Aggregates across all projects; this is the literal "CIO
  dashboard." *(New surface.)*
- **Project level** — a new **Insights** tab on the `system` (project) entity,
  sitting alongside the existing observability tabs. DORA rolled up across the
  project's components, plus the project's cost. *(Primary deliverable.)*
- **Component level** — a new **Insights** tab on the `component` entity, for the
  drill-down: a single service's delivery and cost. *(Drill-down.)*

Drill-down is continuous: a number at org level is explainable by clicking down
to the project and then the component and finally the specific deployment +
incident that moved it. That "explainable from the top" property is what makes it
a *dashboard* and not just four disconnected charts.

---

## 6. How it maps to what OpenChoreo already has

Insights is mostly **consolidation and framing of capabilities that already
exist or are already proposed** — not a from-scratch build:

| Insights needs | Already exists / proposed | Gap to close |
| --- | --- | --- |
| Cost data + UI | `CostAnalysis` (FinOps) in the observability plugin | re-home it under Insights; add org rollup |
| DORA metrics + API | proposal #3668 (delivery events → `insights/dora/query`) | build the module (in flight) |
| Incident data (CFR / MTTR) | observer incident store (powers Incidents tab) | local join — already the plan |
| Per-component / per-project scoping | `ComponentSearchScope` + scope authz used by Incidents/Traces | reuse verbatim |
| Portal placement seam | `EntityPage.tsx` tabs (`system`, `component`) | add two `Insights` tabs |
| Org-level surface | Backstage sidebar (`Root.tsx`) / `Domain` entity | new aggregation page |

The expensive parts (the data, the auth model, the cost UI) are largely done or
designed. Insights is the **packaging decision** that turns them from scattered
tools into an executive product.

---

## 7. Justification summary — the value per stakeholder

- **For the CIO / leadership:** a single, trustworthy answer to "how is
  engineering doing?" across speed, stability, and cost — sourced from the
  platform's own ground truth, not self-reported. Decisions (where to invest,
  which team needs help, whether the cloud bill is justified) get a data backing.
- **For engineering managers:** outcome metrics with trend and deltas, so they
  can see regression early and have an objective, benchmarked
  (Elite/High/Medium/Low) conversation about delivery health.
- **For platform / FinOps owners:** cost and delivery in one frame — efficiency,
  not raw spend; the ability to tie spend back to the delivery it enables.
- **For developers / SREs:** the drill-down path means when a leader's number
  moves, the cause is one or two clicks away (component → deploy → incident),
  instead of a meeting.
- **For OpenChoreo as a product:** "Insights" is a recognizable, sellable
  category (every IDP — Backstage, Port, Cortex, DX — has one). It's the surface
  that makes OpenChoreo legible to buyers, not just operators, and it gives every
  future analytics signal a home instead of another top-level tab.

---

## 8. Scope & phasing (suggested)

1. **Phase 1 — Project Insights tab (DORA).** The primary deliverable from #3668:
   four scorecards + deployment history at `system` level. Highest-value, smallest
   surface.
2. **Phase 2 — Component Insights tab (DORA drill-down).** Per-component view +
   the deploy/incident that moved each metric.
3. **Phase 3 — Fold Cost under Insights.** Re-home the existing Cost Analysis as
   an Insights module at project and component level (delivery + cost in one
   surface).
4. **Phase 4 — Organization Insights page.** The aggregate "CIO dashboard":
   cross-project rollups and a project leaderboard.
5. **Later — new tenants.** Reliability/SLO, security posture, SPACE/DevEx, each
   added as an Insights module rather than a new tab.

---

## 9. Talking points for the meeting

1. **The problem isn't missing data — it's scattered, un-rolled-up, un-framed
   data.** Insights is the consolidation + framing layer.
2. **It's a CIO dashboard.** Built for the person *accountable* for delivery, not
   only the person *doing* it — a new and currently-unserved audience for the
   portal.
3. **DORA and Cost are the same question on two axes** (speed/stability vs.
   efficiency). They belong together; shipping them as two more tabs misses the
   point.
4. **Three altitudes, one truth:** org → project → component, fully drill-down,
   so any top-line number is explainable down to the deploy that caused it.
5. **Mostly packaging, not new build:** cost UI exists, DORA is designed, auth and
   scoping are reused. The decision is *architecture and naming*, and now is the
   time to make it — before either effort hardens into a standalone tab.
6. **Insights is extensible:** reliability, security, and DevEx are the next
   tenants — "Insights" is the name that survives them; "DORA" or "Cost" wouldn't.
</content>
</invoke>

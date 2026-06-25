# Meeting Notes — Engineering Insights & DORA (2026-06-19)

A follow-up to the earlier walkthrough of the Engineering Insights & DORA proposal
(#3668). This time the conversation grew beyond just DORA — into how OpenChoreo
should collect events, store data, and handle observability in general. A few of
the items below are directions we want to explore, not final decisions yet.

**Attendees:** _<fill in>_
**Previous session:** proposal walkthrough + review (2026-06-15).

---

## 1. Can we collect events from the data plane in a Kubernetes-native way?

Right now the design adds a small component in the control plane (an "emitter")
whose only job is to watch for deployments and send DORA events. The concern is
that we'd be building a special-purpose piece just for DORA.

Instead, could we pick up these signals straight from the **data plane** — the
place where the apps actually run and deployments actually happen — using normal
Kubernetes mechanisms (like Kubernetes events and resource status)? That way we're
not inventing a DORA-only component; we use one general way of collecting events
that DORA and other features can all share.

**Next step:** compare the two approaches — the control-plane emitter vs. picking
up events natively from the data plane — and decide which one captures deployments
more reliably and reuses better. One thing to settle: where is a "deployment
happened" moment most accurately seen — in the control plane, or in the data plane
once the rollout finishes?

---

## 2. Look at storage options other than SQL

So far the plan stores delivery events in the existing SQL database (PostgreSQL).
Before we commit to that, we should look at the alternatives and weigh the
trade-offs — for example time-series databases, an event/streaming store, or cheap
object storage for old data.

The important point: don't pick the storage just for DORA on its own. The right
choice depends a lot on the bigger storage question in item #3, so these two should
be decided together.

**Next step:** write up a short comparison of the realistic options against what we
actually need (filtering by org/project/component, joining deployments with
incidents, and keeping data for months or years).

---

## 3. Consolidate storage across all of OpenChoreo

OpenChoreo already runs several separate stores today — the SQL store for
incidents and alerts, Prometheus for metrics, plus logs and traces. If we add yet
another separate store just for DORA, we're adding one more silo.

The bigger idea is to step back and ask whether OpenChoreo can have a more unified
storage setup that all these features share, instead of each feature bringing its
own. DORA/Insights would then plug into that shared foundation rather than build
its own.

**Next step:** this is bigger than the Insights feature, so it goes to the working
group (item #6). In the meantime Insights can move forward on the current store,
designed so it can move onto the shared storage later.

---

## 4. Give OpenChoreo a way to export events that others can subscribe to

Beyond DORA, OpenChoreo should be able to **publish all of its events** so other
systems can **subscribe and receive them**. The DORA idea of "send events to
DevLake / DX / Datadog" is really just one example of this more general capability.

If we build a proper event export/subscription system once, DORA simply becomes one
of the things listening to it — not its own custom exporter. This connects naturally
to item #1 (how we collect events) and item #3 (where we store them): collect once,
store once, and let many consumers subscribe.

**Next step:** scope out a general event model and a subscription mechanism, and
confirm that DORA's needs are just a subset of it.

---

## 5. Wireframes should match the real portal and the Cost Insights UI

The current wireframes are rough sketches. They need to match how the actual
OpenChoreo Backstage portal looks and behaves, and — importantly — stay consistent
with the existing **Cost Insights** screens. Since DORA and Cost will sit side by
side as two tabs under one **Insights** page, they should share the same layout,
filters, and navigation so the whole thing feels like one product, not two.

**Next step:** redo the org / project / component wireframes against the real portal
and review them next to the Cost UI to keep everything consistent.

---

## 6. Start a working group for observability and insights

Several of the items above — storage consolidation, event export, data-plane event
collection — are bigger than the DORA feature and touch the whole platform. They
shouldn't be decided ad-hoc inside one proposal.

So we'll set up an **Observability & Insights working group** to own these wider
topics. The DORA/Insights proposal keeps moving as a concrete deliverable, but it
sits under this group and feeds into the bigger decisions.

**Next step:** define the group — its scope, who's in it, and how often it meets —
and move the cross-cutting questions out of #3668 into the group.

---

## Where this leaves the proposal

DORA stays the concrete thing we're building. But three of its building blocks —
**how we collect events (#1), where we store them (#2 / #3), and how we export them
(#4)** — are now being designed as general OpenChoreo capabilities under the new
working group, with DORA as the first user rather than a one-off stack. The UI work
(#5) carries on in parallel against the real portal.

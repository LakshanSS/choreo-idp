# How the Workload carries commit / branch / repository / authoredAt

The DORA calculation reads `commit`, `branch`, `repository`, and `authoredAt`
from the `Workload`. This doc answers: **what does the Workload look like, how
does that data get there, and does the developer have to write it — or do we
generate it?**

> **Short answer:** the developer does **not** write it. `source` is *build
> metadata*, injected automatically at the same moment and through the same
> channel as the container `image` — by whoever produced that image (OpenChoreo's
> build, or an external CI pipeline). It never lives in the developer's
> hand-authored `workload.yaml`.

---

## 1. The model that already exists: `image` is injected, not authored

This is the crucial precedent. Today a developer's `workload.yaml` **descriptor**
never contains the image — it only describes the static shape of the workload
(endpoints, env, dependencies):

```yaml
# workload.yaml — authored by the developer, committed to the repo
apiVersion: openchoreo.dev/v1alpha1
kind: Workload
metadata:
  name: patient-management-service-workload
endpoints:
  rest-api:
    type: HTTP
    port: 8080
```

The actual image is supplied **at apply time**, as a flag:

```bash
occ workload create -f workload.yaml \
  --project patient-management-project \
  --component patient-management-service \
  --image ghcr.io/acme/patient-mgmt:sha-a1b2c3d
```

In the code, `--image` → `params.ImageURL` → stamped onto `Container.Image` in
`createBaseWorkload` (`internal/occ/resources/workload/converter.go`). The image
is **per-build metadata injected by the producer**, never static descriptor
content.

**`source` follows the identical pattern.** The commit that produced an image is
exactly as per-build as the image itself — so it rides the same channel, set right
next to `Container.Image`, and is likewise *not* something the developer writes.

---

## 2. What the Workload looks like with `source`

We add one optional field, `source`, to `WorkloadTemplateSpec` (sibling of
`container`). A populated `Workload` then looks like:

```yaml
apiVersion: openchoreo.dev/v1alpha1
kind: Workload
metadata:
  name: patient-management-service-workload
  namespace: default
spec:
  owner:
    projectName: patient-management-project
    componentName: patient-management-service
  container:
    image: ghcr.io/acme/patient-mgmt:sha-a1b2c3d     # injected at apply time
  source:                                            # ← NEW, injected alongside image
    commit: a1b2c3d4e5f6
    branch: main
    repository: https://github.com/acme/patient-mgmt
    authoredAt: "2026-06-16T07:10:00Z"
  endpoints:
    rest-api:
      type: HTTP
      port: 8080
```

`source` is **optional** — existing Workloads without it stay valid, and a missing
`authoredAt` simply excludes that deploy from Lead Time (DF/CFR/MTTR are
unaffected).

---

## 3. Does the developer add this data? — No. Here's who does.

`source` is generated/injected by **whoever built the image**, at the moment the
image is built. There are two paths, and the developer authors neither:

### Path A — OpenChoreo ran the build (internal build)

OpenChoreo's build pipeline already **checks out the repo at a specific commit**,
so it inherently knows `commit`, `branch`, and `repository` — they're already
build parameters. When the build produces the image and creates the `Workload`,
it stamps `source` on alongside `Container.Image`.

`authoredAt` (the commit *author* timestamp) is the one value not already on hand;
OpenChoreo resolves it with a **best-effort call to its existing git provider
client** (`GetCommitInfo`) — off the deployment critical path, so if git is
briefly unreachable the deploy still proceeds and `authoredAt` is backfilled
later.

→ **Developer effort: zero.** Everything comes from build inputs OpenChoreo
already has.

### Path B — an external CI pipeline built the image (GitHub Actions, GitLab CI, Jenkins, …)

Here OpenChoreo never ran the build, so there's no `WorkflowRun` — but the CI
runner has the git checkout, which means it has *better* source data than we
could fetch. It passes `source` the same way it already passes `--image`:

```yaml
# .github/workflows/deploy.yml — authored ONCE by a platform/CI engineer, not per-deploy
- run: |
    occ workload create -f workload.yaml \
      --project patient-management-project \
      --component patient-management-service \
      --image $IMAGE \
      --commit       "${{ github.sha }}" \
      --branch       "${{ github.ref_name }}" \
      --repository   "${{ github.server_url }}/${{ github.repository }}" \
      --authored-at  "$(git show -s --format=%aI ${{ github.sha }})"
```

All four values come straight from CI context variables the pipeline already
exposes. The `--authored-at` is a one-line `git show` against the checkout CI
already has — no git-provider round-trip, no credentials needed on the OpenChoreo
side.

→ **Developer effort: zero per deploy.** The flags are added **once** to the CI
template by whoever owns the pipeline, exactly like `--image` was. Every
subsequent deploy carries `source` automatically.

| Path | Who populates `source` | `commit/branch/repo` from | `authoredAt` from |
| --- | --- | --- | --- |
| **OpenChoreo build** | the build pipeline | build params it already has | OpenChoreo git provider lookup (best-effort) |
| **External CI** | the CI step (`occ workload …`) | CI context vars (`github.sha`, …) | `git show -s --format=%aI` on CI's checkout |

---

## 4. Where `source` is *not* — the descriptor

It is deliberately **not** added to the committed `workload.yaml` descriptor.
The descriptor is developer-authored, version-controlled, and describes the
*static* shape of the workload. The commit that produced a given image is *dynamic
per-build* data — putting it in a committed file would be wrong (it'd be stale the
moment the next commit lands) and would force developers to hand-edit it every
build. So it travels the same injected-at-apply channel as `image`, never the
static descriptor.

---

## 5. From Workload → ComponentRelease → DORA (why this object)

`ComponentRelease.spec.workload` is a **full, immutable, frozen copy** of the
`WorkloadTemplateSpec` (`+kubebuilder:validation:XValidation:rule="self ==
oldSelf"`). So putting `source` on the workload gives us two things for free:

1. It is set on the live `Workload` by whoever built the image (internal **or**
   external CI).
2. It is **automatically frozen** into `ComponentRelease.spec.workload.source`
   when the release is cut — immutable, so a later squash or branch move can't
   corrupt the historical Lead Time.

The delivery emitter then reads `spec.owner.{projectName,componentName}` +
`spec.workload.source.*` off the `ComponentRelease` and writes them into the
`deployment_events` row (see `dora-metrics-calculation.md`).

```
 build (OpenChoreo or external CI)
   └─ sets Workload.spec.source  ── same channel as Container.image
        │
        ▼ release cut → frozen, immutable copy
 ComponentRelease.spec.workload.source.{commit,branch,repository,authoredAt}
        │
        ▼ delivery emitter
 deployment_events row → Lead Time = deploy_finished_at − authoredAt
```

---

## 6. Summary (talking points)

1. **The developer authors none of it.** `source` is build metadata, injected
   automatically — exactly like the container `image` is today.
2. **It rides the existing `image` channel** (`occ workload` apply / API), set
   right next to `Container.Image` — not the committed `workload.yaml` descriptor.
3. **Internal builds** stamp it from build params + a best-effort git lookup for
   `authoredAt`.
4. **External CI** passes it from CI context vars in one place in the pipeline
   template — added once, automatic thereafter — which is also how we support the
   no-`WorkflowRun` case.
5. **It freezes into the immutable `ComponentRelease` copy**, so Lead Time stays
   correct forever even if history is rewritten.
6. **All optional** — missing `source` just drops that deploy from Lead Time;
   nothing else breaks.
</content>

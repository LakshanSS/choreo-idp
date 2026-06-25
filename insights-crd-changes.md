## CRD Changes — Delivery Insights / DORA

The producers already emit almost all the raw signal; the gaps are about
**persisting and correlating** it. Two CRDs get new, additive, optional fields —
no breaking changes. `ReleaseBinding` needs none.

### Summary

| # | CRD | Field | Type | Mutability | Enables |
| --- | --- | --- | --- | --- |
| ① | `WorkflowRun.status.source` | `*DeliverySource` | optional | mutable (status) | commit/branch/repo linkage (Gap A) |
| ② | `ComponentRelease.spec.source` | `*ComponentReleaseSource` | optional | immutable (commit/branch/repo); `authoredAt` set-once | frozen source snapshot + Lead Time (Gap A, LT) |
| ③ | `ComponentRelease.spec.source.authoredAt` | `*metav1.Time` | optional | set-once | Lead Time basis (Gap D) |
| — | `ReleaseBinding` | none | — | — | `status.conditions[Ready]` already is the deploy moment |

All fields are optional → existing objects remain valid, no migration required.

---

### Shared type — `DeliverySource`

A small reusable struct, defined once in the `v1alpha1` package (e.g. in
`workflowrun_types.go`, where it is first used) and referenced from
`ComponentRelease`.

```go
// DeliverySource captures the source-control coordinates an artifact was produced from.
type DeliverySource struct {
	// Commit is the git commit SHA the artifact was built from.
	// +kubebuilder:validation:Pattern=`^[0-9a-fA-F]{7,40}$`
	// +optional
	Commit string `json:"commit,omitempty"`

	// Branch is the git branch the build was triggered from.
	// +optional
	Branch string `json:"branch,omitempty"`

	// Repository is the normalized git repository URL.
	// +optional
	Repository string `json:"repository,omitempty"`
}
```

---

### ① `WorkflowRun.status.source`

**File:** `api/v1alpha1/workflowrun_types.go`
**Today:** `WorkflowRunStatus` has `Conditions`, `RunReference`, `Resources`,
`Tasks`, `StartedAt`, `CompletedAt` — **no source field**. The commit is passed in
as a workflow *parameter* but never surfaced on status.

**Add** to `WorkflowRunStatus`:

```go
	// Source is the source-control context the build ran against.
	// Populated when the run is reconciled; mirrors the commit/branch/repo
	// supplied at trigger time so downstream consumers can correlate builds
	// to source without re-reading workflow parameters.
	// +optional
	Source *DeliverySource `json:"source,omitempty"`
```

**Why:** makes the commit a first-class, queryable property of the build
(pointer + `omitempty`, matching the existing optional `RunReference
*ResourceReference`). This is the linkage that later gets frozen onto the
release. No `authoredAt` here — the build hot path should not depend on a git API
call.

---

### ② `ComponentRelease.spec.source` (immutable snapshot + `authoredAt`)

**File:** `api/v1alpha1/componentrelease_types.go`
**Today:** `ComponentReleaseSpec` fields (`Owner`, `ComponentType`, `Traits`,
`ComponentProfile`, `Workload`) are all immutable via
`+kubebuilder:validation:XValidation:rule="self == oldSelf"`. There is **no**
source field, and `ComponentReleaseStatus` is empty.

**Add** the source type:

```go
// ComponentReleaseSource is the immutable source-control snapshot of a release.
type ComponentReleaseSource struct {
	// Commit is the git commit SHA this release was built from. Immutable.
	// +kubebuilder:validation:Pattern=`^[0-9a-fA-F]{7,40}$`
	// +kubebuilder:validation:XValidation:rule="self == oldSelf",message="commit is immutable"
	// +optional
	Commit string `json:"commit,omitempty"`

	// Branch is the git branch this release was built from. Immutable.
	// +kubebuilder:validation:XValidation:rule="self == oldSelf",message="branch is immutable"
	// +optional
	Branch string `json:"branch,omitempty"`

	// Repository is the normalized git repository URL. Immutable.
	// +kubebuilder:validation:XValidation:rule="self == oldSelf",message="repository is immutable"
	// +optional
	Repository string `json:"repository,omitempty"`

	// AuthoredAt is the commit author timestamp, resolved from the git provider
	// at release time and used as the basis for Lead Time for Changes.
	// Set-once: it may be backfilled if it was empty at creation (best-effort
	// git lookup), but cannot be changed once set.
	// +kubebuilder:validation:XValidation:rule="self == oldSelf",message="authoredAt is immutable once set"
	// +optional
	AuthoredAt *metav1.Time `json:"authoredAt,omitempty"`
}
```

**Add** to `ComponentReleaseSpec`:

```go
	// Source is the immutable source-control snapshot for this release.
	// commit/branch/repository are frozen at creation; authoredAt is resolved
	// from the git provider (best-effort) and may be backfilled once.
	// +optional
	Source *ComponentReleaseSource `json:"source,omitempty"`
```

**Why:** `ComponentRelease` is the immutable release record, so it is the right
home for the frozen source snapshot. Freezing commit/branch/repo here means Lead
Time stays correct even if the branch moves or the commit is later squashed.

#### Immutability & best-effort `authoredAt` — the design choice

The immutability markers are placed on the **inner fields**, not on the whole
`source` block, on purpose:

- `commit` / `branch` / `repository` are always known at creation → truly
  immutable (`self == oldSelf`).
- `authoredAt` is resolved via a git-provider call that is **best-effort and off
  the deployment critical path**. If git is unreachable at creation, the release
  is still created with `authoredAt` empty and the value is **backfilled once**
  later by a reconcile.

A Kubernetes CEL transition rule (`self == oldSelf`) is only evaluated when the
field already existed in the old object. So on an optional field it yields
**set-once** semantics for free: unset → value is allowed (the backfill),
value → different value is rejected. That's exactly what `authoredAt` needs.
Putting a single rule on the whole `source` struct would instead block the
backfill, because `source` already existed (with `authoredAt` empty).

---

### ③ `ReleaseBinding` — no schema change

`ReleaseBinding.spec.environment` + `status.conditions[Ready]` already model
"this release was deployed to this environment." A `ReleaseBinding` first
reaching `Ready=True` for a generation **is** the deployment event — the delivery
emitter watches that transition. No new field needed.

---

### Generated artifacts & regeneration

After editing the `*_types.go` files:

```bash
make manifests generate   # regenerates CRD YAML + DeepCopy (zz_generated.deepcopy.go)
make openapi-codegen      # if the openchoreo-api OpenAPI surfaces these fields
go build ./...
```

The new `*DeliverySource` / `*ComponentReleaseSource` pointers need
`DeepCopyInto` entries — produced automatically by `make generate`.

---

### Backward compatibility

- Every field is **optional** with `omitempty` → existing `WorkflowRun` and
  `ComponentRelease` objects validate unchanged; no migration job.
- New `WorkflowRun.status.source` is populated going forward; historical runs
  simply have it empty.
- `ComponentRelease.spec.source` is written for new releases; old releases keep
  an empty source and are excluded from Lead Time (DF/CFR/MTTR are unaffected).

---

### Mapping back to metrics & gaps

| Change | Closes | Feeds metric |
| --- | --- | --- |
| ① `WorkflowRun.status.source` | Gap A (commit linkage) | LT (correlation) |
| ② `ComponentRelease.spec.source` (commit/branch/repo) | Gap A | LT, DF correlation |
| ③ `spec.source.authoredAt` | Gap D (authored time not fetched) | Lead Time for Changes |
| `ReleaseBinding` Ready=True (existing) | — | Deployment Frequency, CFR |
| observer incident store (existing) | Gap C (local) | CFR, MTTR |
```
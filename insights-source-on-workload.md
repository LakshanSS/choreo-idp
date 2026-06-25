## Where does commit metadata live? — Workload, not WorkflowRun

**Review comment (disc. #3668):** don't read the commit from `WorkflowRun`;
read it from the `Workload`, so the external-CI case is covered too.

This is correct, and the code backs it up. Below is the research and the
revised design.

---

### Why WorkflowRun is the wrong source of truth

`WorkflowRun` only exists when **OpenChoreo ran the build**. A large class of
users build on their own CI (GitHub Actions, GitLab CI, Jenkins, Argo, …),
push the image to a registry, and then just register the artifact with
OpenChoreo. In that flow **no `WorkflowRun` is ever created** — so any DORA
signal keyed off `WorkflowRun.status.source` is blank for exactly the users we
most want to support.

Both flows, however, converge on **one** object: the `Workload`.

```
 internal build:   git → WorkflowRun → image → Workload(image=...)         ┐
                                                                           ├─→ Workload
 external CI:       git → (their CI)  → image → occ workload apply --image ┘        │
                                                                                    ▼
                                                          ComponentRelease.spec.workload (frozen copy)
```

The `Workload` is the universal funnel. Its `container.image` is already set
the same way from both paths — `params.ImageURL` in
`internal/occ/resources/workload/converter.go` (`createBaseWorkload`). The
commit that produced that image should be captured **right next to the image**,
on the same object, by whoever set the image.

---

### The key structural win

`ComponentRelease.spec.workload` is a **full embedded copy** of
`WorkloadTemplateSpec`, and the whole block is already immutable:

```go
// componentrelease_types.go
// +kubebuilder:validation:XValidation:rule="self == oldSelf",message="spec.workload is immutable"
Workload WorkloadTemplateSpec `json:"workload"`
```

So if we add `source` to **`WorkloadTemplateSpec`**, it:

1. is set on the live `Workload` by whoever built the image (internal *or* CI), and
2. is **automatically frozen** into `ComponentRelease.spec.workload.source`
   when the release is cut — already immutable, no new rule, no separate
   `ComponentRelease.spec.source` field.

That deletes a whole CRD change from the earlier proposal and removes the
`WorkflowRun.status.source` dependency entirely.

---

### Proposed CRD change — one field, on the Workload

**File:** `api/v1alpha1/workload_types.go`

```go
// WorkloadSource captures the source-control coordinates the image was built from.
// Populated by whoever produced the image — the OpenChoreo build, or an external
// CI pipeline via `occ workload apply` / the API. All fields optional so existing
// Workloads stay valid.
type WorkloadSource struct {
	// Commit is the git commit SHA the image was built from.
	// +kubebuilder:validation:Pattern=`^[0-9a-fA-F]{7,40}$`
	// +optional
	Commit string `json:"commit,omitempty"`

	// Branch is the git branch the build was triggered from.
	// +optional
	Branch string `json:"branch,omitempty"`

	// Repository is the normalized git repository URL.
	// +optional
	Repository string `json:"repository,omitempty"`

	// AuthoredAt is the commit author timestamp — the basis for Lead Time for Changes.
	// Supplied by CI (which has the checkout) or resolved by OpenChoreo's git
	// provider for internal builds. Best-effort.
	// +optional
	AuthoredAt *metav1.Time `json:"authoredAt,omitempty"`
}
```

Add to `WorkloadTemplateSpec` (sibling of `Container`, so it travels into the
`ComponentRelease` copy):

```go
	// Source is the source-control context the container image was built from.
	// +optional
	Source *WorkloadSource `json:"source,omitempty"`
```

> Immutability comes for free on the release side: `spec.workload` is already
> `self == oldSelf`, so the frozen snapshot can't drift. On the live `Workload`
> the field stays mutable, which is what CI re-pushes need.

**`WorkflowRun.status.source`** → now **optional / droppable**. If we keep it at
all it's only a convenience mirror; it is no longer the DORA source of truth.
**`ComponentRelease.spec.source`** from the earlier draft → **deleted** (covered
by `spec.workload.source`).

---

### How each path populates it

| Path | Who sets `workload.source` | `authoredAt` from |
| --- | --- | --- |
| **OpenChoreo build** | build pipeline already knows the commit param; stamp it onto the Workload it creates | git provider lookup (`GetCommitInfo`, best-effort, off critical path) |
| **External CI** | `occ workload apply --image … --commit $SHA --branch $REF --repository $URL --authored-at $TS` | CI already has the git checkout — pass `git show -s --format=%aI` directly |

The descriptor / CLI gets matching fields. Concretely:

- **CLI** — add flags to `occ workload` (`CreateWorkloadParams` in
  `internal/occ/resources/workload/params.go`): `--commit`, `--branch`,
  `--repository`, `--authored-at`. `createBaseWorkload` sets
  `Spec.Source` alongside `Container.Image`.
- **API** — the create-workload request body grows an optional `source` object
  (regenerate via `make openapi-codegen`).
- **Descriptor (`workload.yaml`)** — *not* the place for it. The descriptor is
  developer-authored and committed to the repo; `source` is per-build metadata
  injected at apply time, exactly like `image`. So it rides the same channel as
  the image, never the static descriptor.

For external CI, `authoredAt` is **better** sourced from CI than from us — the
CI runner has the actual checkout, so no git-provider round-trip and no
provider-credential requirement on the OpenChoreo side.

---

### Why this is the right call (talking points)

1. **Covers external CI** — the whole point of the comment. DORA now works
   whether or not OpenChoreo ran the build.
2. **One object, one funnel** — both paths already converge on `Workload`;
   commit rides next to the image that it produced.
3. **Fewer CRD changes** — drops `ComponentRelease.spec.source` and the hard
   dependency on `WorkflowRun.status.source`; the release snapshot inherits
   `source` for free and is already immutable.
4. **Lead Time stays accurate** — `authoredAt` is frozen into the immutable
   release copy, so squashes / branch moves can't corrupt it.
5. **No new credential surface for CI users** — they pass `authoredAt`
   themselves; OpenChoreo only does the git lookup for builds it owns.

---

### Net delta vs. the earlier CRD doc

| Earlier draft | Revised |
| --- | --- |
| `WorkflowRun.status.source` (new) | optional / drop — not the source of truth |
| `ComponentRelease.spec.source` (new, immutable + set-once `authoredAt`) | **removed** — covered by `spec.workload.source` |
| — | **`WorkloadTemplateSpec.source`** (new) — single field, flows into both Workload and the frozen ComponentRelease copy |

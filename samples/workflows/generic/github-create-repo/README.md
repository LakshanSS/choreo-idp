# GitHub Repository Creation — Generic Workflow Sample

This sample demonstrates a self-service Generic Workflow that creates a new GitHub repository under a specified organization via the GitHub API. Developers supply only the organization and repository name as parameters — the GitHub Personal Access Token (PAT) is read directly from a Kubernetes secret and is never exposed as a workflow parameter or visible in any WorkflowRun spec.

---

## Pipeline Overview

```
WorkflowRun
    │
    ▼
[validate-step] — checks secret exists, token is valid, scope is correct, org is accessible
    │
    ▼
[create-step]   — POST /orgs/{org}/repos via GitHub API (PAT from secret)
    │
    ▼
[report-step]   — prints the new repository's URL and clone addresses
```

## Files

| File | Kind | Description |
|------|------|-------------|
| `cluster-workflow-template-github-create-repo.yaml` | `ClusterWorkflowTemplate` | Argo Workflows template with the two execution steps |
| `workflow-github-create-repo.yaml` | `Workflow` | OpenChoreo CR — defines the parameter schema and references the template |
| `workflow-run-github-create-repo.yaml` | `WorkflowRun` | Triggers a run with specific parameter values |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `github.org` | _(required)_ | GitHub organization where the repository will be created |
| `github.repoName` | _(required)_ | Name of the new repository |
| `repo.description` | `""` | Short description of the repository |
| `repo.private` | `true` | Whether the repository should be private |
| `repo.autoInit` | `true` | Initialize the repository with an empty README |

## Secret Setup

The workflow reads the GitHub PAT from a Kubernetes secret named `github-credentials` with a key `pat`. This secret must be created in the build plane namespace **before** running the workflow. Developers who submit WorkflowRuns never see or interact with the token.

```bash
# Create the secret in the build plane namespace (one-time platform setup)
kubectl create secret generic github-credentials \
  --from-literal=pat=<your-github-pat> \
  -n openchoreo-ci-<your-namespace>
```

Replace `<your-namespace>` with the Kubernetes namespace where your WorkflowRun lives (e.g., `default` → `openchoreo-ci-default`).

The PAT requires the **`repo`** scope (or `public_repo` for public-only) to create repositories in an organization.

To update an existing secret:

```bash
kubectl create secret generic github-credentials \
  --from-literal=pat=<new-pat> \
  -n openchoreo-ci-<your-namespace> --dry-run=client -o yaml | kubectl apply -f -
```

### Error messages

The `validate` step runs before any repository is created and prints a clear error for each failure case:

| Failure | Log message |
|---------|-------------|
| Secret `github-credentials` missing | `ERROR: GitHub PAT is missing. The Kubernetes secret 'github-credentials' does not exist ...` |
| Token invalid / expired | `ERROR: GitHub token is invalid or expired (HTTP 401).` |
| Token missing `repo` scope | `ERROR: GitHub token is missing the required 'repo' scope. Current scopes: ...` |
| Owner not found | `ERROR: '<owner>' was not found as a GitHub organization or personal account.` |
| Personal account token mismatch | `ERROR: '<owner>' is a personal GitHub account but the token belongs to '<other-user>'.` |
| Repo already exists | `ERROR: Repository '<owner>/<repo>' already exists or the name is invalid.` |

> **Note:** `github.org` accepts both GitHub **organization** names and personal **account** usernames. The workflow automatically detects the owner type and uses the correct API endpoint (`/orgs/{owner}/repos` for organizations, `/user/repos` for personal accounts).

## How to Run

Deploy the resources in order:

```bash
# 1. Deploy the ClusterWorkflowTemplate to the Build Plane
kubectl apply -f cluster-workflow-template-github-create-repo.yaml

# 2. Deploy the Workflow CR to the Control Plane
kubectl apply -f workflow-github-create-repo.yaml

# 3. Trigger an execution by creating a WorkflowRun
kubectl apply -f workflow-run-github-create-repo.yaml
```

To create a different repository, supply your own values in the WorkflowRun:

```yaml
apiVersion: openchoreo.dev/v1alpha1
kind: WorkflowRun
metadata:
  name: create-my-service-repo
spec:
  workflow:
    name: github-create-repo
    parameters:
      github:
        org: "my-org"
        repoName: "payment-service"
      repo:
        description: "Payment microservice"
        private: true
        autoInit: true
```

## Example Output

```
=============================
  GitHub Repository Created
=============================
Name:          my-org/my-new-repo
URL:           https://github.com/my-org/my-new-repo
Clone (SSH):   git@github.com:my-org/my-new-repo.git
Clone (HTTPS): https://github.com/my-org/my-new-repo.git
Private:       true
Auto-init:     main
Created:       2026-03-06T10:00:00Z
=============================
```

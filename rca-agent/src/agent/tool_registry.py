# Copyright 2026 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0


class Tool(str):
    active_form: str | None
    server: str

    def __new__(cls, name: str, *, server: str, active_form: str | None = None):
        instance = super().__new__(cls, name)
        instance.active_form = active_form
        instance.server = server
        return instance


OBSERVABILITY = "observability"
OPENCHOREO = "openchoreo"


class TOOLS:
    GET_TRACES = Tool("get_traces", server=OBSERVABILITY, active_form="Retrieving traces...")
    GET_NAMESPACE_LOGS = Tool(
        "get_namespace_logs", server=OBSERVABILITY, active_form="Fetching namespace logs..."
    )
    GET_PROJECT_LOGS = Tool(
        "get_project_logs", server=OBSERVABILITY, active_form="Fetching project logs..."
    )
    GET_COMPONENT_LOGS = Tool(
        "get_component_logs", server=OBSERVABILITY, active_form="Fetching component logs..."
    )
    GET_COMPONENT_RESOURCE_METRICS = Tool(
        "get_component_resource_metrics",
        server=OBSERVABILITY,
        active_form="Gathering resource metrics...",
    )
    LIST_ENVIRONMENTS = Tool(
        "list_environments", server=OPENCHOREO, active_form="Loading environments..."
    )
    LIST_NAMESPACES = Tool(
        "list_namespaces", server=OPENCHOREO, active_form="Loading namespaces..."
    )
    LIST_PROJECTS = Tool("list_projects", server=OPENCHOREO, active_form="Loading projects...")
    LIST_COMPONENTS = Tool(
        "list_components", server=OPENCHOREO, active_form="Loading components..."
    )
    PATCH_RELEASEBINDING = Tool(
        "patch_releasebinding", server=OPENCHOREO, active_form="Patching release binding..."
    )
    GET_RESOURCE = Tool("get_resource", server=OPENCHOREO, active_form="Fetching resource...")
    GET_COMPONENT_RELEASE_SCHEMA = Tool(
        "get_component_release_schema",
        server=OPENCHOREO,
        active_form="Fetching release schema...",
    )
    CREATE_WORKLOAD = Tool("create_workload", server=OPENCHOREO, active_form="Creating workload...")
    GET_COMPONENT_WORKLOADS = Tool(
        "get_component_workloads",
        server=OPENCHOREO,
        active_form="Fetching component workloads...",
    )
    LIST_RELEASE_BINDINGS = Tool(
        "list_release_bindings",
        server=OPENCHOREO,
        active_form="Loading release bindings...",
    )
    LIST_COMPONENT_TRAITS = Tool(
        "list_component_traits",
        server=OPENCHOREO,
        active_form="Loading component traits...",
    )
    GET_TRAIT_SCHEMA = Tool(
        "get_trait_schema",
        server=OPENCHOREO,
        active_form="Fetching trait schema...",
    )


_ALL = [v for v in vars(TOOLS).values() if isinstance(v, Tool)]

# Tool names grouped by server
OBSERVABILITY_TOOLS = {t for t in _ALL if t.server == OBSERVABILITY}
OPENCHOREO_TOOLS = {t for t in _ALL if t.server == OPENCHOREO}

# Active forms for streaming UI
TOOL_ACTIVE_FORMS: dict[str, str] = {
    v: v.active_form
    for v in vars(TOOLS).values()
    if isinstance(v, Tool) and v.active_form is not None
}

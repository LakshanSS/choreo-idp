# Copyright 2025 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0


class OpenchoreoTools:
    LIST_ENVIRONMENTS = "list_environments"
    LIST_NAMESPACES = "list_namespaces"
    LIST_PROJECTS = "list_projects"
    LIST_COMPONENTS = "list_components"


class ObservabilityTools:
    GET_TRACES = "get_traces"
    GET_NAMESPACE_LOGS = "get_namespace_logs"
    GET_PROJECT_LOGS = "get_project_logs"
    GET_COMPONENT_LOGS = "get_component_logs"
    GET_COMPONENT_RESOURCE_METRICS = "get_component_resource_metrics"


obs_tools = ObservabilityTools()
oc_tools = OpenchoreoTools()

# Tool name sets for categorization
OBS_MCP_TOOLS = {
    obs_tools.GET_TRACES,
    obs_tools.GET_PROJECT_LOGS,
    obs_tools.GET_COMPONENT_LOGS,
    obs_tools.GET_COMPONENT_RESOURCE_METRICS,
}

OC_MCP_TOOLS = {
    oc_tools.LIST_ENVIRONMENTS,
    oc_tools.LIST_NAMESPACES,
    oc_tools.LIST_PROJECTS,
    oc_tools.LIST_COMPONENTS,
}


class OpenchoreoLabels:
    COMPONENT_UID = "openchoreo.dev/component-uid"
    COMPONENT_UIDS = "openchoreo.dev/component-uids"
    ENVIRONMENT_UID = "openchoreo.dev/environment-uid"
    PROJECT_UID = "openchoreo.dev/project-uid"


oc_labels = OpenchoreoLabels()

# Active forms for tool calls (present continuous descriptions for UI)
TOOL_ACTIVE_FORMS: dict[str, str] = {
    obs_tools.GET_TRACES: "Retrieving traces...",
    obs_tools.GET_COMPONENT_LOGS: "Fetching component logs...",
    obs_tools.GET_PROJECT_LOGS: "Fetching project logs...",
    obs_tools.GET_COMPONENT_RESOURCE_METRICS: "Gathering resource metrics...",
    oc_tools.LIST_ENVIRONMENTS: "Loading environments...",
    oc_tools.LIST_NAMESPACES: "Loading namespaces...",
    oc_tools.LIST_PROJECTS: "Loading projects...",
    oc_tools.LIST_COMPONENTS: "Loading components...",
}


class Templates:
    """Template path constants."""

    # Prompt templates
    RCA_AGENT_PROMPT = "prompts/rca_agent_prompt.j2"
    CHAT_AGENT_PROMPT = "prompts/chat_agent_prompt.j2"

    # Middleware templates
    COMPONENT_LOGS = "middleware/component_logs.j2"
    PROJECT_LOGS = "middleware/project_logs.j2"
    METRICS = "middleware/metrics.j2"
    TRACES = "middleware/traces.j2"

    # API templates
    RCA_REQUEST = "api/rca_request.j2"


# Tools available to the RCA agent (for /analyze)
RCA_AGENT_TOOLS = {
    obs_tools.GET_TRACES,
    obs_tools.GET_COMPONENT_LOGS,
    obs_tools.GET_PROJECT_LOGS,
    obs_tools.GET_COMPONENT_RESOURCE_METRICS,
    oc_tools.LIST_ENVIRONMENTS,
    oc_tools.LIST_NAMESPACES,
    oc_tools.LIST_PROJECTS,
    oc_tools.LIST_COMPONENTS,
}

# Tools available to the chat agent (for /chat)
CHAT_AGENT_TOOLS = {
    obs_tools.GET_TRACES,
    obs_tools.GET_COMPONENT_LOGS,
    obs_tools.GET_PROJECT_LOGS,
    obs_tools.GET_COMPONENT_RESOURCE_METRICS,
    oc_tools.LIST_ENVIRONMENTS,
    oc_tools.LIST_NAMESPACES,
    oc_tools.LIST_PROJECTS,
    oc_tools.LIST_COMPONENTS,
}

import json
from dataclasses import dataclass

import httpx

from src.auth.oauth_client import get_oauth2_auth


@dataclass
class AlertScope:
    project_uid: str
    project_name: str
    namespace_name: str
    environment_uid: str
    environment_name: str
    component_uid: str | None = None
    component_name: str | None = None


def _parse_mcp_response(content_blocks: list[dict], key: str) -> list[dict]:
    text = content_blocks[0]["text"]
    return json.loads(text)[key]


async def resolve_component_scope(
    component_uid: str, environment_uid: str, auth: httpx.Auth | None = None
) -> AlertScope:
    from src.clients import MCPClient

    mcp_client = MCPClient(auth=auth or get_oauth2_auth())
    all_tools = await mcp_client.get_tools()
    list_namespaces = next(t for t in all_tools if t.name == "list_namespaces")
    list_projects = next(t for t in all_tools if t.name == "list_projects")
    list_components = next(t for t in all_tools if t.name == "list_components")
    list_environments = next(t for t in all_tools if t.name == "list_environments")

    component_uid_str = str(component_uid)
    environment_uid_str = str(environment_uid)

    raw_namespaces = await list_namespaces.ainvoke({})
    namespaces = _parse_mcp_response(raw_namespaces, "namespaces")

    for ns in namespaces:
        raw_projects = await list_projects.ainvoke({"namespace_name": ns["name"]})
        projects = _parse_mcp_response(raw_projects, "projects")

        for project in projects:
            raw_components = await list_components.ainvoke(
                {
                    "namespace_name": ns["name"],
                    "project_name": project["name"],
                }
            )
            components = _parse_mcp_response(raw_components, "components")

            for component in components:
                if component["uid"] == component_uid_str:
                    raw_envs = await list_environments.ainvoke(
                        {
                            "namespace_name": ns["name"],
                        }
                    )
                    environments = _parse_mcp_response(raw_envs, "environments")
                    env_name = next(
                        (e["name"] for e in environments if e["uid"] == environment_uid_str),
                        None,
                    )
                    if env_name is None:
                        raise ValueError(f"Environment with UID '{environment_uid}' not found")

                    return AlertScope(
                        component_uid=component["uid"],
                        component_name=component["name"],
                        project_uid=project["uid"],
                        project_name=project["name"],
                        namespace_name=ns["name"],
                        environment_uid=environment_uid_str,
                        environment_name=env_name,
                    )

    raise ValueError(f"Component with UID '{component_uid}' not found")


async def resolve_project_scope(
    project_uid: str, environment_uid: str, auth: httpx.Auth | None = None
) -> AlertScope:
    from src.clients import MCPClient

    mcp_client = MCPClient(auth=auth or get_oauth2_auth())
    all_tools = await mcp_client.get_tools()
    list_namespaces = next(t for t in all_tools if t.name == "list_namespaces")
    list_projects = next(t for t in all_tools if t.name == "list_projects")
    list_environments = next(t for t in all_tools if t.name == "list_environments")

    project_uid_str = str(project_uid)
    environment_uid_str = str(environment_uid)

    raw_namespaces = await list_namespaces.ainvoke({})
    namespaces = _parse_mcp_response(raw_namespaces, "namespaces")

    for ns in namespaces:
        raw_projects = await list_projects.ainvoke({"namespace_name": ns["name"]})
        projects = _parse_mcp_response(raw_projects, "projects")

        for project in projects:
            if project["uid"] == project_uid_str:
                raw_envs = await list_environments.ainvoke({"namespace_name": ns["name"]})
                environments = _parse_mcp_response(raw_envs, "environments")
                env_name = next(
                    (e["name"] for e in environments if e["uid"] == environment_uid_str),
                    None,
                )
                if env_name is None:
                    raise ValueError(f"Environment with UID '{environment_uid}' not found")

                return AlertScope(
                    project_uid=project["uid"],
                    project_name=project["name"],
                    namespace_name=ns["name"],
                    environment_uid=environment_uid_str,
                    environment_name=env_name,
                )

    raise ValueError(f"Project with UID '{project_uid}' not found")

# Copyright 2026 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0

from enum import Enum

from langchain_core.tools import BaseTool

from src.constants import OBS_MCP_TOOLS, OC_MCP_TOOLS, Templates
from src.template_manager import render


class Agent(str, Enum):
    RCA = "rca"
    CHAT = "chat"


def _build_tool_context(tools: list[BaseTool]) -> dict:
    return {
        "observability_tools": [tool for tool in tools if tool.name in OBS_MCP_TOOLS],
        "openchoreo_tools": [tool for tool in tools if tool.name in OC_MCP_TOOLS],
    }


def get_prompt(agent: Agent, tools: list[BaseTool]) -> str:
    context = _build_tool_context(tools)

    if agent == Agent.RCA:
        return render(Templates.RCA_AGENT_PROMPT, context)
    elif agent == Agent.CHAT:
        return render(Templates.CHAT_AGENT_PROMPT, context)
    else:
        raise ValueError(f"Unknown agent type: {agent}")

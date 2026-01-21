# Copyright 2025 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0

from langchain_core.tools import BaseTool

from src.core.constants import OBS_MCP_TOOLS, OC_MCP_TOOLS
from src.core.template_manager import render


def _build_tool_context(tools: list[BaseTool]) -> dict:
    """Build context dictionary with categorized tools."""
    return {
        "observability_tools": [tool for tool in tools if tool.name in OBS_MCP_TOOLS],
        "openchoreo_tools": [tool for tool in tools if tool.name in OC_MCP_TOOLS],
    }


def get_system_prompt(tools: list[BaseTool]) -> str:
    """
    Generate the RCA agent system prompt based on available tools.

    Args:
        tools: List of available tools

    Returns:
        Rendered system prompt
    """
    return render("prompts/system_prompt.j2", _build_tool_context(tools))


def get_chat_prompt(tools: list[BaseTool]) -> str:
    """
    Generate the chat agent system prompt based on available tools.

    Args:
        tools: List of available tools

    Returns:
        Rendered system prompt
    """
    return render("prompts/chat_prompt.j2", _build_tool_context(tools))

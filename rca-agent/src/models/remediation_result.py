# Copyright 2025 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0

from enum import StrEnum

from pydantic import BaseModel, Field


class ActionStatus(StrEnum):
    UNCHANGED = "unchanged"
    REVISED = "revised"


class ResourceChange(BaseModel):
    """A specific change to make on an OpenChoreo resource"""

    resource: str = Field(
        ...,
        description="Resource kind and name (e.g. 'ReleaseBinding api-service-development')",
    )
    field_path: str = Field(
        ...,
        description=(
            "Field path to update"
            " (e.g. 'spec.workloadOverrides.container.env[name=POSTGRES_DSN].value')"
        ),
    )
    value: str = Field(..., description="Recommended value to set")


class RemediationAction(BaseModel):
    """A recommended action translated into how to do it in OpenChoreo"""

    description: str = Field(..., description="Description of the remediation action")
    rationale: str | None = Field(
        default=None,
        description="Why this action is recommended",
    )
    status: ActionStatus = Field(
        ...,
        description="'unchanged' if kept as-is, 'revised' if translated into how to do it in OpenChoreo",
    )
    changes: list[ResourceChange] = Field(
        default_factory=list,
        description="Specific resource changes to make. Empty when status is 'unchanged'",
    )


class RemediationResult(BaseModel):
    """Revised recommended actions from the remediation agent"""

    recommended_actions: list[RemediationAction] = Field(
        ...,
        description="Recommended actions to resolve the identified root causes",
    )

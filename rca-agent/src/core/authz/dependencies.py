# Copyright 2025 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request

from src.core.authn.dependencies import extract_bearer_token, require_authn
from src.core.authz.client import AuthzClient
from src.core.authz.models import (
    EvaluateRequest,
    Resource,
    ResourceHierarchy,
    SubjectContext,
)
from src.core.config import settings

logger = logging.getLogger(__name__)

_authz_client: AuthzClient | None = None


def get_authz_client() -> AuthzClient:
    global _authz_client
    if _authz_client is None:
        _authz_client = AuthzClient(
            base_url=settings.authz_service_url,
            timeout=settings.authz_timeout_seconds,
            disabled=not settings.authz_enabled,
            verify_ssl=not settings.tls_insecure_skip_verify,
        )
    return _authz_client


async def extract_request_body(request: Request) -> dict[str, Any]:
    if hasattr(request.state, "_parsed_body"):
        return request.state._parsed_body

    try:
        body = await request.json()
        request.state._parsed_body = body
        return body
    except Exception:
        return {}


class AuthorizationChecker:
    def __init__(self, action: str, resource_type: str):
        self.action = action
        self.resource_type = resource_type

    async def __call__(
        self,
        request: Request,
        subject: Annotated[SubjectContext | None, Depends(require_authn)],
    ) -> SubjectContext | None:
        # If authn returned None (JWT disabled for local dev), skip authz too
        if subject is None:
            return None

        client = get_authz_client()

        if client.disabled:
            logger.info("Authorization disabled, skipping authz check")
            return subject

        logger.info(
            "Authorization check: action=%s, resource_type=%s, subject_type=%s",
            self.action,
            self.resource_type,
            subject.type,
        )

        token = extract_bearer_token(request)

        body = await extract_request_body(request)
        hierarchy = self._extract_hierarchy(body)
        logger.debug(
            "Resource hierarchy: project=%s, component=%s",
            hierarchy.project,
            hierarchy.component,
        )

        authz_request = EvaluateRequest(
            subjectContext=subject,
            resource=Resource(
                type=self.resource_type,
                id="",
                hierarchy=hierarchy,
            ),
            action=self.action,
            context={},
        )

        decision = await client.evaluate(authz_request, token)
        logger.info("Authz decision: allowed=%s", decision.decision)

        if not decision.decision:
            logger.warning(
                "Access denied: action=%s, resource_type=%s",
                self.action,
                self.resource_type,
            )
            raise HTTPException(
                status_code=403,
                detail={"error": "FORBIDDEN", "message": "Access denied"},
            )

        logger.info("Authorization successful")
        return subject

    def _extract_hierarchy(self, body: dict[str, Any]) -> ResourceHierarchy:
        return ResourceHierarchy(
            project=body.get("projectUid"),
            component=body.get("componentUid"),
        )


require_chat_authz = AuthorizationChecker(action="rcareport:view", resource_type="rcareport")

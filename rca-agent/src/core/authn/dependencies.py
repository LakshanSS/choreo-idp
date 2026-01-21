# Copyright 2025 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Any

from fastapi import HTTPException, Request

from src.core.authn.jwt import DisabledJWTValidator, JWTValidationError, get_jwt_validator
from src.core.authz.models import SubjectContext
from src.core.config import settings

logger = logging.getLogger(__name__)


def extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


def extract_subject_context_from_claims(claims: dict[str, Any]) -> SubjectContext:
    # Service account: has client_id but no sub
    if "client_id" in claims and "sub" not in claims:
        subject_type = "service"
        entitlement_claim = "client_id"
        entitlement_values = [claims.get("client_id", "")]
    else:
        # Regular user
        subject_type = "user"
        if "groups" in claims:
            entitlement_claim = "groups"
            groups = claims.get("groups", [])
            entitlement_values = groups if isinstance(groups, list) else [groups]
        else:
            entitlement_claim = "sub"
            entitlement_values = [claims.get("sub", "")]

    return SubjectContext(
        type=subject_type,
        entitlementClaim=entitlement_claim,
        entitlementValues=entitlement_values,
    )


async def require_authn(request: Request) -> SubjectContext | None:
    # Allow bypass if JWT is explicitly disabled (for local development)
    if settings.jwt_disabled:
        logger.debug("JWT authentication disabled, skipping validation")
        return None

    validator = get_jwt_validator()

    if isinstance(validator, DisabledJWTValidator):
        # JWKS URL not configured but JWT not explicitly disabled
        logger.error("JWT authentication not configured - JWT_JWKS_URL is required")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AUTH_NOT_CONFIGURED",
                "message": "JWT authentication is not configured. Set JWT_JWKS_URL.",
            },
        )

    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": "MISSING_TOKEN", "message": "Authorization header required"},
        )

    try:
        claims = validator.validate(token)
        logger.debug("Authentication successful", extra={"sub": claims.get("sub")})
        return extract_subject_context_from_claims(claims)
    except JWTValidationError as e:
        logger.warning("JWT validation failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=401,
            detail={"error": "INVALID_TOKEN", "message": str(e)},
        )

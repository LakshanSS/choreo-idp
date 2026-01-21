# Copyright 2025 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from opensearchpy import AsyncOpenSearch
from opensearchpy.exceptions import OpenSearchException

from src.core.config import settings
from src.core.constants import oc_labels
from src.core.models.rca_report import RCAReport

logger = logging.getLogger(__name__)

# Default port for OpenSearch when not specified in URL
_DEFAULT_OPENSEARCH_PORT = 9200

# Module-level singleton
_client: AsyncOpenSearchClient | None = None


class AsyncOpenSearchClient:
    def __init__(self) -> None:
        self.client = self._create_client()
        self.index_prefix = "rca-reports"

    def _create_client(self) -> AsyncOpenSearch:
        url = settings.opensearch_address
        parsed = urlparse(url)

        use_ssl = parsed.scheme == "https"
        host = parsed.hostname or "localhost"
        port = parsed.port or _DEFAULT_OPENSEARCH_PORT

        return AsyncOpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=(settings.opensearch_username, settings.opensearch_password),
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
        )

    async def upsert_rca_report(
        self,
        report_id: str,
        alert_id: str,
        status: str = "pending",
        report: RCAReport | None = None,
        summary: str | None = None,
        timestamp: datetime | None = None,
        environment_uid: str | None = None,
        project_uid: str | None = None,
        component_uids: list[str] | None = None,
        version: int = 1,
    ) -> dict[str, Any]:
        doc_timestamp = timestamp or datetime.now(UTC)
        index_name = f"{self.index_prefix}-{doc_timestamp.strftime('%Y.%m')}"

        document = {
            "@timestamp": doc_timestamp.isoformat(),
            "reportId": report_id,
            "alertId": alert_id,
            "status": status,
            "version": version,
            "resource": {
                oc_labels.ENVIRONMENT_UID: environment_uid,
                oc_labels.PROJECT_UID: project_uid,
                oc_labels.COMPONENT_UIDS: component_uids,
            },
        }

        if report is not None:
            document["summary"] = report.summary
            document["report"] = report.model_dump()
        elif summary is not None:
            document["summary"] = summary

        try:
            response = await self.client.index(index=index_name, body=document, id=report_id)
            logger.info(
                f"Successfully upserted RCA report {report_id} to {index_name} with status={status}, version={version}"
            )
            return response
        except OpenSearchException as e:
            logger.error(f"Failed to upsert RCA report {report_id}: {e}")
            raise

    async def get_rca_report(
        self,
        report_id: str,
        version: int | None = None,
    ) -> dict[str, Any] | None:
        query: dict[str, Any] = {
            "query": {"bool": {"must": [{"term": {"reportId": report_id}}]}},
            "sort": [{"version": {"order": "desc"}}],
            "size": 1,
        }

        if version is not None:
            query["query"]["bool"]["must"].append({"term": {"version": version}})

        try:
            response = await self.client.search(
                index=f"{self.index_prefix}-*",
                body=query,
            )
            hits = response.get("hits", {}).get("hits", [])
            if hits:
                return hits[0]["_source"]
            return None
        except OpenSearchException as e:
            logger.error(f"Failed to fetch RCA report {report_id}: {e}")
            raise

    async def check_connection(self) -> bool:
        try:
            await self.client.info()
            return True
        except OpenSearchException as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            return False

    async def close(self) -> None:
        await self.client.close()


def get_opensearch_client() -> AsyncOpenSearchClient:
    global _client
    if _client is None:
        _client = AsyncOpenSearchClient()
    return _client

# Copyright 2026 The OpenChoreo Authors
# SPDX-License-Identifier: Apache-2.0

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from opensearchpy import AsyncOpenSearch
from opensearchpy.exceptions import OpenSearchException

from src.config import settings
from src.constants import oc_labels
from src.models.rca_report import RCAReport

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

    async def get_rca_reports_by_project(
        self,
        project_uid: str,
        environment_uid: str,
        start_time: str,
        end_time: str,
        component_uids: list[str] | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        must_clauses: list[dict[str, Any]] = [
            {"term": {f"resource.{oc_labels.PROJECT_UID}": project_uid}},
            {"term": {f"resource.{oc_labels.ENVIRONMENT_UID}": environment_uid}},
            {"range": {"@timestamp": {"gte": start_time, "lte": end_time}}},
        ]

        if status is not None:
            must_clauses.append({"term": {"status": status}})

        query: dict[str, Any] = {
            "size": limit,
            "query": {"bool": {"must": must_clauses}},
            "sort": [{"@timestamp": {"order": "desc"}}],
        }

        # Add component filter if specified
        if component_uids:
            query["query"]["bool"]["should"] = [
                {"terms": {f"resource.{oc_labels.COMPONENT_UIDS}": component_uids}}
            ]
            query["query"]["bool"]["minimum_should_match"] = 1

        try:
            response = await self.client.search(
                index=f"{self.index_prefix}-*",
                body=query,
            )

            hits = response.get("hits", {}).get("hits", [])
            took_ms = response.get("took", 0)
            total = response.get("hits", {}).get("total", {})
            total_count = total.get("value", 0) if isinstance(total, dict) else total

            reports = []
            for hit in hits:
                source = hit["_source"]
                resource = source.get("resource", {})
                reports.append(
                    {
                        "alertId": source.get("alertId"),
                        "projectUid": resource.get(oc_labels.PROJECT_UID),
                        "reportId": source.get("reportId"),
                        "timestamp": source.get("@timestamp"),
                        "summary": source.get("summary"),
                        "status": source.get("status"),
                    }
                )

            return {
                "reports": reports,
                "totalCount": total_count,
                "tookMs": took_ms,
            }
        except OpenSearchException as e:
            logger.error(f"Failed to fetch RCA reports for project {project_uid}: {e}")
            raise

    async def get_rca_report_by_alert(
        self,
        alert_id: str,
        version: int | None = None,
    ) -> dict[str, Any] | None:
        # First query: Get all versions for this alertId
        versions_query: dict[str, Any] = {
            "size": 0,
            "query": {"term": {"alertId": alert_id}},
            "aggs": {
                "versions": {"terms": {"field": "version", "order": {"_key": "desc"}, "size": 100}}
            },
        }

        try:
            versions_response = await self.client.search(
                index=f"{self.index_prefix}-*",
                body=versions_query,
            )
            buckets = (
                versions_response.get("aggregations", {}).get("versions", {}).get("buckets", [])
            )
            available_versions = [b["key"] for b in buckets]

            if not available_versions:
                return None

            # Second query: Get specific version or latest
            report_query: dict[str, Any] = {
                "query": {"bool": {"must": [{"term": {"alertId": alert_id}}]}},
                "sort": [{"version": {"order": "desc"}}],
                "size": 1,
            }

            if version is not None:
                report_query["query"]["bool"]["must"].append({"term": {"version": version}})

            response = await self.client.search(
                index=f"{self.index_prefix}-*",
                body=report_query,
            )

            hits = response.get("hits", {}).get("hits", [])
            if not hits:
                return None

            source = hits[0]["_source"]
            resource = source.get("resource", {})

            return {
                "alertId": source.get("alertId"),
                "projectUid": resource.get(oc_labels.PROJECT_UID),
                "reportVersion": source.get("version"),
                "reportId": source.get("reportId"),
                "timestamp": source.get("@timestamp"),
                "status": source.get("status"),
                "availableVersions": available_versions,
                "report": source.get("report"),
            }
        except OpenSearchException as e:
            logger.error(f"Failed to fetch RCA report for alert {alert_id}: {e}")
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

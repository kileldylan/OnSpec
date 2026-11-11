"""Deterministic JSON behavior comparison and runtime evidence capture."""

from dataclasses import dataclass

import requests
from django.db import transaction

from Requora_backend.RequoraApp.models import Commit, Evidence


@dataclass(frozen=True)
class JsonProbeResult:
    status_code: int | None
    payload: object | None
    error: str = ""


def probe_json_endpoint(*, url, timeout=10, session=None):
    """Capture one JSON response without following unbounded redirects."""

    session = session or requests
    try:
        response = session.get(
            url,
            timeout=timeout,
            allow_redirects=False,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return JsonProbeResult(
            status_code=response.status_code,
            payload=response.json(),
        )
    except (requests.RequestException, ValueError) as error:
        return JsonProbeResult(status_code=None, payload=None, error=str(error))


def compare_json_snapshots(*, base, head):
    """Return a stable comparison of two JSON-compatible response snapshots."""

    changed_paths = []

    def compare(base_value, head_value, path="$"):
        if isinstance(base_value, dict) and isinstance(head_value, dict):
            for key in sorted(set(base_value) | set(head_value)):
                child_path = f"{path}.{key}"
                if key not in base_value or key not in head_value:
                    changed_paths.append(child_path)
                else:
                    compare(base_value[key], head_value[key], child_path)
            return
        if isinstance(base_value, list) and isinstance(head_value, list):
            if base_value != head_value:
                changed_paths.append(path)
            return
        if base_value != head_value:
            changed_paths.append(path)

    compare(base, head)
    return {
        "status": "unchanged" if not changed_paths else "changed",
        "changed_paths": changed_paths,
    }


@transaction.atomic
def record_runtime_behavior_evidence(
    *,
    requirement,
    pull_request,
    endpoint,
    base_probe,
    head_probe,
):
    """Persist a base/head JSON comparison as runtime evidence."""

    commit = Commit.objects.filter(
        pull_request=pull_request,
        sha=pull_request.head_sha,
    ).first()
    comparison = {
        "base_status_code": base_probe.status_code,
        "head_status_code": head_probe.status_code,
        "base_error": base_probe.error,
        "head_error": head_probe.error,
    }
    if not base_probe.error and not head_probe.error:
        comparison.update(
            compare_json_snapshots(
                base=base_probe.payload,
                head=head_probe.payload,
            )
        )
    else:
        comparison["status"] = "unavailable"
        comparison["changed_paths"] = []

    evidence, _ = Evidence.objects.update_or_create(
        requirement=requirement,
        pull_request=pull_request,
        commit=commit,
        evidence_type="runtime",
        metadata__endpoint=endpoint,
        defaults={
            "status": "valid" if comparison["status"] != "unavailable" else "invalid",
            "description": (
                f"JSON behavior comparison for {endpoint}: "
                f"{comparison['status']}."
            ),
            "metadata": {
                "source": "requora",
                "endpoint": endpoint,
                "head_sha": pull_request.head_sha,
                "base_snapshot": base_probe.payload,
                "head_snapshot": head_probe.payload,
                **comparison,
            },
        },
    )
    return evidence

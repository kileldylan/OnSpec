from unittest.mock import Mock

from Requora_backend.integrations.verification.behavior import (
    JsonProbeResult,
    compare_json_snapshots,
    probe_json_endpoint,
)


def test_compare_json_snapshots_reports_nested_behavior_changes():
    result = compare_json_snapshots(
        base={"user": {"active": True, "role": "user"}},
        head={"user": {"active": False, "role": "user"}},
    )

    assert result == {
        "status": "changed",
        "changed_paths": ["$.user.active"],
    }


def test_compare_json_snapshots_accepts_equivalent_payloads():
    assert compare_json_snapshots(
        base={"ok": True, "items": [1, 2]},
        head={"ok": True, "items": [1, 2]},
    ) == {
        "status": "unchanged",
        "changed_paths": [],
    }


def test_probe_json_endpoint_is_bounded_and_json_only():
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"ok": True}
    response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = response

    result = probe_json_endpoint(
        url="http://head.test/health",
        timeout=3,
        session=session,
    )

    assert result == JsonProbeResult(status_code=200, payload={"ok": True})
    session.get.assert_called_once_with(
        "http://head.test/health",
        timeout=3,
        allow_redirects=False,
        headers={"Accept": "application/json"},
    )

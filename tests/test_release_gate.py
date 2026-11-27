import json

import pytest
from fastapi.testclient import TestClient

import backend.app as bridge
from models.v2.model_runtime import CandidateModels


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(bridge, "SECRET", "phase-0.1-synthetic-secret")
    bridge.session_store.clear()
    with TestClient(bridge.app) as test_client:
        yield test_client
    bridge.session_store.clear()


@pytest.fixture
def pipeline(monkeypatch):
    def run_pipeline(entries, artifacts, secret, model, stage):
        artifacts.update(
            {
                "sanitized/synthetic.txt": b"synthetic sanitized content",
                "report.json": b"{}",
                "records.jsonl": (
                    b'{"file":"sanitized/synthetic.txt","loc":"doc",'
                    b'"patient":"PSN-synthetic"}\n'
                ),
            }
        )
        return (
            {
                "counts": {"files_total": 1, "files_sanitized": 1, "files_quarantined": 0},
                "resources": {"peak_rss_mb": 1},
                "risk_proxy": {"profiles": 1},
            },
            [],
        )

    monkeypatch.setattr(bridge, "run_pipeline", run_pipeline)
    monkeypatch.setattr(
        bridge,
        "verify",
        lambda entries, artifacts, docs: {"approved": True, "contractValid": True, "findings": {}},
    )
    return run_pipeline


def assert_release_locked(client):
    requests = [
        ("get", "/api/release/files"),
        ("get", "/api/release/preview?path=sanitized/synthetic.txt"),
        ("get", "/api/release/download?path=sanitized/synthetic.txt"),
        ("get", "/api/release/artifact/archive"),
        ("get", "/api/release/artifact/report"),
        ("get", "/api/release/artifact/records"),
        ("get", "/api/release/identities"),
    ]
    for method, path in requests:
        response = getattr(client, method)(path)
        assert response.status_code == 409, path


def test_health_reports_cached_trained_model_readiness(client, monkeypatch):
    bridge.model_available.cache_clear()
    calls = []

    def available(required=True):
        calls.append(required)
        return object()

    monkeypatch.setattr(bridge, "load_model", available)
    try:
        first = client.get("/api/health")
        second = client.get("/api/health")

        assert first.status_code == second.status_code == 200
        assert first.json()["modelAvailable"] is True
        assert first.json()["modelFeatureVersion"] == "2.0"
        assert calls == [False]
    finally:
        bridge.model_available.cache_clear()


def test_health_reports_missing_trained_model(client, monkeypatch):
    bridge.model_available.cache_clear()
    monkeypatch.setattr(bridge, "load_model", lambda required=True: None)
    try:
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["modelAvailable"] is False
    finally:
        bridge.model_available.cache_clear()


def run_synthetic(client):
    client.get("/api/run")
    session = bridge.session_store.peek(client.cookies.get(bridge.SESSION_COOKIE))
    bridge.run([("synthetic.txt", b"synthetic input")], session)
    return json.loads(json.dumps(session.state))


def test_diagnostic_mode_with_installed_model_never_loads_or_releases(
    client, pipeline, monkeypatch
):
    CandidateModels()
    monkeypatch.setenv("SHEILD_RULES_DIAGNOSTIC", "1")

    def unexpected_load(*args, **kwargs):
        raise AssertionError("diagnostic mode attempted model initialization")

    monkeypatch.setattr(bridge, "load_model", unexpected_load)
    state = run_synthetic(client)

    assert state["status"] == "completed"
    assert state["modelActive"] is False
    assert state["releaseApproved"] is False
    assert_release_locked(client)


def test_diagnostic_mode_without_model_dependency_remains_locked(client, pipeline, monkeypatch):
    monkeypatch.setenv("SHEILD_RULES_DIAGNOSTIC", "1")
    monkeypatch.setattr(
        bridge, "load_model", lambda *args, **kwargs: pytest.fail("model loader must not run")
    )

    state = run_synthetic(client)

    assert state["status"] == "completed"
    assert state["modelActive"] is False
    assert state["releaseApproved"] is False
    assert_release_locked(client)


def test_normal_mode_with_installed_model_can_release(client, pipeline, monkeypatch):
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    models = CandidateModels()
    seen = []
    original_pipeline = bridge.run_pipeline

    def capture_model(entries, artifacts, secret, model, stage):
        seen.append(model)
        return original_pipeline(entries, artifacts, secret, model, stage)

    monkeypatch.setattr(bridge, "run_pipeline", capture_model)
    monkeypatch.setattr(bridge, "load_model", lambda required=True: models)
    state = run_synthetic(client)

    assert state["releaseApproved"] is True
    assert seen == [models]
    assert client.get("/api/release/files").status_code == 200
    assert client.get("/api/release/artifact/report").status_code == 200


def test_normal_mode_with_unavailable_model_fails_closed(client, pipeline, monkeypatch):
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    monkeypatch.setattr(
        bridge,
        "load_model",
        lambda required=True: (_ for _ in ()).throw(RuntimeError("model_unavailable")),
    )

    state = run_synthetic(client)

    assert state["status"] == "failed"
    assert state["failureCode"] == "MODEL_UNAVAILABLE"
    assert state["releaseApproved"] is False
    assert_release_locked(client)


def test_independent_verification_rejection_fails_closed(client, pipeline, monkeypatch):
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    monkeypatch.setattr(bridge, "load_model", lambda required=True: object())
    monkeypatch.setattr(
        bridge,
        "verify",
        lambda entries, artifacts, docs: {
            "approved": False,
            "contractValid": True,
            "findings": {"synthetic_rejection": 1},
        },
    )

    state = run_synthetic(client)

    assert state["releaseApproved"] is False
    assert state["stages"]["verification"] == "failed"
    assert_release_locked(client)


def test_independent_verification_exception_fails_closed(client, pipeline, monkeypatch):
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    monkeypatch.setattr(bridge, "load_model", lambda required=True: object())

    def fail_verification(entries, artifacts, docs):
        raise RuntimeError("synthetic verification exception")

    monkeypatch.setattr(bridge, "verify", fail_verification)
    state = run_synthetic(client)

    assert state["status"] == "failed"
    assert state["failureCode"] == "VERIFICATION_FAILED"
    assert state["releaseApproved"] is False
    assert_release_locked(client)


def test_failed_run_revokes_previously_approved_release(client, pipeline, monkeypatch):
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    monkeypatch.setattr(bridge, "load_model", lambda required=True: object())
    assert run_synthetic(client)["releaseApproved"] is True

    def fail_processing(*args, **kwargs):
        raise RuntimeError("synthetic processing exception")

    monkeypatch.setattr(bridge, "run_pipeline", fail_processing)
    state = run_synthetic(client)

    assert state["status"] == "failed"
    assert state["releaseApproved"] is False
    assert_release_locked(client)


def test_diagnostic_run_revokes_previously_approved_release(client, pipeline, monkeypatch):
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    monkeypatch.setattr(bridge, "load_model", lambda required=True: object())
    assert run_synthetic(client)["releaseApproved"] is True
    monkeypatch.setenv("SHEILD_RULES_DIAGNOSTIC", "1")
    monkeypatch.setattr(
        bridge, "load_model", lambda *args, **kwargs: pytest.fail("model loader must not run")
    )

    state = run_synthetic(client)

    assert state["status"] == "completed"
    assert state["releaseApproved"] is False
    assert_release_locked(client)

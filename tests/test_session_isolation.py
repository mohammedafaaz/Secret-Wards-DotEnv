import concurrent.futures
import threading
import time

from fastapi.testclient import TestClient

import backend.app as bridge


def _session(client):
    client.get("/api/run")
    return bridge.session_store.peek(client.cookies.get(bridge.SESSION_COOKIE))


def test_sessions_isolate_state_release_and_failed_upload(monkeypatch):
    bridge.session_store.clear()
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    monkeypatch.setattr(bridge, "load_model", lambda required=True: object())

    def pipeline(entries, artifacts, secret, model, stage):
        artifacts.update({
            "sanitized/private.txt": b"client A sanitized output",
            "report.json": b"{}",
            "records.jsonl": b'{"file":"sanitized/private.txt","loc":"doc","patient":"PSN-A"}\n',
        })
        return (
            {"counts": {"files_total": 1}, "resources": {"peak_rss_mb": 1},
             "risk_proxy": {"profiles": 1}},
            [],
        )

    monkeypatch.setattr(bridge, "run_pipeline", pipeline)
    monkeypatch.setattr(
        bridge, "verify",
        lambda entries, artifacts, docs: {"approved": True, "contractValid": True, "findings": {}},
    )
    with TestClient(bridge.app) as first, TestClient(bridge.app) as second:
        first_session = _session(first)
        bridge.run([("private.txt", b"private input")], first_session)
        first_state = first.get("/api/run").json()
        assert first_state["releaseApproved"] is True
        assert "sessionId" not in first_state
        assert first.get("/api/release/artifact/report").content == b"{}"

        second_session = _session(second)
        assert first_session.identifier != second_session.identifier
        assert len(first_session.identifier) >= 40
        assert second.get("/api/run").json()["status"] == "idle"
        protected_paths = (
            "/api/release/files",
            "/api/release/preview?path=sanitized/private.txt",
            "/api/release/download?path=sanitized/private.txt",
            "/api/release/artifact/archive",
            "/api/release/artifact/report",
            "/api/release/artifact/records",
            "/api/release/identities",
        )
        for path in protected_paths:
            assert second.get(path).status_code == 409, path
        assert second.post(
            "/api/run/upload",
            content=b"invalid multipart",
            headers={"content-type": "multipart/form-data; boundary=broken"},
        ).status_code == 400
        assert first.get("/api/run").json()["releaseApproved"] is True
        assert first.get("/api/release/preview?path=sanitized/private.txt").json()["text"] == "client A sanitized output"

        cookie = first.cookies.get(bridge.SESSION_COOKIE)
        assert cookie and len(cookie) >= 40
        set_cookie = first.get("/api/run").headers["set-cookie"].lower()
        assert "httponly" in set_cookie and "samesite=strict" in set_cookie and "path=/api" in set_cookie
    bridge.session_store.clear()


def test_invalid_and_expired_session_tokens_are_rejected():
    bridge.session_store.clear()
    with TestClient(bridge.app) as client:
        client.cookies.set(bridge.SESSION_COOKIE, "attacker-supplied-token", path="/api")
        assert client.get("/api/run").status_code == 401
        client.cookies.clear()
        session = _session(client)
        session.last_activity = time.monotonic() - bridge.SESSION_TTL_SECONDS - 1
        assert client.get("/api/run").status_code == 401
        assert bridge.session_store.peek(session.identifier) is None
    bridge.session_store.clear()


def test_session_bootstrap_recovers_stale_cookie_without_releasing_old_artifacts():
    bridge.session_store.clear()
    with TestClient(bridge.app) as client:
        assert client.get("/api/run").status_code == 200
        old_identifier = client.cookies.get(bridge.SESSION_COOKIE)
        old_session = bridge.session_store.peek(old_identifier)
        assert old_session is not None
        old_session.state.update(status="completed", releaseApproved=True)
        old_session.release["report.json"] = b"private report"

        client.cookies.clear()
        client.cookies.set(
            bridge.SESSION_COOKIE,
            "expired-session-token",
            domain="testserver.local",
            path="/api",
        )
        assert client.get("/api/run").status_code == 401
        initialized = client.post("/api/session")
        assert initialized.status_code == 200
        assert "sessionId" not in initialized.json()

        new_identifier = client.cookies.get(bridge.SESSION_COOKIE)
        new_session = bridge.session_store.peek(new_identifier)
        assert new_identifier != "expired-session-token"
        assert new_session is not None and new_session is not old_session
        assert client.get("/api/run").json()["status"] == "idle"
        assert client.get("/api/release/artifact/report").status_code == 409
        assert old_session.release["report.json"] == b"private report"
    bridge.session_store.clear()


def test_session_capacity_evicts_oldest_idle_session(monkeypatch):
    bridge.session_store.clear()
    monkeypatch.setattr(bridge, "MAX_SESSIONS", 1)
    with TestClient(bridge.app) as first, TestClient(bridge.app) as second:
        old_session = _session(first)
        assert second.get("/api/run").status_code == 200
        assert bridge.session_store.peek(old_session.identifier) is None
        assert first.get("/api/run").status_code == 401
    bridge.session_store.clear()


def test_oversized_release_is_not_retained(monkeypatch):
    bridge.session_store.clear()
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    monkeypatch.setattr(bridge, "load_model", lambda required=True: object())
    monkeypatch.setattr(bridge, "MAX_SESSION_OUTPUT_BYTES", 1)

    def pipeline(entries, artifacts, secret, model, stage):
        artifacts.update({
            "sanitized/private.txt": b"larger than cap",
            "report.json": b"{}",
            "records.jsonl": b'{"file":"sanitized/private.txt","loc":"doc","patient":"PSN-A"}\n',
        })
        return (
            {"counts": {"files_total": 1}, "resources": {"peak_rss_mb": 1},
             "risk_proxy": {"profiles": 1}},
            [],
        )

    monkeypatch.setattr(bridge, "run_pipeline", pipeline)
    monkeypatch.setattr(
        bridge, "verify",
        lambda entries, artifacts, docs: {"approved": True, "contractValid": True, "findings": {}},
    )
    with TestClient(bridge.app) as client:
        session = _session(client)
        bridge.run([("private.txt", b"private input")], session)
        assert session.state["status"] == "failed"
        assert session.state["releaseApproved"] is False
        assert session.release == {}
        assert client.get("/api/release/files").status_code == 409
    bridge.session_store.clear()


def test_concurrent_uploads_on_distinct_sessions_do_not_share_run_lock(monkeypatch):
    bridge.session_store.clear()
    monkeypatch.delenv("SHEILD_RULES_DIAGNOSTIC", raising=False)
    monkeypatch.setattr(bridge, "load_model", lambda required=True: object())
    rendezvous = threading.Barrier(2)

    def pipeline(entries, artifacts, secret, model, stage):
        rendezvous.wait(timeout=5)
        artifacts.update({
            "sanitized/" + entries[0][0]: b"independent output",
            "report.json": b"{}",
            "records.jsonl": b'{"file":"sanitized/note.txt","loc":"doc","patient":"PSN-X"}\n',
        })
        return (
            {"counts": {"files_total": 1}, "resources": {"peak_rss_mb": 1},
             "risk_proxy": {"profiles": 1}},
            [],
        )

    monkeypatch.setattr(bridge, "run_pipeline", pipeline)
    monkeypatch.setattr(
        bridge, "verify",
        lambda entries, artifacts, docs: {"approved": True, "contractValid": True, "findings": {}},
    )
    with TestClient(bridge.app) as first, TestClient(bridge.app) as second:
        _session(first)
        _session(second)

        def upload(client, label):
            return client.post(
                "/api/run/upload",
                files=[("files", ("note.txt", label.encode(), "text/plain"))],
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda pair: upload(*pair), [(first, "first"), (second, "second")]))
        assert [response.status_code for response in responses] == [200, 200]
        for client in (first, second):
            for _ in range(200):
                if client.get("/api/run").json()["status"] in ("completed", "failed"):
                    break
                time.sleep(0.01)
            assert client.get("/api/run").json()["releaseApproved"] is True
        assert first.get("/api/release/preview?path=sanitized/note.txt").status_code == 200
        assert second.get("/api/release/preview?path=sanitized/note.txt").status_code == 200
    bridge.session_store.clear()

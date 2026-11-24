"""/health answers GET and HEAD (uptime monitors), and the OpenAPI schema
builds without a duplicate operation id."""
from __future__ import annotations
import warnings

from fastapi.testclient import TestClient

import main


def test_health_answers_get_and_head():
    client = TestClient(main.app)
    assert client.get("/health").json() == {"status": "ok"}
    r = client.head("/health")
    assert r.status_code == 200
    assert r.content == b""


def test_the_schema_has_no_duplicate_operation_id(monkeypatch):
    monkeypatch.setattr(main.app, "openapi_schema", None)  # build it afresh
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        schema = main.app.openapi()
    assert [str(w.message) for w in caught if "Duplicate Operation ID" in str(w.message)] == []
    assert set(schema["paths"]["/health"]) == {"get"}

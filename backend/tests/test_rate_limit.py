"""Login rate limits: per client IP (spoof-resistant) and per account."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import main
import rate_limit
from rate_limit import client_ip
from tests.conftest import ANALYST_PASSWORD

PROXY_SEEN = "203.0.113.7"  # the address Render's proxy appends


def _request(xff: list[str] | None = None, peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", v.encode()) for v in (xff or [])]
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def _login(client, username, password, xff=None):
    headers = {"X-Forwarded-For": xff} if xff else {}
    return client.post("/auth/login", json={"username": username, "password": password}, headers=headers)


# ── client_ip ─────────────────────────────────────────────────

@pytest.mark.parametrize("spoofed", ["1.1.1.1", "8.8.8.8, 9.9.9.9", "not-an-ip", ""])
def test_spoofed_leftmost_entries_do_not_change_the_key(spoofed):
    header = f"{spoofed}, {PROXY_SEEN}" if spoofed else PROXY_SEEN
    assert client_ip(_request([header])) == PROXY_SEEN


def test_extra_client_sent_header_lines_do_not_change_the_key():
    # Client sends its own X-Forwarded-For line; the proxy's entry is still last.
    assert client_ip(_request(["6.6.6.6", PROXY_SEEN])) == PROXY_SEEN


def test_no_header_falls_back_to_socket_address():
    assert client_ip(_request()) == "10.0.0.1"


def test_hops_are_configurable(monkeypatch):
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 2)
    assert client_ip(_request(["6.6.6.6, 198.51.100.1, 203.0.113.7"])) == "198.51.100.1"


def test_fewer_entries_than_hops_falls_back_to_socket(monkeypatch):
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 2)
    assert client_ip(_request(["6.6.6.6"])) == "10.0.0.1"


def test_zero_hops_ignores_the_header(monkeypatch):
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 0)
    assert client_ip(_request([PROXY_SEEN])) == "10.0.0.1"


# ── per-IP limit, end to end ──────────────────────────────────

def test_rotating_a_spoofed_header_does_not_bypass_the_ip_limit():
    client = TestClient(main.app)
    codes = [
        _login(client, "mallory", "guess", xff=f"10.9.8.{i}, {PROXY_SEEN}").status_code
        for i in range(6)
    ]
    assert codes == [401] * 5 + [429]


def test_other_clients_are_not_affected_by_one_ip_limit():
    client = TestClient(main.app)
    for i in range(6):
        _login(client, "mallory", "guess", xff=f"198.51.100.{i}, {PROXY_SEEN}")
    assert _login(client, "alice", ANALYST_PASSWORD, xff="192.0.2.50").status_code == 200


# ── per-account limit ─────────────────────────────────────────

def test_distributed_brute_force_is_capped_per_account():
    """Every guess from a different IP: the IP limit never triggers, the account one does."""
    client = TestClient(main.app)
    for i in range(10):
        assert _login(client, "alice", f"guess-{i}", xff=f"192.0.2.{i}").status_code == 401
    # Locked now, even with the right password, from a fresh IP.
    assert _login(client, "alice", ANALYST_PASSWORD, xff="192.0.2.200").status_code == 429
    # Other accounts are unaffected.
    assert _login(client, "bob", ANALYST_PASSWORD, xff="192.0.2.201").status_code == 200


def test_successful_logins_do_not_count_toward_the_account_limit():
    client = TestClient(main.app)
    for i in range(12):
        assert _login(client, "alice", ANALYST_PASSWORD, xff=f"192.0.2.{i}").status_code == 200


def test_unknown_usernames_are_limited_like_real_ones():
    """Same 401-then-429 pattern, so the limit does not reveal which accounts exist."""
    client = TestClient(main.app)
    codes = [_login(client, "nobody", "x", xff=f"192.0.2.{i}").status_code for i in range(11)]
    assert codes == [401] * 10 + [429]


# ── demo mode: public demo accounts are exempt from the account lockout ──

@pytest.fixture
def demo_mode(monkeypatch):
    import store
    monkeypatch.setattr(store, "DEMO_MODE", True)


def test_demo_accounts_cannot_be_locked_out_in_demo_mode(demo_mode):
    """Their passwords are public: anyone could otherwise lock visitors out."""
    client = TestClient(main.app)
    for i in range(15):
        assert _login(client, "alice", f"guess-{i}", xff=f"192.0.2.{i}").status_code == 401
    assert _login(client, "alice", ANALYST_PASSWORD, xff="192.0.2.200").status_code == 200


def test_demo_accounts_keep_the_ip_limit_in_demo_mode(demo_mode):
    client = TestClient(main.app)
    codes = [_login(client, "alice", "guess", xff=PROXY_SEEN).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]


def test_real_accounts_keep_the_account_lockout_in_demo_mode(demo_mode, monkeypatch):
    import users
    monkeypatch.setitem(users._users, "carol", {
        "username": "carol", "display_name": "Carol", "role": "analyst",
        "password_hash": users.hash_password("carol-real-password"),
        "session_key": users.new_session_key(), "deleted_at": None,
    })
    client = TestClient(main.app)
    for i in range(10):
        assert _login(client, "carol", f"guess-{i}", xff=f"192.0.2.{i}").status_code == 401
    assert _login(client, "carol", "carol-real-password", xff="192.0.2.200").status_code == 429


# ── keyed limits never share counters ─────────────────────────

def test_login_and_case_limits_stay_independent_at_the_same_rate(monkeypatch):
    """Even with identical rates, each limit counts only its own hits."""
    from limits import parse_many
    same = parse_many("3/minute")
    monkeypatch.setattr(rate_limit.LOGIN_FAILURES_PER_USER, "items", same)
    monkeypatch.setattr(rate_limit.CASES_PER_USER, "items", same)

    for _ in range(3):
        rate_limit.LOGIN_FAILURES_PER_USER.hit("alice")
    assert rate_limit.LOGIN_FAILURES_PER_USER.exceeded("alice")
    assert not rate_limit.CASES_PER_USER.exceeded("alice")

    for _ in range(3):
        rate_limit.CASES_PER_USER.hit("bob")
    assert rate_limit.CASES_PER_USER.exceeded("bob")
    assert not rate_limit.LOGIN_FAILURES_PER_USER.exceeded("bob")


def test_limits_use_distinct_explicit_namespaces():
    assert rate_limit.LOGIN_FAILURES_PER_USER.namespace == "login-user"
    assert rate_limit.CASES_PER_USER.namespace == "case-user"


@pytest.mark.parametrize("namespace", ["login-user", "case-user", ""])
def test_reusing_or_omitting_a_namespace_is_refused(namespace):
    with pytest.raises(ValueError):
        rate_limit.KeyedLimit(namespace, "1/minute")

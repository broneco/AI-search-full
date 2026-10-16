"""The CLI authenticates through HTTP and never bypasses server-side permissions."""
import json

import httpx
import pytest

import ask


def test_token_is_sent_to_chat_endpoint(monkeypatch, capsys):
    monkeypatch.setenv("AI_SEARCH_TOKEN", "synthetic-token")
    requests = []
    def server(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer synthetic-token"
        assert request.url.path == "/api/chat"
        assert json.loads(request.content)["search_strategy"] == "keyword"
        return httpx.Response(200, json={"answer": "answer", "sources": [{"title": "fixture", "page_number": 1}]})
    assert ask.main(["--strategy=keyword", "question"], transport=httpx.MockTransport(server)) == 0
    output = capsys.readouterr().out
    assert "answer" in output and "fixture" in output
    assert "synthetic-token" not in output
    assert len(requests) == 1


def test_login_uses_password_prompt_and_server_token(monkeypatch):
    monkeypatch.delenv("AI_SEARCH_TOKEN", raising=False)
    monkeypatch.setattr(ask.getpass, "getpass", lambda prompt: "synthetic-password")
    paths = []
    def server(request):
        paths.append(request.url.path)
        if request.url.path == "/api/auth/login":
            assert json.loads(request.content)["password"] == "synthetic-password"
            return httpx.Response(200, json={"access_token": "new-token"})
        assert request.headers["Authorization"] == "Bearer new-token"
        return httpx.Response(200, json={"answer": "authorized", "sources": []})
    assert ask.main(["--email", "user@example.test", "question"], transport=httpx.MockTransport(server)) == 0
    assert paths == ["/api/auth/login", "/api/chat"]


def test_auth_failure_returns_nonzero_without_leaking_body(monkeypatch, capsys):
    monkeypatch.setenv("AI_SEARCH_TOKEN", "synthetic-token")
    assert ask.main(["question"], transport=httpx.MockTransport(
        lambda request: httpx.Response(401, json={"detail": "private-server-detail"}))) == 1
    output = capsys.readouterr()
    assert "401" in output.err
    assert "private-server-detail" not in output.err


@pytest.mark.parametrize("url", ["http://remote.example.test", "https://user:password@example.test", "https://example.test?token=x"])
def test_cli_rejects_insecure_or_credential_urls(url):
    with pytest.raises(SystemExit):
        ask.main(["--url", url, "question"])

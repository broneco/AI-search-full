"""Ask the running API using the same authentication and ACL checks as the UI."""
import argparse
import getpass
import os
import sys
from urllib.parse import urlsplit

import httpx


def main(argv=None, *, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*")
    parser.add_argument("--url", default=os.getenv("AI_SEARCH_API_URL", "http://localhost:8000"))
    parser.add_argument("--email", default=os.getenv("AI_SEARCH_EMAIL"))
    parser.add_argument("--strategy", choices=["hybrid", "vector", "keyword"], default="hybrid")
    parser.add_argument("--mode", choices=["flash", "thinking"], default="flash")
    args = parser.parse_args(argv)
    url = urlsplit(args.url)
    if url.username or url.password or url.query or url.fragment or not url.hostname:
        parser.error("Use a backend URL without credentials, query or fragment.")
    if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}):
        parser.error("Use HTTPS, or HTTP only for a loopback backend.")
    query = " ".join(args.query).strip() or input("Dotaz: ").strip()
    if not query:
        return 0
    try:
        with httpx.Client(base_url=args.url.rstrip("/") + "/", timeout=180, transport=transport) as client:
            token = os.getenv("AI_SEARCH_TOKEN")
            if not token:
                email = args.email or input("E-mail: ").strip()
                password = getpass.getpass("Heslo: ")
                login = client.post("api/auth/login", json={"email": email, "password": password})
                login.raise_for_status()
                token = login.json()["access_token"]
            response = client.post("api/chat", headers={"Authorization": "Bearer " + token}, json={
                "query": query, "mode": args.mode, "include_sources": True, "search_strategy": args.strategy})
            response.raise_for_status()
            body = response.json()
            print(body["answer"])
            for index, item in enumerate(body.get("sources") or [], 1):
                print(f"[{index}] {item['title']} (strana {item.get('page_number', '?')})")
        return 0
    except httpx.HTTPStatusError as error:
        print(f"API vratilo HTTP {error.response.status_code}. Over prihlaseni a serverove logy.", file=sys.stderr)
    except (httpx.HTTPError, ValueError, KeyError, EOFError):
        print("Dotaz se nepodarilo dokoncit. Over API URL, pripojeni a prihlaseni.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

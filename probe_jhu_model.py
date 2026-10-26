"""Synthetic Ollama probe, using a verified host VPN or explicit managed helper."""
import argparse
import getpass
import json
import os
import subprocess
import sys
import time
import asyncio

import httpx
from dotenv import dotenv_values


async def managed_probe(model: str) -> int:
    from app.providers.jhu_connection import embedding_connection, jhu_client, slots
    from app.core.model_config import ModelError
    if not slots.acquire(blocking=False):
        print('{"error":"model_busy"}')
        return 1
    try:
        connection = await embedding_connection()
        async with jhu_client(connection, httpx.Timeout(180, connect=10)) as client:
            for run in range(2):
                started = time.monotonic()
                response = await client.post(connection['endpoint'] + '/api/generate', json={
                    'model': model, 'prompt': 'Napiš jednu krátkou větu v češtině o studiu na vysoké škole.',
                    'stream': False, 'options': {'num_predict': 100}})
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or not isinstance(body.get('response'), str):
                    raise ModelError('jhu_probe_response_invalid', 'Invalid generation response.')
                if not body['response'].strip():
                    raise ModelError('jhu_probe_response_empty', 'Empty generation response.')
                if body.get('model', model) != model:
                    raise ModelError('jhu_probe_model_mismatch', 'Different generation model.')
                print(json.dumps(dict(run=run+1, model=model,
                    latency_ms=round(1000*(time.monotonic()-started)),
                    total_duration=body.get('total_duration'), load_duration=body.get('load_duration'),
                    response=body['response']), ensure_ascii=False))
        return 0
    except ModelError as exc:
        print(json.dumps({'error': exc.code}))
        return 1
    except httpx.HTTPStatusError as exc:
        print(json.dumps({'error': 'jhu_probe_request_rejected', 'status': exc.response.status_code}))
        return 1
    except httpx.TimeoutException:
        print('{"error":"jhu_probe_timeout"}')
        return 1
    except (httpx.HTTPError, ValueError, TypeError):
        print('{"error":"jhu_probe_failed"}')
        return 1
    finally:
        slots.release()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env.jhu-model")
    parser.add_argument("--model", default="qwen3.8:latest")
    parser.add_argument("--vpn-interface", default="OpenVPN")
    parser.add_argument("--save-env", action="store_true", help="Save a new Git-ignored private env after success")
    parser.add_argument("--managed", action="store_true", help="Use the running helper and Key Vault API credentials")
    parser.add_argument("--tenant", default="jhu")
    parser.add_argument("--vault", default="ju-ai-search-kv-prod")
    args = parser.parse_args()
    if args.managed:
        if args.save_env:
            parser.error('--managed cannot be combined with --save-env')
        from scripts.vpn_spike.runtime import configure_managed_environment
        configure_managed_environment(args.tenant, args.vault)
        return asyncio.run(managed_probe(args.model))
    values = {**dotenv_values(args.env_file), **os.environ}
    endpoint = values.get("JHU_LLM_ENDPOINT", "http://160.217.182.41:11434")
    if endpoint.startswith("http:"):
        from urllib.parse import urlsplit
        host = urlsplit(endpoint).hostname
        # Host is validated before being used as a PowerShell argument.
        import ipaddress
        ipaddress.ip_address(host)
        route = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
            f"(Find-NetRoute -RemoteIPAddress '{host}').InterfaceAlias | ConvertTo-Json"],
            capture_output=True, text=True, check=False)
        if route.returncode or args.vpn_interface.lower() not in route.stdout.lower():
            print("VPN route not verified. Connect JHU VPN and run in a terminal allowed to read routes.")
            return 2
    username = values.get("JHU_LLM_USERNAME") or input("JHU API username: ")
    password = values.get("JHU_LLM_PASSWORD") or getpass.getpass("JHU API password: ")
    try:
        with httpx.Client(timeout=httpx.Timeout(180, connect=10), trust_env=False,
                          auth=httpx.BasicAuth(username, password), follow_redirects=False) as client:
            for run in range(2):
                started = time.monotonic()
                response = client.post(endpoint.rstrip("/") + "/api/generate", json={
                    "model": args.model, "prompt": "Napiš jednu krátkou větu v češtině o studiu na vysoké škole.",
                    "stream": False,
                })
                if response.status_code != 200:
                    print(json.dumps({"run": run + 1, "status": response.status_code,
                        "result": "model unavailable" if response.status_code == 404 else "request rejected"}))
                    return 1
                body = response.json()
                if not isinstance(body.get("response"), str) or not body["response"].strip():
                    print("Invalid or empty generation response.")
                    return 1
                if body.get("model", args.model) != args.model:
                    print("Server returned a different model; verification rejected.")
                    return 1
                print(json.dumps({"run": run + 1, "model": body.get("model", args.model),
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "total_duration": body.get("total_duration"), "load_duration": body.get("load_duration"),
                    "response": body["response"]}, ensure_ascii=False))
    except (httpx.HTTPError, ValueError):
        print("JHU probe failed: connection, timeout or response format. Credentials were not logged.")
        return 1
    if args.save_env:
        from pathlib import Path
        target = Path(args.env_file)
        ignored = subprocess.run(["git", "check-ignore", "--quiet", "--", str(target)], check=False)
        if ignored.returncode or target.exists():
            print("Refusing to overwrite a file or save credentials outside a Git-ignored path.")
            return 2
        with target.open("x", encoding="utf-8") as stream:
            for key, value in dict(JHU_LLM_ENDPOINT=endpoint, JHU_LLM_USERNAME=username, JHU_LLM_PASSWORD=password,
                    JHU_LLM_VERIFIED_MODEL=args.model, JHU_LLM_ALLOW_HTTP=str(endpoint.startswith("http:")).lower()).items():
                stream.write(key + "=" + json.dumps(value) + "\n")
        print("Private Git-ignored env saved. No credentials were printed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

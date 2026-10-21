"""Local Windows guard for the explicitly selected unencrypted JHU HTTP endpoint."""
import ipaddress
import json
import subprocess

from app.core.model_config import ModelError


def verify_windows_vpn(host: str, interface: str) -> None:
    try:
        ipaddress.ip_address(host)
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
            f"(Find-NetRoute -RemoteIPAddress '{host}').InterfaceAlias | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10, check=False)
        aliases = json.loads(result.stdout)
        aliases = [aliases] if isinstance(aliases, str) else aliases
        if result.returncode or not aliases or not any(interface.casefold() in alias.casefold() for alias in aliases):
            raise ValueError("VPN route missing")
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        raise ModelError("model_vpn_required", "Připojte JHU VPN. Trasa k modelu nebyla ověřena.") from None

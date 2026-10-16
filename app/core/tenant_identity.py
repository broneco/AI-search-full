"""Configuration aliases must never change database tenant identities."""


def tenant_config_name(tenant_id: str) -> str:
    base = (tenant_id or "default").strip().lower().split("-")[0] or "default"
    return "jhu" if base == "ju" else base

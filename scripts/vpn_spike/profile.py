"""Strict input policy for the isolated JHU probe; never execute supplied hooks."""
import shlex


# Intentionally limited to the supplied profile, not a general OpenVPN importer.
ALLOWED = {
    "client": (0, 0), "dev": (1, 1), "proto": (1, 1), "remote": (2, 2),
    "resolv-retry": (1, 1), "nobind": (0, 0), "persist-key": (0, 0),
    "persist-tun": (0, 0), "mute-replay-warnings": (0, 0),
    "comp-lzo": (0, 1), "verb": (1, 1), "auth-user-pass": (0, 0),
    "auth-nocache": (0, 0), "verify-x509-name": (1, 2), "reneg-sec": (1, 1),
    "remote-cert-tls": (1, 1), "auth": (1, 1), "cipher": (1, 1),
    "data-ciphers": (1, 1), "tls-version-min": (1, 1),
}


def validated_profile(source: str) -> str:
    if len(source) > 128_000 or "\x00" in source:
        raise ValueError("Invalid profile size/content")
    lines, seen, in_ca, ca_count = [], set(), False, 0
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line == "<ca>" and not in_ca:
            ca_count += 1
            in_ca = True
            lines.append(line)
            continue
        if in_ca:
            lines.append(line)
            if line == "</ca>":
                in_ca = False
            elif not (line in {"-----BEGIN CERTIFICATE-----", "-----END CERTIFICATE-----"}
                      or (line and all(c.isalnum() or c in "+/=" for c in line))):
                raise ValueError("Invalid inline CA")
            continue
        args = shlex.split(line, comments=True)
        if not args or args[0] not in ALLOWED:
            raise ValueError("Unsupported profile directive")
        low, high = ALLOWED[args[0]]
        if not low <= len(args) - 1 <= high or any(not part for part in args):
            raise ValueError("Unsupported directive arguments")
        if args[0] in seen and args[0] != "verb":
            raise ValueError("Duplicate profile directive")
        seen.add(args[0])
        if args[0] == "dev" and args[1] != "tun":
            raise ValueError("Only tun supported")
        if args[0] == "proto" and args[1] not in {"udp", "udp4"}:
            raise ValueError("Only UDP profile supported")
        if args[0] == "remote-cert-tls" and args[1] != "server":
            raise ValueError("Server certificate required")
        if args[0] == "verify-x509-name" and len(args) == 3 and args[2] == "name-prefix":
            raise ValueError("Exact server identity required")
        if args[0] == "auth-user-pass":
            lines.append("auth-user-pass /run/probe/auth")
        elif args[0] not in {"verb", "persist-tun"}:
            lines.append(line)
    if in_ca or ca_count != 1 or not {"client", "dev", "proto", "remote", "auth-user-pass",
                                            "verify-x509-name", "auth-nocache"} <= seen:
        raise ValueError("Incomplete verified client profile")
    # Recreate the userspace stack after reconnect; retaining its old address/FD
    # with persist-tun caused post-reconnect API timeouts in the live spike.
    # Preserve comp-lzo and certificate verification; override only local I/O.
    lines += ["dev-node unix:/opt/probe/bridge.py", "disable-dco", "script-security 2",
              "tmp-dir /run/probe",
              "route-noexec", "ifconfig-noexec", "auth-retry none", "connect-retry-max 1",
              "verb 3", "tls-exit"]
    return "\n".join(lines) + "\n"


def failure_code(line: str) -> str | None:
    """Discard raw peer/client log text and expose only fixed diagnostic codes."""
    for marker, code in [('AUTH_FAILED', 'vpn_auth_failed'),
                         ('VERIFY ERROR', 'vpn_certificate_failed'),
                         ('VERIFY X509NAME ERROR', 'vpn_certificate_failed'),
                         ('Options error:', 'vpn_options_failed'),
                         ('TLS Error:', 'vpn_tls_failed')]:
        if marker in line:
            return code
    return None

#!/usr/local/bin/python
"""Map OpenVPN's documented AF_UNIX environment to a fixed tunsocks forward.

No VPN/crypto implementation, shell, system interface, DNS or host-IP fallback.
"""
import ipaddress
import os


def bridge_command(env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    if env.get("TUNTAP_DEV_TYPE") != "tun":
        raise ValueError("Only a tun packet stream is supported")
    fd = int(env["TUNTAP_SOCKET_FD"])
    if fd < 3:
        raise ValueError("Invalid packet descriptor")
    address = str(ipaddress.IPv4Address(env["ifconfig_local"]))
    # Point-to-point OpenVPN may provide a peer instead of a subnet mask.
    # All destinations in this isolated stack go through the inherited VPN fd.
    target = str(ipaddress.IPv4Address(env["PROBE_TARGET_IP"]))
    port = int(env["PROBE_TARGET_PORT"])
    if not 1 <= port <= 65535:
        raise ValueError("Invalid target port")
    return ["/usr/local/bin/tunsocks", "-L", f"127.0.0.1:18080:{target}:{port}"], {
        "PATH": "/usr/local/bin:/usr/bin:/bin", "VPNFD": str(fd),
        "INTERNAL_IP4_ADDRESS": address, "INTERNAL_IP4_NETMASK": "0.0.0.0",
        "INTERNAL_IP4_MTU": str(min(1400, int(env.get("TUNTAP_MTU", "1400")))),
    }


if __name__ == "__main__":
    command, environment = bridge_command(dict(os.environ))
    os.execve(command[0], command, environment)

# Pinned userspace VPN runtime: probe, local helper and ACA sidecar.
FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential autoconf automake libtool pkg-config git ca-certificates \
    libssl-dev liblzo2-dev liblz4-dev libcap-ng-dev libevent-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone https://github.com/OpenVPN/openvpn.git openvpn \
    && cd openvpn && git checkout dc1f569087135894ac2703aeabd7a960ee9452d4 \
    && autoreconf -vi && ./configure --disable-dco --disable-plugin-auth-pam \
       --disable-pkcs11 --disable-systemd --disable-unit-tests --disable-debug \
    && make -j2 && install -D src/openvpn/openvpn /usr/local/sbin/openvpn
RUN git clone https://github.com/russdill/tunsocks.git tunsocks \
    && cd tunsocks && git checkout 4e4ff8682053412145930b8daf2c55d357cf1e44 \
    && git submodule init \
    && git config submodule.lwip.url https://github.com/lwip-tcpip/lwip.git \
    && git submodule update --init \
    && autoreconf -vi && ./configure --disable-pcap && make -j2 && make install

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 liblzo2-2 liblz4-1 libcap-ng0 libevent-2.1-7 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/sbin/openvpn /usr/local/sbin/openvpn
COPY --from=build /usr/local/bin/tunsocks /usr/local/bin/tunsocks
COPY --from=build /src/openvpn/COPYRIGHT.GPL /usr/local/share/licenses/openvpn/COPYRIGHT.GPL
COPY --from=build /src/tunsocks/lwip/COPYING /usr/local/share/licenses/tunsocks/COPYING
COPY --from=build /src/tunsocks/README.md /usr/local/share/licenses/tunsocks/README.md
RUN pip install --no-cache-dir azure-identity==1.26.0 azure-keyvault-secrets==4.11.3
COPY bridge.py profile.py container_probe.py service.py lifecycle.py gateway.py cloud.py /opt/probe/
RUN chmod 755 /opt/probe/bridge.py \
    && mkdir -p /run/probe && chown 65532:65532 /run/probe && chmod 700 /run/probe
USER 65532:65532
ENTRYPOINT ["python", "-u", "/opt/probe/container_probe.py"]

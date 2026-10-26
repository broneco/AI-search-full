# Živá odolnost JHU helperu

`tests/test_jhu_resilience_live.py` vyžaduje `RUN_JHU_RESILIENCE_TESTS=1`; jinak se přeskočí. Vyžaduje skutečný Docker, stávající KV Get a externí profil. Test zakládá a odstraňuje jen vlastní helper; jiné spravované relace odmítne. API prompty jsou syntetické a SQL ani aplikační dokumenty se nepoužívají.

Fault je injektovaný až po odeslání skutečného generate. Test ověří jeden forwarded request, řízené selhání, 429 pro souběžnou variantu, automatický reconnect a úspěch následující nové otázky. Dále nahradí helper a prokáže nutnost i úspěch explicitního snapshot refresh. Rotace nové hodnoty secrets je mockovaná v status testech; živý test žádnou novou KV verzi nevytváří.

Samostatný `RUN_JHU_DOCKER_RESTART_TESTS=1` restartuje celý Rancher a přeruší ostatní kontejnery; vyžaduje souhlas uživatele. Bez této druhé volby se neprovede. V testovém odvozeném tmpfs profilu je reneg-sec30, CA a serverová identita se zachovají. Soak120–3600s musí ve stejné VPN generation pozorovat nové skutečné TLS control channel události a funkční tags API. Měření cgroup paměti/CPU patří pouze helperu a zahrnuje sampling; není benchmarkem aplikace/ACA ani důkazem dnů provozu.

Postup: [provozní návod](../development/jhu-connection-resilience.md). Test neprovádí reset WSL, mazání volumes, Azure writes ani automatické opakování modelové generace.

Při dokončení soak vypíše chráněné čítače obnovy podle pevných kódů (např. vpn_tls_failed nebo vpn_upstream_unavailable), aby nečekaný reconnect nebyl skrytý úspěchem pozdějšího dotazu. Diagnostika neúspěšné generace vypíše jen HTTP status, délku pole response a allowlist done_reason; nikdy text odpovědi, prompt ani raw serverovou chybu.

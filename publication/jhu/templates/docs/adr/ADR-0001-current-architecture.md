# ADR-0001: Výchozí architektura JHU

Status: accepted for this repository baseline.

Cloudové měnitelné RAG/search/classification nastavení ukládat do SQL `tenant_settings`, přesně podle datového tenantu. Bundled JSON jsou pouze celosouborové defaults při chybějícím řádku. Startup nepřepisuje hodnoty ani nevytváří cloudovou tabulku; první převod je explicitní guarded insert-only import. Lokální/testovací overlaye zůstávají. [Aktualizace a rollback](../development/non-destructive-updates.md).

Cloudové JHU připojení má explicitní Linux ACA sidecar režim se systémovou managed identity, privátní gateway ve stejné replice a kontrolou přesného runtime kontextu. Lokální managed guard zůstává local/test. Kapacita, VPN session policy, secrets a migrace vyžadují schválený cloudový plán; zdrojová podpora není důkaz živé cloudové akceptace. [Cloudový runbook](../development/jhu-sidecar-azure.md).

Používat současnou Azure SQL/Blob/Azure OpenAI architekturu s explicitními provider rozhraními, profilovými indexy a tenant/ACL prefiltry před top K. Výchozí exact a volitelné ověřené ANN sdílejí profil a oprávnění. Lokální vývoj používá SQL Server Developer v Dockeru a stále vyžaduje síťové modelové připojení.

Přesná datová identita se nesmí zkracovat podle konfiguračního aliasu. Změna embeddingového prostoru vytvoří nový profil. Změna odpovědního LLM sama nevyžaduje nový embedding; změna chunk textu ano. Údržba nesmí předmazat korpus před přípravou náhradních embeddingů.

Git historie tohoto repozitáře sleduje pouze jeho předané snapshoty a následnou práci. Další zdůvodnění a limity jsou v [aktuální architektuře](../architecture/search.md).

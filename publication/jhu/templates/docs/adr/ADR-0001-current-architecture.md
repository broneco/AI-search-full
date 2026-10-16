# ADR-0001: Výchozí architektura JHU

Status: accepted for this repository baseline.

Používat současnou Azure SQL/Blob/Azure OpenAI architekturu s explicitními provider rozhraními, profilovými indexy a tenant/ACL prefiltry před top K. Výchozí exact a volitelné ověřené ANN sdílejí profil a oprávnění. Lokální vývoj používá SQL Server Developer v Dockeru a stále vyžaduje síťové modelové připojení.

Přesná datová identita se nesmí zkracovat podle konfiguračního aliasu. Změna embeddingového prostoru vytvoří nový profil. Změna odpovědního LLM sama nevyžaduje nový embedding; změna chunk textu ano. Údržba nesmí předmazat korpus před přípravou náhradních embeddingů.

Git historie tohoto repozitáře sleduje pouze jeho předané snapshoty a následnou práci. Další zdůvodnění a limity jsou v [aktuální architektuře](../architecture/search.md).

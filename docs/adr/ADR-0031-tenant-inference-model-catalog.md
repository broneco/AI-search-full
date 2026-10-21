# ADR-0031: Tenantový katalog inferenčních modelů

Stav: přijato pro implementaci. Datum: 2026-10-16.

## Rozhodnutí

LLM identitu oddělujeme od flash/thinking režimu a od embeddingového prostoru. Veřejný verzovaný JSON určuje profily, účely a defaults, prostředí určuje připojení. Katalog má existující file-level fallback, nikoli implicitní merge.

Factory vytváří instanci svázanou s jedním profilem. Chat a zpracování dokumentů předávají explicitní profil. Azure a JHU Ollama generate jsou skutečné implementace společného LLM rozhraní; JHU request contract se nemění. Selhání nikdy nevyvolá implicitní změnu modelu ani poskytovatele.

Pravidla model × skupina jsou tenantová SQL data s optimistickou revizí; metadata a secrets katalogu se přes UI neupravují. Chybějící pravidlo znamená přístup všech, prázdný seznam nikoho. Modelové volání revaliduje aktuální serverovou identitu. API uživatel nevybírá URL nebo credentials.

Generace ukládá provenance do existujícího JSON chatových zpráv a dokumentových metadat. Novou tabulku vyžadují jen runtime oprávnění. Staré zprávy ani embeddingy nepřeznačujeme.

## Důsledky

Lze porovnat více odpovědních modelů nad stejným indexem. Změna shrnutí v explicitní reindexaci nadále mění vstup embeddingů. Lokální odpovědní LLM nezaručuje plně lokální RAG. Připojení JHU z Azure potřebuje samostatné ověření sítě; vývojářská OpenVPN není cloudová konektivita.

Podrobný postup a ověření: [roadmap](../architecture/model-catalog-roadmap.md), [lokální návod](../development/model-selection.md).

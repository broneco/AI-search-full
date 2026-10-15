# ADR-0019: Embeddingové profily a centrální výběr providerů

- **Status:** Accepted
- **Datum:** 2026-10-12
- **Autor:** AI Search Implementation Team
- **Supersedes:** —
- **Superseded by:** —

## Kontext a problém

Aplikace vytváří Azure OpenAI embedding a LLM providery přímo v API routách a ingestaci. Rozměr embeddingu je pevně nastaven na 1536. To komplikuje budoucí výměnu providerů a nedává aplikaci identitu, podle které by bezpečně rozlišila dva vektorové prostory. Shodný počet rozměrů nezaručuje srovnatelné embeddingy.

Budoucí provoz počítá s porovnáním více embeddingových modelů a s lokálními providery. Aktuální implementační slice však zachovává stávající Azure model a nesahá na databázové schéma.

## Rozhodnutí

- Zavést neměnný `EmbeddingProfile`, který popisuje model a deklarovanou revizi, rozměry, normalizaci a verzované zpracování vstupů pro dotazy i dokumenty.
- Odvozovat stabilní `profile_id` ze všech vlastností měnících význam vektoru. Endpoint, klíč a deployment providera zůstávají konfigurační vazbou, nikoli identitou vektorového prostoru.
- Zvolit embedding a LLM providery v jedné factory vrstvě; API a orchestrace ingestace nemají vytvářet konkrétní implementaci přímo.
- Zachovat Azure OpenAI jako jedinou registrovanou implementaci tohoto slice. Neznámý provider selže s jasnou chybou; nevytváří se prázdná lokální implementace.
- Oddělit `embed_query` a `embed_documents`, protože model může pro oba typy textu vyžadovat jiné zpracování.
- Ověřit počet a konečnost prvků v každém vráceném vektoru a počet embeddingů proti počtu vstupů.

## Zvažované možnosti

### Vložený profil a konkrétní providery v každém volajícím modulu

Výhody:

- Bez nové centrální vrstvy.

Nevýhody:

- Opakované výběry providerů a obtížně testovatelná vazba na Azure napříč chatem a ingestací.

### Neměnný profil a centrální factory

Výhody:

- Jednotná identita embeddingů, konfigurace rozměrů a výběr implementace.
- Budoucí lokální adaptér může zapadnout do existujících rozhraní bez změn v API a vyhledávací orchestraci.

Nevýhody:

- Faktická provenance historických embeddingů vyžaduje pozdější databázovou migraci a ověření dat.

## Důsledky

### Pozitivní

- Dva modely se stejným rozměrem dostanou odlišné profily, pokud se liší jejich deklarovaná identita nebo zpracování textu.
- Vektor s chybným rozměrem či neplatnou hodnotou se odmítne před uložením nebo použitím.
- Výchozí profil zůstává Azure OpenAI, model `text-embedding-3-large`, revize `1`, 1536 rozměrů a nezměněný textový vstup.

### Náklady a omezení

- Správce musí zvýšit `AZURE_OPENAI_EMBEDDING_MODEL_REVISION`, pokud přesměruje Azure deployment na jiné parametry modelu. Aplikace sama neověřuje verzi modelu uloženou v Azure.
- Tento slice neukládá profil k historickým databázovým embeddingům a neaktivuje další index. To patří do následné databázové migrace.
- Lokální provider zatím není registrován. Přidá se až s konkrétní implementací a ověřením provozního umístění.

## Implementační poznámky

- `EmbeddingProfile.profile_id` je SHA-256 fingerprint kanonické reprezentace profilu.
- Konfigurační prefixy dotazu a dokumentu mají prázdnou výchozí hodnotu, takže současné požadavky modelu zůstávají stejné.
- Provider factory přijímá explicitní název pro testovatelnost a jinak čte typ providera z nastavení.
- Slice 2 nejprve opraví SQL prefiltry a oprávnění. Slice 3 následně uloží identitu profilu a revizi vstupu spolu s nativními vektory Azure SQL. Historické JSON embeddingy bez ověřené identity se nesmí automaticky přiřadit novému profilu. Úplné pořadí, stav a podmínky dokončení zachycuje [schválený plán sliců](../architecture/azure-sql-search-roadmap.md).

## Následné kroky

- [ ] Přidat profilovou provenance a nativní přesné hledání v samostatném Azure SQL slice.
- [ ] Registrovat lokální provider až po výběru konkrétní implementace a modelové služby.

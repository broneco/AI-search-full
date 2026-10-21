# Načítání JHU modelů a další selectors

## Implementovaný slice 1: přehled služby

V administraci přihlas účet se serverovou skupinou `Management`, přejdi do záložky **Modely a vyhledávání** a v sekci **Dostupné modely a oprávnění** otevři **Modely dostupné na JHU API**. Při prvním otevření se načtou metadata; tlačítko **Obnovit z API** provede nové načtení. Vyžaduje běžící aktualizovaný backend, stávající privátní JHU připojení a při lokálním HTTP testu ověřenou VPN. Na každou uživatelskou otázku se katalog znovu nenačítá.

Autentizovaný `GET /api/models/discovery` načítá `GET /api/tags` a omezeně souběžné `POST /api/show`. Neposílá dokumenty, negeneruje odpovědi/embeddingy, nestahuje modely a nemění katalogy, ACL ani indexy. Nalezený model není automaticky povolený. UI rozlišuje schopnosti, rozměry skutečných embeddingových modelů, kontext, parametry/kvantizaci, velikost souboru a již nakonfigurované profily. Velikost souboru není odhad nutné RAM/VRAM ani rychlosti.

Vrací se jen whitelist metadat; nikoli system prompt, template, license text, serverové cesty, URL či credentials. Poškozená metadata jednotlivého modelu jej označí jako neověřený. Nedostupný seznam, duplicity, neplatné identity a překročený limit 200 modelů jsou řízená chyba bez automatického retry. Celkový scan má limit 60 s, jednotlivý request 15 s a nejvýše 3 souběžné metadata requesty. Jeden scan na backendový proces; repliky tento limit nesdílí.

Endpoint je pouze pro Management tenanta s nakonfigurovaným JHU providerem. Konfigurační alias `ju-prod → jhu` nemění datovou/tokenovou identitu. Privátní `.env.jhu-model` se nevydává do ZIPu ani image. Modely Azure se přes JHU API neobjeví; jejich dosavadní konfigurace zůstává.

## Skutečně zjištěný inventář 2026-10-20

| Účel podle metadat | Modely |
|---|---|
| Kandidáti pro textový chat (13) | `qwen:latest`, `qwen3.8:latest`, `bbm-rag:latest`, `gemma4:e4b`, `gemma3:4b`, `qwen3:32b`, `llama3.2:3b`, `qwen2.5:32b`, `llama3.1:8b`, `qwen2.5:14b`, `gpt-oss:120b`, `gpt-oss-safe:latest`, `gpt-oss:20b` |
| Embeddingy (2) | `nomic-embed-text:latest`: 768 rozměrů, metadata kontext 2048; `mxbai-embed-large:latest`: 1024 rozměrů, kontext 512 |
| Rerankery (2) | `qllama/bge-reranker-v2-m3:latest`, `qllama/bge-reranker-v2-m3:f16` |

Nomic byl vybrán z tohoto API pro první integraci; není doloženým vítězem pro češtinu. MXBAI má jiný query prefix a kratší kontext, takže nestačí změnit pouze název/dimenzi profilu. BGE rerankery mohou hlásit `completion`; tento údaj ani skrytá velikost embedding vrstvy z nich nedělají chatový či embeddingový model. Název s `rerank` se konzervativně oddělí; neznámý BERT specialista se nenabízí jako chat. Vzdálený alias a deklarované schopnosti jsou metadata, nikoli nezávislé potvrzení skutečné verze, licence, kvality nebo bezchybného `/api/generate` kontraktu.

## Implementovaný registr a výběr modelů

Přehled má hledání podle názvu, **Přidat pro testování**, hromadné přidání kompatibilních modelů a checkbox **Zobrazit v uživatelské aplikaci**. Backend znovu ověří metadata a uloží profil do přesného tenantového SQL registru. Samotný read-only scan stále nic neschvaluje. Přidané LLM se objeví v administraci pro odpovědi, shrnutí i klasifikaci; publikované profily uvidí i povolené skupiny běžných uživatelů. Výchozí JSON profily zůstávají.

Embeddingy mají samostatné profily: stávající Nomic a MXBAI s vlastní query instrukcí a 1024 rozměry. Po přidání připrav konkrétní index v embeddingové sekci. Běžní uživatelé mohou vybrat pouze publikovaný a skupinově povolený úplný index. Rerankery a neověřená metadata se nepřidávají; neznámý embeddingový recept vyžaduje konfiguraci. Nikdy se automaticky nestahuje ani nebenchmarkuje celý inventář.

Podrobný [postup registrace a výběru](local-model-registry.md), [příprava indexů](local-embeddings.md), [modelová připojení](model-selection.md). Cloudové schéma a síť mají samostatný handoff.

## Jediný embeddingový index na dotaz

Uživatel vybírá konkrétní existující `search_index_id` (UUID). Backend ověří přesný tenant, publikaci, serverové skupiny, současné pokrytí a neměnný profil/digest/rozměry. Dotaz vytvoří jediný query embedding a čte jedinou tabulku; metadata/ACL filtry dál platí před top K. Dva indexy stejného profilu se nezaměňují. Neúplný, zakázaný či změněný explicitní výběr je chyba bez fallbacku nebo opětovného odeslání.

Volba nemění ingestaci. Nové chunky mohou vyžadovat doplnění experimentálních indexů. Modelová dostupnost a ANN recall jsou jiné otázky než relevance embeddingů; porovnávej stejné české dotazy a filtry, nikoli cosine skóre mezi různými modely.

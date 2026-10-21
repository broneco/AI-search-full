# ADR-0037: Editovatelný limit výstupu modelu

- Status: accepted
- Date: 2026-10-21

## Kontext a rozhodnutí

Správce nastaví výstupní rozpočet JSON i registrovaných LLM ve společném administračním přehledu. Samostatná tabulka `model_runtime_settings` uchovává hash přesného tenantu, ID LLM, přesný tenant, volitelný limit, revizi, autora a UTC čas. Změna nezasahuje immutable schválený profil, digest ani embeddingový prostor. Výchozí je původní konfigurace/snapshot; `NULL` znamená návrat na výchozí hodnotu. Reset zachová řádek/revizi, aby stará revize 0 nemohla přepsat novější stav. Zápis vyžaduje aktuální Management a CAS. Embeddingové profily nelze takto nastavovat.

Efektivní katalog skládá JSON + immutable registr + provozní override. Limit je společný pro chat/shrnutí/klasifikaci při nově zahájených operacích, včetně implicitního klasifikátoru s DB session a operátorské CLI cesty. Již vytvořený provider drží snapshot běžící operace. Veřejný autorizovaný katalog uvádí efektivní hodnotu. DB-less metadata utility zůstávají u souborové konfigurace.

Aplikační rozsah je 128–32768. Připnutý lokální profil musí nechat alespoň 1024 jednotek vstupního rozpočtu a rezervu 256 v nakonfigurovaném kontextu. Legacy profil bez ověřeného kontextu dovolí pouze hodnotu do svého původního limitu. Zvýšení výstupu zmenší vstupní limit; snížení jej nezvětší nad původní profil. Žádné tiché oříznutí. Služba může mít další omezení.

Adaptéry aplikují strop přes Azure `max_completion_tokens` a lokální `options.num_predict` i bez `num_ctx`. Nižší interní limit je dovolený, vyšší nesmí překročit efektivní maximum. ID, digest, kontext a vektory zůstávají stejné.

Lokální startup vytvoří tabulku. Azure ji vynechá a vyžaduje guarded `migrate_model_limits.py`. Skutečně chybějící tabulka dovoluje původní čtení katalogu; zápis požaduje migraci a ostatní SQL chyby se neignorují. Popisy a limity sdílejí ověřený read helper, ale mají samostatné tabulky/revize.

## Alternativy a hranice

Přepsání JSON či registry snapshotu by směšovalo provozní stav s immutable identitou a nebylo sdílené mezi replikami. Přidání pole do chat requestu by umožnilo klientovi měnit správcovský strop. Per-purpose limity, automatické ladění, přepracování korpusu a cloudové nasazení nejsou součástí této slice.

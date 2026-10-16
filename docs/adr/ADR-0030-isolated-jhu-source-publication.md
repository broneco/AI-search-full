# ADR-0030: Reprodukovatelné předávání JHU bez vývojové historie

- Status: accepted
- Date: 2026-10-16

## Rozhodnutí

GitHub vývoj, Forgejo JHU snapshoty a Azure runtime mají oddělené historie a oprávnění. Zdrojové předání vzniká z konkrétního commitnutého refu přes git archive, bez kopie Git objektů. Forgejo aktualizace je běžný navazující souhrnný commit nad jeho vlastním main, nikdy mirror/merge původní historie ani force-push.

Export a sync jsou verzované nástroje v hlavním repozitáři. Nemají závislost na původních ignorovaných operátorech. Projekce povoluje jediný JHU tenant a motiv, materializuje potřebné sdílené konfigurace a nahrazuje historickou dokumentaci aktuálními verzovanými templates. Neočekávaný drift formátu vyžaduje revizi. Interní zdrojové SHA a hashe jsou v odděleném manifestu mimo zákaznický Git.

Sync je výchozím režimem read-only. Apply ověřuje samostatný clone s přesným origin/main, čistý strom, cílové HEAD, manifest a hranice souborových cest. Soubory mění bez commit/push/cloud operací. Odebírá pouze sledované stale soubory; ignorované secrets a Git metadata zachová. Operátor musí před aplikací posoudit případné nové zákaznické commity a plánovaný diff.

## Důsledky

Stejné vydání lze reprodukovat po novém klonu. Verzované templates vyžadují revizi spolu se změnou aplikace. Partial file apply je viditelný jako lokální diff a vyžaduje kontrolované obnovení, není to atomická Git transakce. Publikace zdrojů sama neprokazuje ani nespouští Azure release.

[Kanonický workflow](../../.agents/workflows/jhu-publication.md) obsahuje příkazy, testy, cílové kontroly, oddělenou autorizaci, pokračování po přerušení a provozní nasazení.

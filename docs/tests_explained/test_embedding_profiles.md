# Vysvětlení testů `test_embedding_profiles.py`

Testy ověřují embeddingový profil a Azure provider bez připojení k Azure. Síťový klient je nahrazen fake rozhraním, které zaznamená texty, deployment a počet rozměrů.

## Vysoká technická úroveň

Profil představuje identitu prostoru, ve kterém se embeddingy porovnávají. Testy zajišťují, že změna modelu, revize, rozměru nebo vstupního prefixu změní stabilní identifikátor. Azure adaptér odděleně zpracuje dotaz a dokument a zachová pořadí výsledků i přes hranice API dávek.

## Nízká technická úroveň

- Neměnný profil nelze omylem upravit poté, co jej provider používá.
- Profil odmítne vektor s nesprávným počtem čísel nebo s hodnotou NaN či nekonečno.
- Fake Azure API ověří, že dotaz používá dotazový prefix, dokumenty používají dokumentový prefix a požadavek nese nakonfigurovaný rozměr.
- Dávka 33 textů ověří rozdělení 32 + 1 a zachování původního pořadí.
- Neúplná odpověď providera se odmítne, aby se vektor omylem nepřiřadil jinému chunku.
- Factory použije aktuální nastavení profilu a selže jasně, pokud je zvolen dosud neregistrovaný provider.

Spuštění: `pytest tests/test_embedding_profiles.py`.

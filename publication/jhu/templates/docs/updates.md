# Předávání dalších verzí

Tento repozitář má vlastní Git historii začínající úvodním snapshotem. Aktualizace znamená nový souhrnný commit nad předchozím předáním. Původní vývojové větve, tagy a objekty se nepřipojují, nemergují ani nemirrorují.

1. Připrav ověřený JHU snapshot se stejnými pravidly: jediný tenant, žádné privátní env/data, závislosti, pracovní archivy ani původní .git.
2. V samostatném checkoutu tohoto Forgejo repozitáře ověř `git status` a aktuální origin, pak `git pull --ff-only origin main`.
3. Aktualizuj zdrojové soubory ze snapshotu a zkontroluj i záměrně odstraněné soubory. Zachovej .git, lokální secrets a vlastní necommitované úpravy; při konfliktu se zastav a vyřeš jej.
4. Zkontroluj diff, spusť relevantní testy a zapiš aktuální změny do changelogu.
5. Vytvoř jeden commit s popisem předávané změny a použij běžné `git push origin main`.

Nepoužívej `git push --mirror`, import původních větví/tagů ani force-push. Je-li cílem příprava nového prázdného repozitáře, vytvoř vlastní .git ze snapshotu, nikoli kopii .git vývojového projektu. Samotná publikace zdrojů nenasazuje Azure aplikaci.

# vysvětlení testu `test_tenant_prompts.py`

Tento dokument poskytuje technické i laické vysvětlení testovacího modulu `tests/test_tenant_prompts.py`.

---

## 1. Výměr a účel testu (Netechnické shrnutí)

Test ověřuje výběr správného systémového promptu, oba jazyky a izolaci klientů. Vytváří dočasné syntetické tenanty `alpha` a `beta`; skutečné konfigurace dalších klientů nejsou nutné, takže sada běží i v exportu obsahujícím pouze JHU.

---

## 2. Technické řešení (Technical Deep Dive)

Testovací modul `tests/test_tenant_prompts.py` ověřuje funkčnost modulu `app.core.prompts`:

1. `test_tenant_base_extraction()`: Ověřuje suffixy, alias `ju-prod → jhu` a prázdnou identitu.
2. `test_tenant_prompt_formats_both_languages()`: Kontroluje českou i anglickou šablonu včetně přesného vložení kontextu.
3. `test_tenant_prompt_does_not_mix_clients()`: Kontroluje, že prompt beta neobsahuje identitu alpha. Fixture přesměruje resolver a vypne lokální overlay pouze po dobu testu; nedotýká se skutečných tenantích souborů.

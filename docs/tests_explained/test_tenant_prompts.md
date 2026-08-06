# vysvětlení testu `test_tenant_prompts.py`

Tento dokument poskytuje technické i laické vysvětlení testovacího modulu `tests/test_tenant_prompts.py`.

---

## 1. Výměr a účel testu (Netechnické shrnutí)

Test ověřuje, že vyhledávač AI Search používá pro každého klienta (tenanta) **správný a přizpůsobený systémový prompt**. Pro **Nemocnici sv. Alžběty na Slupi** (`alzbeta`) ověřuje, že model dostává instrukce k identifikaci klíčových představitelů vedení nemocnice:
- **Jednatel**: RNDr. Karel Matyska, CSc.
- **Náměstek LPP**: MUDr. Ivana Doleželová, MBA
- **Náměstek NZOK**: Mgr. Marcela Tomanová, MBA, LL.M.

Pro ostatní klienty (např. **Dolphin Consulting**) se naopak používá obecnější firemní prompt bez nemocničních specifik.

---

## 2. Technické řešení (Technical Deep Dive)

Testovací modul `tests/test_tenant_prompts.py` ověřuje funkčnost modulu `app.core.prompts`:

1. `test_tenant_base_extraction()`: Testuje parsování bázového jména tenanta z řetězců jako `"alzbeta-prod"` nebo `"dolphin-dev"`.
2. `test_alzbeta_tenant_prompt_identifies_leaders()`: Testuje generování českého i anglického systémového promptu pro tenanty `alzbeta-prod` a `alzbeta-dev` a ověřuje přítomnost jmen a funkcí vedení nemocnice.
3. `test_dolphin_tenant_prompt()`: Ověřuje izolaci promptů tak, aby nemocniční představitelé nebyli přítomni v promptu klienta Dolphin Consulting.

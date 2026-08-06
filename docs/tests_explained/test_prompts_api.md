# vysvětlení testu `test_prompts_api.py`

Tento dokument poskytuje technické i laické vysvětlení testovacího modulu `tests/test_prompts_api.py`.

---

## 1. Výměr a účel testu (Netechnické shrnutí)

Test ověřuje funkčnost REST API endpointů pro správy systémového promptu:
- `GET /api/prompts`: Načte aktuální systémový prompt pro daného tenanta v češtině i angličtině.
- `PUT /api/prompts`: Umožní administrátorovi upravit a uložit nový systémový prompt, který se ihned aplikuje na všechny nové dotazy uživatelů.

---

## 2. Technické řešení (Technical Deep Dive)

Testovací modul `tests/test_prompts_api.py` využívá `fastapi.testclient.TestClient`:

1. `test_get_prompts_endpoint()`: Volá `GET /api/prompts` a ověřuje vrácení objektu se klíči `tenant_id`, `tenant_base` a slovníkem `prompts` obsahujícím šablony pro `cs` a `en`.
2. `test_update_prompt_endpoint()`: Odesílá `PUT /api/prompts` s novým textem promptu, ověřuje HTTP 200 a následně ověřuje přes `GET /api/prompts`, že změněný prompt persistuje.

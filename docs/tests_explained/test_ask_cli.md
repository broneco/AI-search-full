# Testy autentizovaného CLI

`tests/test_ask_cli.py` používá httpx.MockTransport. Ověřuje skutečnou tvorbu HTTP požadavků: token patří do Authorization, přihlášení používá skryté zadání hesla a následuje chat se serverovým tokenem. Odpověď401 znamená nenulový návrat a citlivý detail ani token se nevypíše. Nekorektní URL a HTTP mimo loopback se odmítají před požadavkem.

Spuštění: `python -m pytest tests/test_ask_cli.py -q`. Nevyžaduje běžící API, DB nebo Azure.

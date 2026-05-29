import asyncio
import sys
from app.storage.db import SessionLocal, init_db
from app.api.routes.chat import chat_interaction
from app.schemas.chat import ChatRequest

async def main():
    # Proactively ensure database base schemas and indices exist
    init_db()

    print("=" * 75)
    print("🇨🇿 Firemní AI vyhledávač - Testovací dotazník")
    print("=" * 75)
    
    # Parse command line arguments
    query_args = []
    strategy = "hybrid"
    for arg in sys.argv[1:]:
        if arg.startswith("--strategy="):
            strategy = arg.split("=")[1].strip().lower()
        else:
            query_args.append(arg)

    if query_args:
        query = " ".join(query_args)
    else:
        print("Dostupné strategie vyhledávání: 'hybrid' (Weighted RRF), 'vector' (Sémantika), 'keyword' (Full-Text)")
        strategy_input = input(f"Zvolte strategii (výchozí '{strategy}'): ").strip().lower()
        if strategy_input in ("hybrid", "vector", "keyword"):
            strategy = strategy_input
        query = input("Zadejte dotaz (např. 'Jaká jsou pravidla pro registr smluv?'): ")
        
    if not query.strip():
        print("Konec. Prázdný dotaz.")
        return

    print(f"\n🔍 Vyhledávám pomocí strategie '{strategy}' v Azure PostgreSQL a generuji odpověď...")
    
    db = SessionLocal()
    try:
        request = ChatRequest(
            query=query,
            mode="flash",
            include_sources=True,
            search_strategy=strategy
        )
        response = await chat_interaction(request, db)
        
        print("\n🤖 Odpověď:")
        print("-" * 75)
        print(response.answer)
        print("-" * 75)
        
        if response.sources:
            print("\n📄 Citované zdroje a skóre shody:")
            for idx, src in enumerate(response.sources):
                print(f"  [{idx+1}] {src.title} (strana {src.page_number}) [Skóre: {src.score:.4f}]")
    except Exception as e:
        print(f"\n❌ Chyba při zpracování dotazu: {e}")
    finally:
        db.close()
    print("=" * 70)

if __name__ == "__main__":
    # Standard console encoding fix for Windows Czech characters
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.run(main())

import asyncio
from scraper.session_manager import SessionManager
from scraper.proxy_manager import ProxyManager
from scraper.search_scraper import scrape_search

async def test():
    pm = ProxyManager()
    sm = SessionManager(pm)
    await sm.initialise()
    
    products = await scrape_search(
        session_manager=sm,
        keyword="iphone 17 pro",
        pages=1,
    )
    
    print(f"Products found: {len(products)}")
    if products:
        p = products[0]
        print(f"Name  : {p['name']}")
        print(f"Price : {p['current_price']} AED")
        print(f"SKU   : {p['noon_sku']}")
        print(f"Store : {p['store_name']}")

# --- THIS IS THE MISSING PIECE ---
if __name__ == "__main__":
    asyncio.run(test())
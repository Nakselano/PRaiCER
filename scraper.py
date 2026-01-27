import os
import re
import random
from serpapi import GoogleSearch
from dotenv import load_dotenv

load_dotenv()

def _clean_price(price_raw) -> float:
    if isinstance(price_raw, (int, float)):
        return float(price_raw)
    if not price_raw or not isinstance(price_raw, str):
        return 0.0

    clean = re.sub(r'[^\d.,]', '', price_raw)
    clean = clean.replace(',', '.')
    try:
        if clean.count('.') > 1:
            clean = clean.replace('.', '', clean.count('.') - 1)
        return float(clean)
    except:
        return 0.0



def get_mock_search_results(query: str):
    print(f"🔎 MOCK SEARCH: '{query}'")
    img = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Cat_August_2010-4.jpg/1200px-Cat_August_2010-4.jpg"
    return [
        {"name": f"{query} Pro", "price": 299.00, "image_url": img, "link": "http://google.com"},
        {"name": f"{query} Lite", "price": 99.00, "image_url": img, "link": "http://google.com"},
        {"name": f"Markowe {query}", "price": 450.00, "image_url": img, "link": "http://google.com"},
    ]


def get_mock_deep_data(name: str, price: float, link: str):
    return {
        "name": name,
        "price": price,
        "image_url": "",
        "offers": [{"store": "MockStore", "price": price, "link": link}],
        "reviews": [
            {"content": "Bateria trzyma krótko, ale dźwięk super.", "rating": 4.0, "source": "Forum"},
            {"content": "Nie polecam, zepsuły się po miesiącu.", "rating": 1.0, "source": "Ceneo"}
        ]
    }

def search_products_shallow(query: str):
    api_key = os.getenv("SERP") or os.getenv("SERPAPI_KEY")
    if not api_key:
        return get_mock_search_results(query)

    try:
        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": "pl",
            "hl": "pl",
            "api_key": api_key
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        products = []
        for item in results.get("shopping_results", [])[:12]:
            products.append({
                "name": item.get("title"),
                "price": _clean_price(item.get("price")),  
                "image_url": item.get("thumbnail"),
                "link": item.get("link") or item.get("product_link")
            })
        return products if products else get_mock_search_results(query)
    except Exception as e:
        print(f"{e}")
        return get_mock_search_results(query)


def scrape_product_deep(name: str, price: float, link: str):
    api_key = os.getenv("SERP")

    data = {
        "name": name,
        "price": price,
        "image_url": "",  
        "offers": [{"store": "Wybrana Oferta", "price": price, "link": link}],
        "reviews": []
    }

    if not api_key:
        return get_mock_deep_data(name, price, link)

    try:
        params = {
            "engine": "google",
            "q": f"{name} opinie forum wady zalety",  
            "gl": "pl",
            "hl": "pl",
            "num": 10,  
            "api_key": api_key
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        if "organic_results" in results:
            for res in results["organic_results"]:
                snippet = res.get("snippet", "")
                title = res.get("title", "")
                if len(snippet) > 30:
                    data["reviews"].append({
                        "content": f"[{title}] {snippet}",  
                        "rating": 0.0,  
                        "source": res.get("source", "Google Search")
                    })
    except Exception as e:
        print(f"{e}")
        pass
    return data
import requests


def fetch_google_doc_content(doc_id: str) -> str:
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    print(f"📥 Pobieranie wiedzy z Google Docs (ID: {doc_id})...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        text = response.text
        print(f"✅ Pobrano {len(text)} znaków.")
        return text
    except Exception as e:
        print(f"❌ Błąd pobierania Google Doc: {e}")
        return ""

if __name__ == "__main__":
    
    TEST_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    print(fetch_google_doc_content(TEST_ID)[:100] + "...")
import json
import re
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from pydantic import BaseModel
from database import get_session, engine, create_db_and_tables
from models import Product, Review, Offer, Insight, AnalysisStatus
from scraper import search_products_shallow, scrape_product_deep
from ai_service import analyze_reviews_with_gemini, generate_ai_response
from rag_engine import rag
from tools import TOOLS_MAP, TOOLS_DESC
import uvicorn
from security import guard
import logging

create_db_and_tables()

app = FastAPI()

origins = [
    "http://localhost:8051",
    "http://127.0.0.1:8051",
    "*"  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tool_logger = logging.getLogger("tool_logger")
tool_logger.setLevel(logging.INFO)
tool_logger.propagate = False

file_handler = logging.FileHandler("tools_activity.log", mode="a", encoding="utf-8")
formatter = logging.Formatter('%(asctime)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)
tool_logger.addHandler(file_handler)

def log_tool_activity(tool_name, status, details = "-"):
    tool_logger.info(f"{tool_name} | {status} | {details}")

class SearchQuery(BaseModel):
    query: str
    
class AnalyzeRequest(BaseModel):
    name: str
    price: float
    image_url: str
    link: str

class Message(BaseModel):
    role: str  
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]  
    provider: str = "auto"
    active_product_name: str | None = None

def process_ai_analysis(product_id: int):
    with Session(engine) as session:
        reviews = session.exec(select(Review).where(Review.product_id == product_id)).all()
        offers = session.exec(select(Offer).where(Offer.product_id == product_id)).all()
        if not reviews and not offers:
            return

        text_corpus = "RAPORT CENOWY:\n"
        for o in offers:
            text_corpus += f"- Sklep: {o.store_name}, Cena: {o.price} zł\n"
        text_corpus += "\nOPINIE UŻYTKOWNIKÓW:\n"
        for r in reviews:
            text_corpus += f"- (Ocena: {r.rating}/5) {r.content}\n"
        try:
            result = analyze_reviews_with_gemini(text_corpus)
            insight = session.exec(select(Insight).where(Insight.product_id == product_id)).first()
            if insight:
                insight.summary = result.get("summary", "Brak podsumowania")
                insight.pros = result.get("pros", "Brak")
                insight.cons = result.get("cons", "Brak")
                insight.status = AnalysisStatus.COMPLETED
                session.add(insight)
                session.commit()

        except Exception as e:
            print(f"{e}")
            insight = session.exec(select(Insight).where(Insight.product_id == product_id)).first()
            if insight:
                insight.status = AnalysisStatus.ERROR
                session.add(insight)
                session.commit()

@app.post("/search")
def search_endpoint(req: SearchQuery):
    results = search_products_shallow(req.query)
    return {"results": results}


@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_session)):
    existing = db.exec(select(Product).where(Product.name == req.name)).first()
    if existing:
        insight = db.exec(select(Insight).where(Insight.product_id == existing.id)).first()
        if not insight or insight.status == AnalysisStatus.NONE:
            background_tasks.add_task(process_ai_analysis, existing.id)
        return {"message": "Produkt pobrany z cache", "id": existing.id}
    data = scrape_product_deep(req.name, req.price, req.link)
    try:
        price_val = float(data["price"])
    except:
        price_val = 0.0
    final_image = data.get("image_url") if data.get("image_url") else req.image_url
    new_product = Product(
        name=data["name"],
        price=price_val,
        image_url=final_image
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    for off in data.get("offers", []):
        db.add(Offer(
            product_id=new_product.id,
            store_name=off["store"],
            price=off["price"],
            link=off["link"]
        ))

    for rev in data.get("reviews", []):
        db.add(Review(
            product_id=new_product.id,
            content=rev["content"],
            rating=rev["rating"],
            source=rev.get("source", "unknown")
        ))

    insight = Insight(product_id=new_product.id, status=AnalysisStatus.PROCESSING)
    db.add(insight)
    db.commit()
    background_tasks.add_task(process_ai_analysis, new_product.id)
    return {"message": "Rozpoczęto analizę i zapisano produkt", "id": new_product.id}


def security_guardrail(text: str) -> bool:
    forbidden = ["ignore previous", "zapomnij instrukcje", "system prompt", "reveal"]
    text_lower = text.lower()
    if any(f in text_lower for f in forbidden):
        return False
    return True

MAX_TOOL_OUTPUT_CHARS = 8000

def truncate_tool_output(output: str, max_len: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(output) > max_len:
        return output[:max_len] + f"\n... [Przycięto {len(output)-max_len} znaków]"
    return output
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):

    last_user_msg = req.messages[-1].content if req.messages else ""
    provider = req.provider
    rag_context = rag.search(last_user_msg, k=2)

    if guard.check_path_traversal(last_user_msg):
        raise HTTPException(status_code=400, detail="Wykryto niedozwolone znaki w zapytaniu.")

    if not security_guardrail(last_user_msg):
        raise HTTPException(status_code=400, detail="Zapytanie zablokowane.")
    context_faq = rag.search(last_user_msg)
    history_str = ""
    for msg in req.messages:
        prefix = "Użytkownik" if msg.role == "user" else "Asystent"
        history_str += f"{prefix}: {msg.content}\n"
    system_prompt = f"""
        Jesteś Inteligentnym Asystentem Zakupowym. Twoim celem jest pomóc użytkownikowi w zakupach, łącząc twarde dane z bazy z twoją wiedzą ogólną.

        ---------------------------------------------------
        AKTUALNY KONTEKST:
        - Użytkownik przegląda teraz produkt: "{req.active_product_name if req.active_product_name else 'Brak'}"
        - Dodatkowa wiedza (RAG/Sekrety): {rag_context}
        ---------------------------------------------------
        ZASADA CARDINALNA (NAJWAŻNIEJSZA):
        Twoja odpowiedź trafia BEZPOŚREDNIO do klienta na czacie.
        ❌ NIE WOLNO Ci wypisywać nazwy scenariusza (np. "SCENARIUSZ 2").
        ❌ NIE WOLNO Ci pisać co robisz (np. "Analizuję bazę...").
        ✅ Pisz TYLKO finalną treść wiadomości.
        
        TWOJE ZADANIE - ZIDENTYFIKUJ SCENARIUSZ(NIE WYPISUJ, KTÓRY) I ZACHOWAJ SIĘ ODPOWIEDNIO:

        SCENARIUSZ 1: Użytkownik chce znaleźć/zmienić produkt
        (np. pisze "ThinkPad", "Pokaż iPhone'a", "Szukam słuchawek", "Jakie są zalety produktu?")
        -> Wtedy i TYLKO WTEDY użyj narzędzia.
        -> Zwróć JSON: {{"tool": "get_product_details", "args": {{"product_name": "..."}}}}
        -> Nie pisz żadnego tekstu, tylko JSON.

        SCENARIUSZ 2: Użytkownik zadaje pytanie o AKTUALNY produkt
        (np. "Jaki ma ekran?", "Czy jest dobry do gier?", "W jakich kolorach jest dostępny?")
        -> NIE używaj narzędzia (masz już produkt w kontekście).
        -> Odpowiedz normalnym tekstem.
        -> Użyj informacji z historii rozmowy (tam są dane z bazy o cenie/wadach).
        -> Jeśli w historii brakuje szczegółów technicznych (np. Hz ekranu), użyj swojej WIEDZY OGÓLNEJ.

        SCENARIUSZ 3: Pytania o RAG / Kontekst / Inne
        (np. "Jaki jest kod rabatowy?", "Co mówi regulamin?", "tajne hasło")
        -> Sprawdź sekcję "Dodatkowa wiedza (RAG)" powyżej.
        -> Odpowiedz tekstem na podstawie tej wiedzy.

        ---------------------------------------------------
        HISTORIA ROZMOWY:
        {history_str}

        DOSTĘPNE NARZĘDZIA:
        {TOOLS_DESC}
        """
    full_prompt = f"{system_prompt}\n\nHISTORIA ROZMOWY:\n{history_str}\nAsystent:"
    ai_response_text = generate_ai_response(full_prompt, provider=provider)

    if not ai_response_text:
        return {
            "response": "Przepraszam, system AI jest obecnie przeciążony (Limit zapytań). Spróbuj ponownie za minutę.",
            "provider_used": provider,
            "rag_context_used": False
        }

    if guard.check_prompt_leakage(ai_response_text):
        print("AI próbowało ujawnić System Prompt!")
        final_answer = "Przepraszam, nie mogę udzielić tej informacji ze względów bezpieczeństwa."
        return {"response": final_answer, "provider_used": provider, "rag_context_used": False}
    ai_response_text = guard.sanitize_output(ai_response_text)
    final_answer = ai_response_text
    tool_executed = False
    if '"tool":' in ai_response_text:
        try:
            json_match = re.search(r'(\{.*"tool":.*\})', ai_response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                json_str = re.sub(r'```(?:json)?', '', json_str).replace('```', '').strip()
                tool_call = json.loads(json_str)
                tool_name = tool_call.get("tool")
                tool_args = tool_call.get("args", {})

                if tool_name in TOOLS_MAP:
                    print(f"🔧 DISPATCHER: Wywołanie {tool_name}...")
                    tool_result_raw = TOOLS_MAP[tool_name](tool_args)
                    tool_result_safe = truncate_tool_output(str(tool_result_raw))
                    try:
                        res_json = json.loads(tool_result_safe)
                        if isinstance(res_json,dict) and res_json.get("status") == "error":
                            code = res_json.get("code")
                            msg = res_json.get("message")
                            log_tool_activity(tool_name, "ERROR",f'{code}: {msg}')
                            if code == "TIMEOUT":
                                final_answer = "Baza danych odpowiada zbyt wolno."
                            elif code == "NOT_FOUND":
                                final_answer = "Nie znalazłem takiego produktu."
                            else:
                                final_answer = f"Błąd techniczny: {res_json.get('message')}"
                        else:
                            log_tool_activity(tool_name, "OK", "Pobrano dane")
                            follow_up_prompt = f"""
                            {system_prompt}
                            
                            WYNIK Z BAZY DANYCH:
                            {tool_result_safe}
                            
                            Napisz użytkownikowi JEDNO krótkie zdanie, np. "Oto znaleziony iPhone 15".
                            NIE WYPISUJ CENY ANI PARAMETRÓW W TEKŚCIE (są w karcie poniżej).
                            """
                            ai_intro_text = generate_ai_response(follow_up_prompt, provider=provider)
                            final_answer = f"{ai_intro_text}\n\n{tool_result_safe}"
                            tool_executed = True
                    except json.JSONDecodeError:
                        log_tool_activity(tool_name, "WARN", "Wynik nie jest JSONem")
                        final_answer = f"Dane: {tool_result_safe}"
                else:
                    final_answer = f"Błąd: Nieznane narzędzie {tool_name}."
        except Exception as e:
            print(f"❌ Błąd dispatchera: {e}")
            final_answer = "Wystąpił błąd podczas przetwarzania zapytania."
    if not tool_executed:
        final_answer = guard.sanitize_output(final_answer)
        source_type = "RAG" if context_faq else "CHAT"
        log_tool_activity(source_type, "OK", "Wygenerowano odpowiedź tekstową")
    return {
        "response": final_answer,
        "provider_used": provider,
        "rag_context_used": bool(context_faq)
    }

if __name__ == "__main__":
    create_db_and_tables()
    print("Serwer na http://0.0.0.0:8000")

    uvicorn.run(app, host="0.0.0.0", port=8000)



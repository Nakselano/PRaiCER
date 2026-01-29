from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, select
from models import Product, Offer, Insight
from database import engine
import json
import concurrent.futures
import functools

MAX_TEXT_LENGTH = 500

def with_timeout(seconds: int):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, *args, **kwargs)
                    return future.result(timeout=seconds)
            except concurrent.futures.TimeoutError:
                return json.dumps(
                    {"status": "error", "code": "TIMEOUT", "message": f"Przekroczono czas operacji ({seconds}s)."})
            except ValidationError as ve:
                return json.dumps({"status": "error", "code": "VALIDATION_ERROR", "message": str(ve)})
            except Exception as e:
                return json.dumps({"status": "error", "code": "TOOL_ERROR", "message": str(e)})
        return wrapper
    return decorator

class ProductInput(BaseModel):
    product_name: str = Field(..., description="Nazwa produktu, o który pyta użytkownik")

class InstallmentInput(BaseModel):
    price: float = Field(..., gt=0)
    months: int = Field(..., ge=3, le=48)

@with_timeout(5)
def tool_get_product_details(args: dict) -> str:
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                return json.dumps({"status": "error", "code": "VALIDATION_ERROR", "message": "Argumenty nie są JSONem"})
        params = ProductInput(**args)
        search_term = params.product_name.strip()
        with Session(engine) as session:
            statement = select(Product).where(Product.name.ilike(f"%{search_term}%")).order_by(Product.id.desc())
            prod = session.exec(statement).first()
            if not prod:
                return json.dumps({"status": "error", "code": "NOT_FOUND", "message": f"Nie znaleziono produktu '{search_term}'."})
            offers = session.exec(select(Offer).where(Offer.product_id == prod.id)).all()
            insight = session.exec(select(Insight).where(Insight.product_id == prod.id)).first()

            summary_text = (insight.summary[:MAX_TEXT_LENGTH] + "...") if insight and insight.summary and len(
                insight.summary) > MAX_TEXT_LENGTH else (insight.summary if insight else "Brak analizy.")

            data = {
                "type": "product_report",
                "id": prod.id,
                "name": prod.name,
                "price": float(prod.price),
                "image": prod.image_url,
                "summary": summary_text,
                "pros": insight.pros if insight else "Brak danych.",
                "cons": insight.cons if insight else "Brak danych.",


                "system_info": f"""
                            TO SĄ FAKTY Z BAZY DANYCH O {prod.name}:
                            - Cena: {prod.price} zł
                            - Główne zalety z opinii: {insight.pros if insight else 'brak'}
                            - Główne wady z opinii: {insight.cons if insight else 'brak'}
                            Jeśli użytkownik pyta o te rzeczy, CYTUJ TE DANE.
                            Jeśli pyta o parametry techniczne (ekran, bateria), użyj swojej wiedzy.
                            """,
                

                "offers": [
                    {"store": o.store_name, "link": o.link.strip().replace("\n", ""), "price": float(o.price)}
                    for o in offers
                ]
            }
            return json.dumps(data, ensure_ascii=False)


@with_timeout(1)
def tool_calculate_installment(args: dict) -> str:
    if isinstance(args, str):
        try: args = json.loads(args)
        except: pass
        params = InstallmentInput(**args)
        monthly = params.price / params.months
        return json.dumps({
            "status": "success",
            "details": f"Rata: {monthly:.2f} zł miesięcznie ({params.months} rat) dla kwoty {params.price} zł."
        }, ensure_ascii=False)

TOOLS_MAP = {
    "get_product_details": tool_get_product_details,
    "calculate_installment": tool_calculate_installment
}
TOOLS_DESC = """
DOSTĘPNE NARZĘDZIA:
1. get_product_details(product_name: str) - Użyj ZAWSZE, gdy użytkownik pyta o cenę, zdjęcie, linki, zalety, wady lub chce poznać szczegóły zaimportowanego produktu.
2. calculate_installment(price: float, months: int) - Użyj do obliczeń ratalnych.
"""
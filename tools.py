from pydantic import BaseModel, Field
from sqlmodel import Session, select
from models import Product, Offer
from database import engine
import json

class ProductInput(BaseModel):
    product_name: str = Field(..., description="Nazwa produktu, o który pyta użytkownik")

class InstallmentInput(BaseModel):
    price: float = Field(..., gt=0)
    months: int = Field(..., ge=3, le=48)


def tool_get_product_details(args: dict) -> str:
    try:
        from models import Insight
        params = ProductInput(**args)
        search_term = params.product_name.strip()
        with Session(engine) as session:
            statement = select(Product).where(Product.name.ilike(f"%{search_term}%")).order_by(Product.id.desc())
            prod = session.exec(statement).first()
            if not prod:
                return f"Błąd: Nie znaleziono produktu {search_term}"
            offers = session.exec(select(Offer).where(Offer.product_id == prod.id)).all()
            insight = session.exec(select(Insight).where(Insight.product_id == prod.id)).first()

            data = {
                "type": "product_report",
                "id": prod.id,
                "name": prod.name,
                "price": float(prod.price),
                "image": prod.image_url,
                "summary": insight.summary if insight else "Brak analizy.",
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
    except Exception as e:
        return f"{e}"


def tool_calculate_installment(args: dict) -> str:
    try:
        params = InstallmentInput(**args)
        monthly = params.price / params.months
        return f"Symulacja raty dla kwoty {params.price} zł: **{monthly:.2f} zł** miesięcznie ({params.months} rat)."
    except Exception as e:
        return f"Błąd obliczeń: {e}"


TOOLS_MAP = {
    "get_product_details": tool_get_product_details,
    "calculate_installment": tool_calculate_installment
}
TOOLS_DESC = """
DOSTĘPNE NARZĘDZIA:
1. get_product_details(product_name: str) - Użyj ZAWSZE, gdy użytkownik pyta o cenę, zdjęcie, linki, zalety, wady lub chce poznać szczegóły zaimportowanego produktu.
2. calculate_installment(price: float, months: int) - Użyj do obliczeń ratalnych.
"""
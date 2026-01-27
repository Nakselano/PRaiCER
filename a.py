from sqlmodel import SQLModel
from database import engine
from models import Product, Offer, Review, Insight

def reset():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

if __name__ == '__main__':
    reset()
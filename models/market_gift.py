from pydantic import BaseModel

class MarketGift(BaseModel):
    code: str
    title: str
    price_stars: int
    remaining: int
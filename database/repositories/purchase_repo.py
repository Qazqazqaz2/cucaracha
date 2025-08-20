from sqlmodel import select, Session
from models.purchase import Purchase
from database.repositories.base_repo import BaseRepository
import json

class PurchaseRepository(BaseRepository):
    def create_purchase(self, gift_type_id: int, account_id: int, price_stars: int, owner_user_id: int, meta: dict) -> Purchase:
        p = Purchase(
            gift_type_id=gift_type_id,
            account_id=account_id,
            price_stars=price_stars,
            status="purchased",
            owner_user_id=owner_user_id,
            ext_payload=json.dumps(meta, ensure_ascii=False)
        )
        self.session.add(p)
        self.session.commit()
        return p

    def get_pending(self):
        return self.session.exec(select(Purchase).where(Purchase.status == "purchased")).all()

    def mark_delivered(self, purchase: Purchase):
        purchase.status = "delivered"
        self.session.add(purchase)
        self.session.commit()

    def get_all_pending(self):
        return self.get_pending()
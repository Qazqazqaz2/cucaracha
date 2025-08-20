from sqlmodel import select, Session
from models.gift_type import GiftType
from database.repositories.base_repo import BaseRepository

class GiftTypeRepository(BaseRepository):
    def get_by_code(self, code: str) -> GiftType | None:
        return self.session.exec(select(GiftType).where(GiftType.code == code)).first()

    def create_or_update(self, code: str, title: str, price_stars: int, remaining_global: int) -> GiftType:
        gt = self.get_by_code(code)
        if not gt:
            gt = GiftType(
                code=code,
                title=title,
                price_stars=price_stars,
                remaining_global=remaining_global,
            )
            self.session.add(gt)
        else:
            gt.price_stars = price_stars
            gt.remaining_global = remaining_global
            gt.title = title
            self.session.add(gt)
        self.session.commit()
        return gt

    def get_all(self):
        return self.session.exec(select(GiftType)).all()

    def decrement_remaining(self, gt: GiftType):
        gt.remaining_global = max(0, gt.remaining_global - 1)
        self.session.add(gt)
        self.session.commit()
from sqlmodel import select, Session
from math import floor
from models.deposit import Deposit
from database.repositories.base_repo import BaseRepository

class DepositRepository(BaseRepository):
    def apply_realization_fifo(self, user_id: int, amount: int):
        deposits = self.session.exec(select(Deposit).where(Deposit.user_id == user_id).order_by(Deposit.id.asc())).all()
        remain = amount
        for d in deposits:
            if remain <= 0:
                break
            free = d.amount_stars_gross - d.realized_spend
            use = min(free, remain)
            if use > 0:
                d.realized_spend += use
                d.commission_final = floor(d.realized_spend * d.commission_rate + 0.5)
                d.refunded_commission = max(0, d.commission_provisional - d.commission_final)
                self.session.add(d)
                remain -= use
        self.session.commit()

    def create_deposit(self, user_id: int, amount: int, commission_rate: float):
        provisional = floor(amount * commission_rate + 0.5)
        dep = Deposit(user_id=user_id, amount_stars_gross=amount, commission_rate=commission_rate,
                      commission_provisional=provisional)
        self.session.add(dep)
        self.session.commit()

    def get_by_user_id(self, user_id: int):
        return self.session.exec(select(Deposit).where(Deposit.user_id == user_id)).all()
from sqlmodel import select, Session
from sqlalchemy.exc import IntegrityError
from models.account import Account
from database.repositories.base_repo import BaseRepository

class AccountRepository(BaseRepository):
    def get_or_create_account(self, session_name: str) -> Account:
        account = self.session.exec(select(Account).where(Account.session_name == session_name)).first()
        if account:
            return account

        account = Account(session_name=session_name)
        self.session.add(account)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            account = self.session.exec(select(Account).where(Account.session_name == session_name)).first()
        return account

    def get_all_non_blacklisted(self):
        return self.session.exec(select(Account).where(Account.blacklisted == False)).all()

    def get_by_id(self, acc_id: int) -> Account | None:
        return self.session.get(Account, acc_id)

    def update(self, account: Account):
        self.session.add(account)
        self.session.commit()

    def blacklist(self, acc: Account, reason: str):
        acc.blacklisted = True
        acc.last_error = reason
        self.session.add(acc)
        self.session.commit()

    def get_all(self):
        return self.session.exec(select(Account)).all()
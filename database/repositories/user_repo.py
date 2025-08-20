from sqlmodel import select, Session
from sqlalchemy.exc import IntegrityError
from models.user import User
from database.repositories.base_repo import BaseRepository

class UserRepository(BaseRepository):
    def get_by_tg_id(self, tg_id: int) -> User | None:
        return self.session.exec(select(User).where(User.tg_id == tg_id)).first()

    def create_or_update(self, tg_id: int) -> User:
        user = self.get_by_tg_id(tg_id)
        if not user:
            user = User(tg_id=tg_id)
            self.session.add(user)
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                user = self.get_by_tg_id(tg_id)
        return user

    def update(self, user: User):
        self.session.add(user)
        self.session.commit()

    def get_all(self):
        return self.session.exec(select(User)).all()
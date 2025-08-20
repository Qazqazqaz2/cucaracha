from sqlmodel import create_engine, SQLModel
from config.settings import CFG

if CFG.DB_DSN:
    engine = create_engine(CFG.DB_DSN, echo=False)
else:
    engine = create_engine(f"sqlite:///{CFG.DB_PATH}", echo=False)
SQLModel.metadata.create_all(engine)
"""The connection to the database (Neon Postgres in deployments): engine, sessions, and the Base
every table class inherits from. Tables are in app/models/."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://wasac_user:wasac_pass@localhost:5432/wasac_db")

# pool_pre_ping: Neon closes idle connections; check before use instead of failing a request.
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

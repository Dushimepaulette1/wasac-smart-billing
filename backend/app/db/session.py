"""The connection to the database (Neon Postgres in deployments): engine, sessions, and the Base
every table class inherits from. Tables are in app/models/."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

def database_url() -> str:
    """Require an explicit database in production; keep the local setup convenient."""
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        return configured
    if os.getenv("RENDER") or os.getenv("APP_ENV", "").lower() == "production":
        raise RuntimeError("DATABASE_URL must be set before starting a production deployment.")
    return "sqlite:///./local.db"


DATABASE_URL = database_url()

# pool_pre_ping: Neon closes idle connections; check before use instead of failing a request.
connection_options = {}
if make_url(DATABASE_URL).get_backend_name() == "postgresql":
    # One small API worker on the free server: avoid a burst consuming the database's connections.
    connection_options = {"pool_size": 5, "max_overflow": 2, "pool_timeout": 10,
                          "connect_args": {"connect_timeout": 10}}
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, **connection_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

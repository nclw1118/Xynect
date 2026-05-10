from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection OK")
        return True
    except Exception as exc:
        print(f"Database connection FAILED: {exc}")
        return False


if __name__ == "__main__":
    import sys
    ok = check_db()
    sys.exit(0 if ok else 1)

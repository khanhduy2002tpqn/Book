from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Setup engine depending on whether it's SQLite or PostgreSQL
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import models  # noqa
    Base.metadata.create_all(bind=engine)

    # Auto-migrate new columns for SQLite if missing
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(documents);")).fetchall()
            existing_cols = [r[1] for r in res]
            if "grade" not in existing_cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN grade VARCHAR(50) DEFAULT 'Chung';"))
            if "subject" not in existing_cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN subject VARCHAR(100) DEFAULT 'Khác';"))
            conn.commit()
    except Exception:
        pass

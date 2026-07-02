"""
database.py — SQLAlchemy engine and session factory for MySQL (AWS RDS)
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Connection string ───────────────────────────────────────────────────────
DB_USER     = os.getenv("DB_USER",     "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")
DB_HOST     = os.getenv("DB_HOST",     "your-rds-endpoint.rds.amazonaws.com")
DB_PORT     = os.getenv("DB_PORT",     "3306")
DB_NAME     = os.getenv("DB_NAME",     "mysqlRouteOne")

# ?charset=utf8mb4 ensures full Unicode support (required for emoji / multi-byte)
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?charset=utf8mb4"
)

# ── SSL — AWS RDS enforces SSL by default; pass the RDS CA bundle ──────────
# Download from: https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
# Set RDS_SSL_CA=/path/to/global-bundle.pem in your .env to enable cert verification.
_ssl_ca = os.getenv("RDS_SSL_CA")
_connect_args: dict = {}
if _ssl_ca:
    _connect_args["ssl"] = {"ca": _ssl_ca}
else:
    # Encrypted connection without server cert verification (acceptable for dev/staging)
    _connect_args["ssl"] = {"ssl_disabled": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,      # verify connection health before using from pool
    pool_recycle=1800,       # recycle connections every 30 min (avoids RDS timeout)
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Table creation ──────────────────────────────────────────────────────────
_SCHEMAS_SQL = os.path.join(os.path.dirname(__file__), "schemas.sql")


def create_tables() -> None:
    """
    Execute schemas.sql against the AWS RDS MySQL instance.
    Every statement uses CREATE TABLE IF NOT EXISTS / CREATE DATABASE IF NOT EXISTS,
    so this is safe to call on every startup — existing tables are never dropped.
    """
    with open(_SCHEMAS_SQL, "r", encoding="utf-8") as fh:
        sql_script = fh.read()

    # Strip full-line comments first so a ";" inside a comment can never split
    # a statement, then split on ";" and execute each non-empty statement
    # individually (pymysql does not support multi-statement execution).
    sql_no_comments = "\n".join(
        line for line in sql_script.splitlines()
        if not line.lstrip().startswith("--")
    )
    statements = [s.strip() for s in sql_no_comments.split(";") if s.strip()]

    with engine.connect() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                # 1060 = duplicate column (ALTER TABLE already applied)
                # 1061 = duplicate key name (index already exists)
                code = getattr(e.orig, 'args', [None])[0] if hasattr(e, 'orig') else None
                if code in (1060, 1061):
                    continue
                raise
        conn.commit()

    logger.info(
        "schemas.sql executed — all tables verified / created on AWS RDS MySQL (%s).",
        DB_NAME,
    )


# ── Dependency ──────────────────────────────────────────────────────────────
def get_db():
    """Yield a database session and close it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

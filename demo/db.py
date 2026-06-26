# ─── db.py ───────────────────────────────────────────────────────────────────
# Single source of truth for all database connectivity.
# Every other file imports from here — nothing else talks to the DB directly.
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os

# ─── Path + Working Directory Fix ────────────────────────────────────────────
# Problem 1: Python path
#   Streamlit runs from demo/ so the project root isn't on sys.path.
#   Fix: insert the root so `from config import settings` resolves.
#
# Problem 2: .env location
#   pydantic-settings looks for .env relative to the current working
#   directory (demo/), but .env lives in the project root.
#   Fix: change the working directory to the root BEFORE importing config.
#   This is safe — it only affects where Python searches for .env,
#   not how any other part of the app behaves.
# ─────────────────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
os.chdir(ROOT_DIR)

from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from config import settings


# ─── Engine ──────────────────────────────────────────────────────────────────
# Created once at import time. Reused across all queries.
#
# pool_pre_ping=True  → verifies connection is alive before use.
#                       Critical for Streamlit: the script reruns on every
#                       user interaction, so stale connections must be caught
#                       before they cause silent mid-query crashes.
#
# echo=False          → suppresses SQL logging in terminal (clean output).
# ─────────────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# ─── Session Factory ─────────────────────────────────────────────────────────
# autocommit=False  → we control when transactions are committed.
# autoflush=False   → we flush manually; prevents unexpected DB writes.
# ─────────────────────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ─── Session Context Manager ─────────────────────────────────────────────────
# Usage in queries.py:
#
#     with get_db() as db:
#         result = db.execute(text("SELECT ..."))
#
# Guarantees the session is always closed — even if the query crashes.
# Never call SessionLocal() directly outside of this function.
# ─────────────────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─── Connection Health Check ──────────────────────────────────────────────────
# Called once when the Streamlit app boots (in app.py).
# Returns (True, "") on success.
# Returns (False, error_message) on failure.
# Lets us show a clear, friendly error page instead of a confusing crash.
# ─────────────────────────────────────────────────────────────────────────────
def test_connection() -> tuple[bool, str]:
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        return True, ""
    except Exception as e:
        return False, str(e)
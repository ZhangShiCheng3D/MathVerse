"""SQLAlchemy engine + session factory."""
import os
import time
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.services import metrics

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/mathverse.db")

# Handle sqlite relative path — ensure data directory exists
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# WAL lets readers and a writer coexist; busy_timeout avoids "database is locked"
# under concurrent writers. synchronous=NORMAL (WAL-safe — only risks the last
# txns on an OS/power crash, never corruption) is the big write-throughput win
# for the per-request quota/archive/analytics writes at scale.
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA wal_autocheckpoint=1000")
        cur.execute("PRAGMA cache_size=-16000")  # ~16MB page cache
        cur.close()


# DB write-latency instrumentation for /api/metrics. Writes are the single-box
# bottleneck at scale; this times only INSERT/UPDATE/DELETE (negligible overhead).
@event.listens_for(engine, "before_cursor_execute")
def _db_timer_start(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_q_start", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _db_timer_end(conn, cursor, statement, parameters, context, executemany):
    stack = conn.info.get("_q_start")
    if not stack:
        return
    elapsed = time.perf_counter() - stack.pop()
    if statement[:6].upper() in ("INSERT", "UPDATE", "DELETE"):
        metrics.observe_db_write(elapsed)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Call on app startup."""
    from app.models.all import Base
    Base.metadata.create_all(bind=engine)

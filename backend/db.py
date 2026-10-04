from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import JSON, String, Float, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from backend.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(4000), default="")
    created_at: Mapped[str] = mapped_column(default=lambda: datetime.now(timezone.utc).isoformat())
    status: Mapped[str] = mapped_column(default="uploaded")
    video: Mapped[dict] = mapped_column(JSON, default=dict)
    config: Mapped[dict] = mapped_column(JSON, default=lambda: {"zones": [], "lines": []})
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    ground_truth: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(nullable=True)
    job_id: Mapped[str | None] = mapped_column(nullable=True)
    run_id: Mapped[str | None] = mapped_column(nullable=True)
    result_run: Mapped[str | None] = mapped_column(nullable=True)
    heartbeat: Mapped[float] = mapped_column(Float, default=0)


engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True
)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_pragmas(connection, _):
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")


Session = sessionmaker(engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(engine)


def serialize(p):
    return {c.name: getattr(p, c.name) for c in Project.__table__.columns}

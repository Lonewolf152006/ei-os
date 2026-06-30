from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Float, Text, String, DateTime
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone

Base = declarative_base()

class IncidentTelemetry(Base):
    __tablename__ = 'incident_telemetry'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    cpu_spike: Mapped[float] = mapped_column(Float, nullable=True)
    memory_usage: Mapped[float] = mapped_column(Float, nullable=True)
    service_name: Mapped[str] = mapped_column(String, nullable=True)
    log_dump: Mapped[str] = mapped_column(Text, nullable=True)

class SlackMessage(Base):
    __tablename__ = 'slack_messages'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    channel: Mapped[str] = mapped_column(String, nullable=True)
    user: Mapped[str] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    text_embedding = mapped_column(Vector(1536), nullable=True)

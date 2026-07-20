from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import logging
import smtplib
import ssl
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, load_settings
from app.database import SessionFactory
from app.models import Incident, Monitor, NotificationDelivery


logger = logging.getLogger(__name__)

EmailSender = Callable[[EmailMessage, Settings], str]

SAFE_FAILURE_SUMMARIES = {
    "unexpected_status": "HTTP status was outside the accepted range.",
    "http_status": "HTTP status was outside the accepted range.",
    "unsafe_destination": "Monitor destination could not be reached safely.",
    "response_limit": "Monitor response exceeded the safe size limit.",
    "redirect": "Monitor redirect could not be completed safely.",
    "connect_timeout": "Monitor connection timed out.",
    "request_timeout": "Monitor request timed out.",
    "dns": "Monitor hostname could not be resolved.",
    "connection_refused": "Monitor connection was refused.",
    "tls": "Monitor TLS connection failed.",
    "connection": "Monitor connection failed.",
    "request": "Monitor request failed.",
    "internal": "Monitor check failed.",
}


@dataclass(frozen=True)
class OpeningEmailContext:
    delivery_id: UUID
    deduplication_key: str
    destination: str
    monitor_name: str
    opened_at: datetime
    cause_category: str | None


@dataclass(frozen=True)
class RecoveryEmailContext:
    delivery_id: UUID
    deduplication_key: str
    destination: str
    monitor_name: str
    opened_at: datetime
    resolved_at: datetime


def _safe_header_text(value: str) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _message_id(deduplication_key: str) -> str:
    digest = hashlib.sha256(deduplication_key.encode("utf-8")).hexdigest()
    return f"<notification-{digest}@api-monitoring.local>"


def build_opening_email(context: OpeningEmailContext, settings: Settings) -> EmailMessage:
    monitor_name = _safe_header_text(context.monitor_name)
    failure_summary = SAFE_FAILURE_SUMMARIES.get(
        context.cause_category,
        "Monitor check failed.",
    )
    message = EmailMessage()
    message["Subject"] = f"Incident opened: {monitor_name}"
    message["From"] = settings.email_from
    message["To"] = context.destination
    message["Message-ID"] = _message_id(context.deduplication_key)
    message.set_content(
        "\n".join(
            (
                f"Monitor: {monitor_name}",
                f"Opened at: {_utc_text(context.opened_at)}",
                f"Failure: {failure_summary}",
            )
        )
    )
    return message


def _duration_text(opened_at: datetime, resolved_at: datetime) -> str:
    total_seconds = max(0, int((resolved_at - opened_at).total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or hours:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def build_recovery_email(
    context: RecoveryEmailContext,
    settings: Settings,
) -> EmailMessage:
    monitor_name = _safe_header_text(context.monitor_name)
    message = EmailMessage()
    message["Subject"] = f"Incident recovered: {monitor_name}"
    message["From"] = settings.email_from
    message["To"] = context.destination
    message["Message-ID"] = _message_id(context.deduplication_key)
    message.set_content(
        "\n".join(
            (
                f"Monitor: {monitor_name}",
                f"Recovered at: {_utc_text(context.resolved_at)}",
                f"Incident duration: {_duration_text(context.opened_at, context.resolved_at)}",
            )
        )
    )
    return message


def send_smtp_message(message: EmailMessage, settings: Settings) -> str:
    with smtplib.SMTP(
        settings.email_host,
        settings.email_port,
        timeout=settings.email_timeout_seconds,
    ) as smtp:
        if settings.email_use_tls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.email_username:
            smtp.login(settings.email_username, settings.email_password or "")
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    return str(message["Message-ID"])


async def _load_email_context(
    delivery_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> OpeningEmailContext | RecoveryEmailContext | str:
    async with session_factory() as session:
        row = (
            await session.execute(
                select(NotificationDelivery, Incident, Monitor)
                .join(Incident, Incident.id == NotificationDelivery.incident_id)
                .join(Monitor, Monitor.id == Incident.monitor_id)
                .where(NotificationDelivery.id == delivery_id)
            )
        ).one_or_none()
    if row is None:
        return "missing"
    delivery, incident, monitor = row
    if delivery.channel != "email":
        return "unsupported"
    if delivery.status == "delivered":
        return "already_delivered"
    common = {
        "delivery_id": delivery.id,
        "deduplication_key": delivery.deduplication_key,
        "destination": delivery.destination,
        "monitor_name": monitor.name,
        "opened_at": incident.opened_at,
    }
    if delivery.event_type == "incident_opened":
        return OpeningEmailContext(
            **common,
            cause_category=incident.cause_category,
        )
    if delivery.event_type != "incident_recovered":
        return "unsupported"
    if incident.status != "resolved" or incident.resolved_at is None:
        return "invalid_lifecycle"
    async with session_factory() as session:
        opening_delivery_id = await session.scalar(
            select(NotificationDelivery.id).where(
                NotificationDelivery.incident_id == incident.id,
                NotificationDelivery.channel == "email",
                NotificationDelivery.event_type == "incident_opened",
            )
        )
    if opening_delivery_id is None:
        return "invalid_lifecycle"
    return RecoveryEmailContext(
        **common,
        resolved_at=incident.resolved_at,
    )


async def deliver_notification(
    delivery_id: str | UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    sender: EmailSender = send_smtp_message,
    settings: Settings | None = None,
) -> str:
    try:
        parsed_delivery_id = UUID(str(delivery_id))
    except ValueError:
        logger.warning("email_delivery_invalid_identifier")
        return "missing"

    context = await _load_email_context(
        parsed_delivery_id,
        session_factory=session_factory,
    )
    if isinstance(context, str):
        return context

    current_settings = settings or load_settings()
    if isinstance(context, OpeningEmailContext):
        message = build_opening_email(context, current_settings)
    else:
        message = build_recovery_email(context, current_settings)
    try:
        provider_message_id = sender(message, current_settings)
    except (OSError, smtplib.SMTPException):
        logger.warning(
            "email_delivery_provider_failure",
            extra={"delivery_id": str(context.delivery_id)},
        )
        return "provider_failed"

    delivered_at = datetime.now(timezone.utc)
    async with session_factory() as session:
        async with session.begin():
            delivery = await session.scalar(
                select(NotificationDelivery)
                .where(NotificationDelivery.id == context.delivery_id)
                .with_for_update()
            )
            if delivery is None:
                return "missing"
            if delivery.status == "delivered":
                return "already_delivered"
            delivery.status = "delivered"
            delivery.delivered_at = delivered_at
            delivery.provider_message_id = provider_message_id
    return "delivered"

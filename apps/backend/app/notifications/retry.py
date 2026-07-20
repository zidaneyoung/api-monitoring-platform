from dataclasses import dataclass
import smtplib
from uuid import UUID

from app.notifications.dispatcher import enqueue_notification_delivery


MAX_EMAIL_ATTEMPTS = 5
BASE_RETRY_DELAY_SECONDS = 60
MAX_RETRY_DELAY_SECONDS = 3600
RATE_LIMIT_SMTP_CODES = frozenset({421})


@dataclass(frozen=True)
class ProviderFailure:
    temporary: bool
    error_code: str
    safe_message: str


def _response_code(error: smtplib.SMTPException) -> int | None:
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        codes = [
            int(response[0])
            for response in error.recipients.values()
            if response and isinstance(response[0], int)
        ]
        if not codes:
            return None
        return min(codes)
    if isinstance(error, smtplib.SMTPResponseException):
        return int(error.smtp_code)
    return None


def classify_provider_failure(error: Exception) -> ProviderFailure:
    if isinstance(error, smtplib.SMTPException):
        if isinstance(error, smtplib.SMTPServerDisconnected):
            return ProviderFailure(
                temporary=True,
                error_code="smtp_unavailable",
                safe_message="SMTP provider is temporarily unavailable.",
            )
        code = _response_code(error)
        if code in RATE_LIMIT_SMTP_CODES:
            return ProviderFailure(
                temporary=True,
                error_code="smtp_rate_limited",
                safe_message="SMTP provider requested a later retry.",
            )
        if code is not None and 400 <= code < 500:
            return ProviderFailure(
                temporary=True,
                error_code="smtp_temporary",
                safe_message="SMTP provider reported a temporary failure.",
            )
        return ProviderFailure(
            temporary=False,
            error_code="smtp_permanent",
            safe_message="SMTP provider rejected delivery permanently.",
        )
    if isinstance(error, OSError):
        return ProviderFailure(
            temporary=True,
            error_code="smtp_unavailable",
            safe_message="SMTP provider is temporarily unavailable.",
        )
    return ProviderFailure(
        temporary=False,
        error_code="provider_permanent",
        safe_message="Email provider rejected delivery permanently.",
    )


def retry_delay_seconds(attempt_count: int) -> int:
    if attempt_count < 1:
        raise ValueError("attempt_count must be at least one")
    return min(
        BASE_RETRY_DELAY_SECONDS * (2 ** (attempt_count - 1)),
        MAX_RETRY_DELAY_SECONDS,
    )


async def schedule_notification_retry(delivery_id: UUID, countdown: int) -> None:
    await enqueue_notification_delivery(delivery_id, countdown=countdown)

import os


def get_ai_coach_allowed_emails() -> list[str]:
    configured = os.environ.get("AI_COACH_ALLOWED_EMAILS", "").strip()

    if not configured:
        return []

    return [
        email.strip().lower()
        for email in configured.split(",")
        if email.strip()
    ]


def is_ai_coach_enabled(email: str | None) -> bool:
    if not email:
        return False

    allowed = get_ai_coach_allowed_emails()
    if not allowed:
        return False

    return email.strip().lower() in allowed

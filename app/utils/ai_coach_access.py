import os

DEFAULT_AI_COACH_ALLOWED_EMAILS = ["patelnisarg1309@gmail.com"]


def get_ai_coach_allowed_emails() -> list[str]:
    configured = os.environ.get("AI_COACH_ALLOWED_EMAILS", "").strip()

    if configured:
        return [
            email.strip().lower()
            for email in configured.split(",")
            if email.strip()
        ]

    return [email.lower() for email in DEFAULT_AI_COACH_ALLOWED_EMAILS]


def is_ai_coach_enabled(email: str | None) -> bool:
    if not email:
        return False

    return email.strip().lower() in get_ai_coach_allowed_emails()

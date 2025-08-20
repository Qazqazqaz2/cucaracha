import secrets

def generate_session_name(phone: str | None = None, user_id: int | None = None, username: str | None = None) -> str:
    if username:
        return f"acc_{username.lower()}"
    if user_id:
        return f"acc_{user_id}"
    if phone:
        return f"acc_{phone.strip('+')}"
    return f"acc_{secrets.token_hex(4)}"

from config.settings import ADMIN_IDS

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
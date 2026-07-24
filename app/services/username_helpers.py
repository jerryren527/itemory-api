import re
import secrets

from ..models import CustomUser


def _slugify_base(base: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", (base or "").lower())
    slug = slug[:20]
    return slug or "user"


def generate_unique_username(base: str) -> str:
    """
    Slugify `base` (a display name or email local-part) into a candidate
    username, appending a numeric suffix until it's unique. Falls back to a
    random suffix if incrementing gets unlucky (kept bounded, not infinite).
    """
    slug = _slugify_base(base)

    if not CustomUser.objects.filter(username=slug).exists():
        return slug

    for suffix in range(1, 10000):
        candidate = f"{slug}{suffix}"
        if not CustomUser.objects.filter(username=candidate).exists():
            return candidate

    return f"{slug}{secrets.token_hex(4)}"

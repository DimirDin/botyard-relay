"""Basic profanity filter for free-text phrase/guess input.

Deliberately simple word-list + normalization approach for MVP. Drawing moderation is
explicitly out of scope for now (documented in PROJECT_CONTEXT.md as a later phase).
"""
from __future__ import annotations

import re

# Minimal seed list of common Russian/English profanity roots. This is intentionally
# NOT exhaustive — it's a basic first line of defense, easy to extend later with a
# proper library (e.g. better-profanity) or an external moderation API.
_BANNED_ROOTS = [
    "хуй", "хуе", "хуя", "пизд", "ебат", "еба", "ёбан", "ебал", "бля",
    "муда", "мудак", "сука", "сучк", "гандон", "залуп", "долбоеб", "долбоёб",
    "fuck", "shit", "bitch", "cunt", "asshole", "dick", "nigger", "faggot",
]

_LEET_MAP = str.maketrans({
    "0": "о", "1": "i", "3": "e", "4": "a", "@": "a", "$": "s", "!": "i",
})


def _normalize(text: str) -> str:
    text = text.lower().translate(_LEET_MAP)
    text = re.sub(r"[^a-zа-яё0-9]+", "", text)
    return text


def contains_profanity(text: str) -> bool:
    normalized = _normalize(text)
    return any(root in normalized for root in _BANNED_ROOTS)


def moderate(text: str) -> tuple[bool, str]:
    """Returns (is_allowed, reason_if_rejected)."""
    if not text or not text.strip():
        return False, "Пустое сообщение — напиши что-нибудь."
    if len(text) > 300:
        return False, "Слишком длинно — уложись в 300 символов."
    if contains_profanity(text):
        return False, "Давай без мата, это увидят все в чате."
    return True, ""

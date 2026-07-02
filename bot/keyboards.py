from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.config import settings


def join_lobby_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Я в деле", callback_data=f"join:{session_id}")]]
    )


def forward_story_keyboard(entry_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Переслать историю",
                    switch_inline_query=f"story_{entry_id}",
                )
            ]
        ]
    )


def draw_webapp_keyboard(session_id: str, round_number: int) -> InlineKeyboardMarkup:
    url = f"{settings.webapp_url}/?sid={session_id}&round={round_number}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Рисовать", web_app=WebAppInfo(url=url))]]
    )

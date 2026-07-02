"""Phase 3 (stub, minimal by design): Telegram Stars monetization hooks.

Two paid options are stubbed:
  - "themed starter phrase pack" -- would unlock curated seed phrases instead of
    free-text (not implemented beyond the invoice stub; free-text remains the default).
  - "early replay" -- would let the lobby owner re-roll/replay immediately instead of
    waiting for a new /relay cooldown (no cooldown exists yet, so this is a pure stub).

Neither is wired into the game loop; this just proves the invoice plumbing works so a
future session can flesh out the actual paid perks.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

router = Router(name="monetization")

STARTER_PACK_PAYLOAD = "starter_pack"
EARLY_REPLAY_PAYLOAD = "early_replay"


@router.message(Command("shop"))
async def cmd_shop(message: Message) -> None:
    await message.answer_invoice(
        title="Тематический набор фраз",
        description="Разблокирует набор тематических стартовых фраз для игры (скоро).",
        payload=STARTER_PACK_PAYLOAD,
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label="Набор фраз", amount=50)],
    )


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(lambda m: m.successful_payment is not None)
async def process_successful_payment(message: Message) -> None:
    payload = message.successful_payment.invoice_payload
    if payload == STARTER_PACK_PAYLOAD:
        await message.answer("Спасибо! Набор фраз пока в разработке — скоро появится в игре.")
    elif payload == EARLY_REPLAY_PAYLOAD:
        await message.answer("Спасибо! Функция раннего реванша пока в разработке.")
    else:
        await message.answer("Спасибо за покупку!")

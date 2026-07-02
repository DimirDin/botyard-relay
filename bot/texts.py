"""All user-facing strings, in Russian, kept in one place for easy editing/translation."""

LOBBY_OPEN = (
    "🎨 Кривой телефон запускается!\n"
    "Нажми «Я в деле», чтобы участвовать. Нужно минимум 3 игрока, максимум 8.\n"
    "Сбор длится {seconds} секунд."
)
LOBBY_ALREADY_RUNNING = "игра уже идёт"
LOBBY_JOINED = "Записал(а) тебя, {name}! Игроков сейчас: {count}."
LOBBY_NEED_DM = (
    "Чтобы играть, сначала напиши мне в личку — иначе не смогу прислать тебе задания.\n"
    "{deep_link}"
)
LOBBY_TOO_FEW = "Маловато людей, попробуйте ещё раз"
LOBBY_FULL = "Уже набрали максимум игроков."

SEED_PROMPT = (
    "Игра началась! Придумай любую фразу — с неё начнётся твоя книга «Кривого телефона». "
    "Просто напиши её мне сюда."
)
SEED_ACCEPTED = "Принято! Жду остальных игроков."

DRAW_PROMPT = "Нарисуй фразу: «{phrase}»"
GUESS_PROMPT = "Угадай текстом, что здесь нарисовано, и опиши это фразой."

ROUND_ANNOUNCE_GROUP = "Раунд {round}/{max_round} начался, всем отправлены новые задания в личку."
SUBMIT_ACCEPTED = "Принято! Жду остальных."
SUBMIT_DUPLICATE = "Ты уже отправил(а) ход в этом раунде, жди остальных."

MODERATION_REJECTED = "Давай без мата, это увидят все в чате."

GAME_STARTED_GROUP = "Игра началась! Участники ({count}): {names}\nКаждому пишу в личку — жду первые фразы (раунды: {max_round})."

CHAIN_CARD_HEADER = "📖 Книга: {owner}"
CHAIN_ROUND_TEXT = "Раунд {round} (текст): {content}"
CHAIN_ROUND_DRAWING = "Раунд {round} (рисунок) 🖼"
CHAIN_ROUND_SKIPPED = "Раунд {round}: (пропущено)"

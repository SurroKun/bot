# bot.py — Компактна, ВИПРАВЛЕНА версія (aiogram 3.22+)
import asyncio
import random
import json
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage  # ← ДОДАЙ ЦЕЙ РЯДОК!
from aiogram.types import (
    Message, CallbackQuery, PreCheckoutQuery, LabeledPrice,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==================== НАЛАШТУВАННЯ ====================
TOKEN = "8535159174:AAFVhYRZIjj9CM03ud72foAoPPwv2RxVSdA"
# ==================== АДМІНКА ====================
ADMIN_ID = [202322435, 7807230898]  # ← заміни на свій Telegram ID (можна кілька через кому)
# ADMIN_ID = [6027893162, 123456789]   # якщо кілька адмінів

def is_admin(user_id: int) -> bool:
    if isinstance(ADMIN_ID, list):
        return user_id in ADMIN_ID
    return user_id == ADMIN_ID
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Пам'ять
vip_expires: dict[int, datetime] = {}
used_photos_today: dict[int, set] = {}
last_free_spin: dict[int, str] = {}
last_free_photo: dict[int, str] = {}

VIP_DAYS = 30
VIP_SPINS = 20
VIP_PHOTOS = 25

# Фото
random_photos = [f"https://picsum.photos/seed/vip{i}/800/1200" for i in range(1, 31)]
PREVIEW_PHOTO = random_photos[0]

# Контент
CONTENT_CATALOG = {
    "hot1": {"title": "Гарячий набір #1", "price": 1, "files": random_photos[:3]},
    "hot2": {"title": "Ексклюзив #2",    "price": 1, "files": random_photos[10:15]},
}

# ==================== Клавіатури ====================
def get_main_menu(user_id: int):
    buttons = [
        [KeyboardButton(text="1 Free Spin on day")],
        [KeyboardButton(text="Tips")], #KeyboardButton(text="VIP status")],
        [KeyboardButton(text="1 Free photo on day"), KeyboardButton(text="Surprise Box for 20")],
        [KeyboardButton(text="Buy content")],
    ]
    if is_admin(user_id):
        buttons.append([KeyboardButton(text="Адмінка")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ==================== Допоміжне ====================
def vip_active(uid): 
    expires = vip_expires.get(uid, datetime(1,1,1))
    return datetime.now() < expires

# ==================== Старт ====================
@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Продовжити", callback_data="go")]
        ]
    )
    await m.answer_video(
        video=FSInputFile("hello.mp4"),
        caption="Привіт!",
        reply_markup=kb
    )

@dp.callback_query(F.data == "go")
async def go(c: CallbackQuery):
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer("Меню:", reply_markup=get_main_menu(c.from_user.id))
    await c.answer()

# ==================== Buy Content ====================
@dp.message(F.text == "Buy content")
async def buy_content(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for pid, pack in CONTENT_CATALOG.items():
        row.append(InlineKeyboardButton(
            text=f"{pack['title']} — {pack['price']}⭐", 
            callback_data=f"buy:{pid}"
        ))
        if len(row) == 2:
            kb.inline_keyboard.append(row)
            row = []
    if row: 
        kb.inline_keyboard.append(row)

    await m.answer_photo(
        photo=PREVIEW_PHOTO, 
        caption="<b>Обери контент</b>", 
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("buy:"))
async def buy_pack(c: CallbackQuery):
    pack_id = c.data.split(":")[1]
    pack = CONTENT_CATALOG[pack_id]
    await bot.send_invoice(
        chat_id=c.from_user.id,
        title=pack["title"],
        description=f"{len(pack['files'])} фото",
        payload=f"pack:{pack_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=pack["title"], amount=pack["price"])]
    )
    await c.answer("Відкриваю платіж...")

# ==================== Оплата ====================
@dp.pre_checkout_query()
async def pre(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query_id=q.id, ok=True)

# ==================== ОПЛАТА — ВИПРАВЛЕНА ВЕРСІЯ (підтримує фото + відео) ====================
@dp.message(F.successful_payment)
async def paid(m: Message):
    p = m.successful_payment.invoice_payload
    uid = m.from_user.id

    if p == "vip_30days":
        expires = datetime.now() + timedelta(days=VIP_DAYS)
        if vip_active(uid):
            expires = vip_expires[uid] + timedelta(days=VIP_DAYS)
        vip_expires[uid] = expires
        await m.answer(f"VIP активовано!\nДійсний до: {expires:%d.%m.%Y}")

    elif p == "slot_paid":
        await m.answer("Оплата пройшла! Кручу ще раз")
        d = await m.answer_dice(emoji="slot_machine")
        await asyncio.sleep(3.5)
        if d.dice.value == 64:
            await m.answer("ДЖЕКПОТ!")
            await bot.send_photo(chat_id=uid, photo=random.choice(random_photos))
        else:
            await m.answer("На жаль, цього разу без виграшу")

    elif p == "surprise_box":
        await m.answer(random.choice(["БАМ!", "Ого!", "Сюрприз!"]))
        await bot.send_photo(chat_id=uid, photo=random.choice(random_photos), caption="З коробки!")

    elif p == "random_photo_payment":
        await bot.send_photo(chat_id=uid, photo=random.choice(random_photos), caption="Дякую за Stars! Ось твоє фото")

    elif p.startswith("pack:"):
        pack_id = p.split(":")[1]
        pack = CONTENT_CATALOG.get(pack_id)
        if not pack:
            await m.answer("Пак не знайдено :(")
            return

        await m.answer(f"Ось твій пак «{pack['title']}»:")

        for item in pack["files"]:
            if isinstance(item, str):  # старий формат — просто URL або file_id
                await bot.send_photo(chat_id=uid, photo=item)
            elif isinstance(item, tuple):
                file_type, file_id = item
                if file_type == "photo":
                    await bot.send_photo(chat_id=uid, photo=file_id)
                elif file_type == "video":
                    await bot.send_video(chat_id=uid, video=file_id)
            await asyncio.sleep(0.7)

        await m.answer("Приємного перегляду!")

# ==================== Кнопки ====================
@dp.message(F.text == "VIP status")
async def vip_buy(m: Message):
    await bot.send_invoice(
        chat_id=m.from_user.id,
        title="VIP 30 днів",
        description="20 спінів + 25 фото щодня",
        payload="vip_30days",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="VIP", amount=400)]
    )

@dp.message(F.text == "Surprise Box for 20")
async def box(m: Message):
    await bot.send_invoice(
        chat_id=m.chat.id,
        title="Surprise Box",
        description="Таємний сюрприз",
        payload="surprise_box",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Box", amount=1)]
    )

@dp.message(F.text == "1 Free Spin on day")
async def slot(m: Message):
    uid, today = m.from_user.id, datetime.now().strftime("%Y-%m-%d")
    if not vip_active(uid) and last_free_spin.get(uid) == today:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Купити ще 1 спін за 10", callback_data="buy_slot")]
        ])
        await m.answer("Безкоштовний спін сьогодні вже використано!\nХочеш ще один?", reply_markup=kb)
        return
    if not vip_active(uid): 
        last_free_spin[uid] = today
    await m.answer("Кручу...")
    d = await m.answer_dice(emoji="🎰")  # ПРАВИЛЬНО!
    await asyncio.sleep(2)

    if d.dice.value == 64:
        await m.answer("JACKPOT!")
        await m.answer_photo(random.choice(random_photos))
    else:
        await m.answer("Not today")

@dp.message(F.text == "1 Free photo on day")
async def photo(m: Message):
    uid, today = m.from_user.id, datetime.now().strftime("%Y-%m-%d")
    if vip_active(uid):
        used = used_photos_today.get(uid, set())
        if len(used) >= VIP_PHOTOS:
            await m.answer("Ліміт VIP-фото на сьогодні вичерпано")
            return
        photo_url = random.choice([p for p in random_photos if p not in used])
        used_photos_today.setdefault(uid, set()).add(photo_url)
        await m.answer_photo(photo=photo_url, caption="VIP фото")
    elif last_free_photo.get(uid) != today:
        last_free_photo[uid] = today
        await m.answer_photo(photo=random.choice(random_photos), caption="Безкоштовне фото")
    else:
        await bot.send_invoice(
            chat_id=m.chat.id,
            title="Фото",
            description="За 2⭐",
            payload="random_photo_payment",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Фото", amount=2)]
        )

@dp.message(F.text == "Tips")
async def tips(m: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Підтримати", url="https://onlyfans.com/onlyfans")]
        ]
    )
    await m.answer("Дякую за підтримку!", reply_markup=kb)

@dp.callback_query(F.data == "buy_slot")  # ← ЦЬОГО НЕ БУЛО!
async def buy_extra_slot(c: CallbackQuery):
    await bot.send_invoice(
        chat_id=c.from_user.id,
        title="Додатковий спін",
        description="Ще одна спроба в слоті",
        payload="slot_paid",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Спін", amount=1)]
    )
    await c.answer("Відкриваю платіж за спін...")
    
# ==================== АДМІН-ПАНЕЛЬ — ФІНАЛЬНА, СТАБІЛЬНА ВЕРСІЯ ====================

# Файл для збереження паков (щоб не зникали після рестарту)
PACKS_FILE = "content_packs.json"

# Завантажуємо паки з файлу при запуску
def load_packs():
    if os.path.exists(PACKS_FILE):
        with open(PACKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for pid, pack in data.items():
                CONTENT_CATALOG[pid] = pack
    print(f"Завантажено {len(CONTENT_CATALOG)} паков з файлу")

# Зберігаємо паки в файл
def save_packs():
    with open(PACKS_FILE, "w", encoding="utf-8") as f:
        json.dump(CONTENT_CATALOG, f, ensure_ascii=False, indent=2)

# Стани
class AdminStates(StatesGroup):
    waiting_vip_input = State()
    add_pack_title = State()
    add_pack_price = State()
    add_pack_files = State()
    edit_pack_title = State()
    edit_pack_price = State()

# Тимчасове сховище файлів для створення пака
temp_pack_files = {}  # {admin_id: [("photo"|"video", file_id), ...]}

# Завантажуємо паки при старті
load_packs()

# — Адмін-панель
@dp.message(F.text == "Адмінка")
async def admin_panel(m: Message):
    if not is_admin(m.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="Розсилка", callback_data="admin_broadcast")],
     ##   [InlineKeyboardButton(text="Надати VIP", callback_data="admin_give_vip")],
        [InlineKeyboardButton(text="Додати пак", callback_data="admin_add_pack")],
        [InlineKeyboardButton(text="Редагувати паки", callback_data="admin_edit_pack")],
        [InlineKeyboardButton(text="Вимкнути бота", callback_data="admin_off")],
    ])
    await m.answer("Адмінка v3", reply_markup=kb)

# — Статистика
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    users = {*last_free_spin.keys(), *last_free_photo.keys(), *vip_expires.keys()}
    await c.message.edit_text(
        f"СТАТИСТИКА\n\n"
        f"Користувачів: {len(users)}\n"
        f"Активних VIP: {sum(1 for uid in vip_expires if vip_active(uid))}\n"
        f"Паків у продажу: {len(CONTENT_CATALOG)}",
        reply_markup=c.message.reply_markup
    )

# — Надати VIP
@dp.callback_query(F.data == "admin_give_vip")
async def admin_give_vip_start(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    await state.set_state(AdminStates.waiting_vip_input)
    await c.message.edit_text("Надішли: <code>ID_користувача кількість_днів</code>")

@dp.message(AdminStates.waiting_vip_input)
async def process_give_vip(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    await state.clear()
    try:
        user_id, days = map(int, m.text.split())
        expires = datetime.now() + timedelta(days=days)
        if vip_active(user_id):
            expires = vip_expires[user_id] + timedelta(days=days)
        vip_expires[user_id] = expires
        await m.answer(f"VIP видано!\nКористувач: {user_id}\nДо: {expires:%d.%m.%Y}")
    except:
        await m.answer("Неправильний формат!")

# — Додати пак
@dp.callback_query(F.data == "admin_add_pack")
async def admin_add_pack_start(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id): return
    temp_pack_files[c.from_user.id] = []
    await state.set_state(AdminStates.add_pack_title)
    await c.message.edit_text("Новий пак\n\n1 Надішли назву:")

@dp.message(AdminStates.add_pack_title)
async def pack_title(m: Message, state: FSMContext):
    await state.update_data(title=m.text.strip())
    await state.set_state(AdminStates.add_pack_price)
    await m.answer("2 Надішли ціну в Stars:")

@dp.message(AdminStates.add_pack_price, F.text.regexp(r"^\d+$"))
async def pack_price(m: Message, state: FSMContext):
    await state.update_data(price=int(m.text))
    await state.set_state(AdminStates.add_pack_files)
    await m.answer(
        "3 Надішли фото або відео\nКоли закінчиш — натисни кнопку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Завершити", callback_data="admin_pack_done")]
        ])
    )

@dp.message(AdminStates.add_pack_files, F.photo | F.video)
async def pack_add_file(m: Message):
    if m.from_user.id not in temp_pack_files: return
    file_type = "video" if m.video else "photo"
    file_id = m.video.file_id if m.video else m.photo[-1].file_id
    temp_pack_files[m.from_user.id].append((file_type, file_id))
    await m.answer(f"Додано! Всього: {len(temp_pack_files[m.from_user.id])}")

@dp.callback_query(F.data == "admin_pack_done")
async def pack_finish(c: CallbackQuery, state: FSMContext):
    if c.from_user.id not in temp_pack_files or not temp_pack_files[c.from_user.id]:
        await c.message.edit_text("Немає файлів!")
        return
    data = await state.get_data()
    new_id = f"pack_{int(datetime.now().timestamp())}"
    CONTENT_CATALOG[new_id] = {
        "title": data["title"],
        "price": data["price"],
        "files": temp_pack_files[c.from_user.id]
    }
    del temp_pack_files[c.from_user.id]
    save_packs()  # ЗБЕРІГАЄМО!
    await state.clear()
    await c.message.edit_text(
        f"Пак додано!\nНазва: {data['title']}\nЦіна: {data['price']}⭐\nФайлів: {len(CONTENT_CATALOG[new_id]['files'])}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="В адмінку", callback_data="back_to_admin")]
        ])
    )

# — Редагування паков
@dp.callback_query(F.data == "admin_edit_pack")
async def admin_edit_pack(c: CallbackQuery):
    if not CONTENT_CATALOG:
        await c.message.edit_text("Немає паков")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{v['title']} — {v['price']}⭐", callback_data=f"editmenu:{k}")]
        for k, v in CONTENT_CATALOG.items()
    ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Назад", callback_data="back_to_admin")])
    await c.message.edit_text("Обери пак:", reply_markup=kb)

@dp.callback_query(F.data.startswith("editmenu:"))
async def edit_menu(c: CallbackQuery):
    pack_id = c.data.split(":")[1]
    pack = CONTENT_CATALOG[pack_id]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Змінити назву", callback_data=f"edit_title:{pack_id}")],
        [InlineKeyboardButton(text="Змінити ціну", callback_data=f"edit_price:{pack_id}")],
        [InlineKeyboardButton(text="Видалити пак", callback_data=f"del_pack:{pack_id}")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_edit_pack")],
    ])
    await c.message.edit_text(
        f"Пак: <b>{pack['title']}</b>\nЦіна: {pack['price']}⭐\nФайлів: {len(pack['files'])}",
        reply_markup=kb, parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("edit_title:"))
async def edit_title_start(c: CallbackQuery, state: FSMContext):
    pack_id = c.data.split(":")[1]
    await state.set_state(AdminStates.edit_pack_title)
    await state.set_data({"pack_id": pack_id})
    await c.message.edit_text("Нова назва:")

@dp.message(AdminStates.edit_pack_title)
async def edit_title_done(m: Message, state: FSMContext):
    data = await state.get_data()
    CONTENT_CATALOG[data["pack_id"]]["title"] = m.text.strip()
    save_packs()
    await m.answer("Назву змінено!")
    await state.clear()

@dp.callback_query(F.data.startswith("edit_price:"))
async def edit_price_start(c: CallbackQuery, state: FSMContext):
    pack_id = c.data.split(":")[1]
    await state.set_state(AdminStates.edit_pack_price)
    await state.set_data({"pack_id": pack_id})
    await c.message.edit_text("Нова ціна:")

@dp.message(AdminStates.edit_pack_price, F.text.regexp(r"^\d+$"))
async def edit_price_done(m: Message, state: FSMContext):
    data = await state.get_data()
    CONTENT_CATALOG[data["pack_id"]]["price"] = int(m.text)
    save_packs()
    await m.answer("Ціну змінено!")
    await state.clear()

@dp.callback_query(F.data.startswith("del_pack:"))
async def delete_pack(c: CallbackQuery):
    pack_id = c.data.split(":")[1]
    title = CONTENT_CATALOG[pack_id]["title"]
    del CONTENT_CATALOG[pack_id]
    save_packs()
    await c.message.edit_text(f"Пак <b>{title}</b> видалено!", parse_mode="HTML")

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(c: CallbackQuery):
    await admin_panel(c.message)

# — Вимкнення
@dp.callback_query(F.data == "admin_off")
async def admin_off(c: CallbackQuery):
    if not is_admin(c.from_user.id): return
    await c.message.edit_text("Бот вимкнено")
    await dp.stop_polling()
    await bot.session.close()

# ==================== Запуск ====================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
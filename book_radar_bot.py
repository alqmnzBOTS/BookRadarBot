import os
import re
import logging
import httpx
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    URLInputFile
)

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Временное хранилище данных
user_data = {}
saved_books = {}

# Предопределенные жанры
GENRES = [
    "Фэнтези", "Нон-фикшн", "Психология", "Научная фантастика",
    "Детектив", "Роман", "Исторический", "Бизнес", "Саморазвитие",
    "Биография", "Классика", "Триллер", "Ужасы", "Поэзия"
]


# Классы состояний
class BookSearch(StatesGroup):
    waiting_for_title = State()
    waiting_for_author = State()


# Инициализация пользователя
def init_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "genres": [],
            "notifications": True,
            "current_search": {},
            "genre_message_id": None  # Для отслеживания сообщения с выбором жанров
        }
    if user_id not in saved_books:
        saved_books[user_id] = []


# Клавиатуры
def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(text="Новинки за последнюю неделю"),
        types.KeyboardButton(text="Поиск книги")
    )
    builder.row(
        types.KeyboardButton(text="Сохраненные книги"),
        types.KeyboardButton(text="Настройки")
    )
    return builder.as_markup(resize_keyboard=True)


def settings_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Изменить жанры",
        callback_data="change_genres")
    )
    builder.row(InlineKeyboardButton(
        text="Включить/выключить уведомления",
        callback_data="toggle_notifications")
    )
    return builder.as_markup()


def genres_keyboard(selected_genres):
    builder = InlineKeyboardBuilder()
    for genre in GENRES:
        status = "✅" if genre in selected_genres else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {genre}",
            callback_data=f"genre_{genre}")
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="Готово",
        callback_data="genres_done")
    )
    return builder.as_markup()


def save_book_keyboard(book_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="💾 Сохранить книгу",
        callback_data=f"save_{book_id}")
    )
    return builder.as_markup()


# ЗАГЛУШКА для API новинок (пользователь может заменить на реальный API)
async def get_new_books_api(genres):
    """ЗАМЕНИТЕ ЭТУ ФУНКЦИЮ НА РЕАЛЬНЫЙ ПАРСИНГ ИЛИ API ВАШЕГО СЕРВИСА"""
    logger.info("Используется заглушка для новинок. Замените на реальный API!")

    # Пример данных для демонстрации
    books = []
    for i, genre in enumerate(genres[:3]):
        books.append({
            "id": f"stub_{i}",
            "title": f"Пример новинки в жанре {genre}",
            "author": "Известный автор",
            "description": f"Это демонстрационная книга в жанре {genre}. В реальном боте здесь будет настоящее описание.",
            "cover_url": "",
            "price": f"{399 + i * 50} ₽",
            "source_url": "https://example.com"
        })
    return books


# ЗАГЛУШКА для поиска книг (пользователь может заменить на реальный API)
async def search_books_api(query, author=None):
    """ЗАМЕНИТЕ ЭТУ ФУНКЦИЮ НА РЕАЛЬНЫЙ ПОИСК ВАШЕГО СЕРВИСА"""
    logger.info(f"Используется заглушка для поиска: {query}, автор: {author}")

    # Пример данных для демонстрации
    books = []
    for i in range(3):
        books.append({
            "id": f"search_{i}",
            "title": f"{query} - пример результата {i + 1}",
            "author": author or "Автор неизвестен",
            "description": f"Это демонстрационный результат поиска. В реальном боте здесь будет настоящее описание книги '{query}'.",
            "cover_url": "",
            "price": f"{299 + i * 100} ₽",
            "source_url": "https://example.com"
        })
    return books


# Поиск новинок (заглушка)
async def get_new_books(genres):
    return await get_new_books_api(genres)


# Форматирование сообщения о книге
def format_book_info(book):
    return (
        f"📚 *{book['title']}*\n"
        f"✍️ {book['author']}\n"
        f"💰 {book.get('price', 'Цена не указана')}\n"
        f"📝 {book['description']}\n"
        f"🔗 [Ссылка на источник]({book['source_url']})"
    )


# Обработчики
@dp.message(Command("start"))
async def cmd_start(message: Message):
    init_user(message.from_user.id)

    welcome_text = (
        "📖 *Добро пожаловать в Актуальный Книжный Радар!*\n\n"
        "Я помогу вам быть в курсе последних книжных новинок по вашим любимым жанрам. "
        "Вы можете настроить предпочтения, получать персонализированные подборки "
        "и сохранять понравившиеся книги.\n\n"
        "⚠️ *Важно:* Этот бот создан для некоммерческого использования. "
        "Разработчик: @alqmnz\n\n"
        "Выберите действие:"
    )

    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


@dp.message(F.text == "Новинки за последнюю неделю")
async def new_books_handler(message: Message):
    user_id = message.from_user.id
    init_user(user_id)

    if not user_data[user_id]["genres"]:
        await message.answer(
            "Сначала выберите жанры в настройках!",
            reply_markup=main_keyboard()
        )
        return

    await message.answer("🔍 Ищу новинки по вашим жанрам...")

    try:
        books = await get_new_books(user_data[user_id]["genres"])
        if not books:
            await message.answer("Не найдено новинок по вашим жанрам 😔")
            return

        for book in books:
            msg = format_book_info(book)

            if book.get("cover_url"):
                try:
                    await message.answer_photo(
                        URLInputFile(book["cover_url"]),
                        caption=msg,
                        parse_mode="Markdown",
                        reply_markup=save_book_keyboard(book["id"])
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки обложки: {e}")
                    await message.answer(
                        msg,
                        parse_mode="Markdown",
                        reply_markup=save_book_keyboard(book["id"])
                    )
            else:
                await message.answer(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=save_book_keyboard(book["id"])
                )

    except Exception as e:
        logger.error(f"New books error: {e}")
        await message.answer("Ошибка при поиске новинок. Попробуйте позже.")


@dp.message(F.text == "Поиск книги")
async def search_book_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    init_user(user_id)

    await state.set_state(BookSearch.waiting_for_title)
    await message.answer(
        "🔍 Введите название книги:",
        reply_markup=types.ReplyKeyboardRemove()
    )


@dp.message(BookSearch.waiting_for_title)
async def process_book_title(message: Message, state: FSMContext):
    user_id = message.from_user.id
    title = message.text.strip()

    if len(title) < 3:
        await message.answer("Слишком короткое название. Попробуйте еще раз:")
        return

    # Сохраняем поисковый запрос
    user_data[user_id]["current_search"] = {
        "title": title,
        "books": []
    }

    await state.set_state(BookSearch.waiting_for_author)
    await message.answer(
        "✍️ Введите автора (если знаете, иначе нажмите /skip):",
        reply_markup=types.ForceReply(selective=True)
    )


@dp.message(Command("skip"))
@dp.message(BookSearch.waiting_for_author)
async def process_book_author(message: Message, state: FSMContext):
    user_id = message.from_user.id
    author = message.text.strip() if message.text != "/skip" else None

    search_data = user_data[user_id]["current_search"]
    title = search_data["title"]

    await message.answer(f"🔍 Ищу книги: {title}" + (f" ({author})" if author else ""))

    try:
        books = await search_books_api(title, author)
        if not books:
            await message.answer("Книги не найдены 😔", reply_markup=main_keyboard())
            await state.clear()
            return

        # Сохраняем книги для последующего сохранения
        user_data[user_id]["current_search"]["books"] = books

        # Если нашли несколько книг
        for book in books:
            msg = format_book_info(book)

            if book.get("cover_url"):
                try:
                    await message.answer_photo(
                        URLInputFile(book["cover_url"]),
                        caption=msg,
                        parse_mode="Markdown",
                        reply_markup=save_book_keyboard(book["id"])
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки обложки: {e}")
                    await message.answer(
                        msg,
                        parse_mode="Markdown",
                        reply_markup=save_book_keyboard(book["id"])
                    )
            else:
                await message.answer(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=save_book_keyboard(book["id"])
                )

    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.answer("Ошибка при поиске книг. Попробуйте позже.")

    await state.clear()
    await message.answer("Поиск завершен!", reply_markup=main_keyboard())


@dp.message(F.text == "Сохраненные книги")
async def saved_books_handler(message: Message):
    user_id = message.from_user.id
    init_user(user_id)

    if not saved_books.get(user_id) or not saved_books[user_id]:
        await message.answer("У вас нет сохраненных книг.")
        return

    await message.answer("📚 Ваши сохраненные книги:")

    for i, book in enumerate(saved_books[user_id], 1):
        msg = (
            f"{i}. *{book['title']}*\n"
            f"✍️ Автор: {book['author']}\n"
            f"🔗 [Ссылка на книгу]({book.get('source_url', 'https://example.com')})"
        )
        await message.answer(msg, parse_mode="Markdown")


@dp.message(F.text == "Настройки")
async def settings_handler(message: Message):
    user_id = message.from_user.id
    init_user(user_id)

    status = "✅ включены" if user_data[user_id]["notifications"] else "❌ отключены"
    genres = ", ".join(user_data[user_id]["genres"]) if user_data[user_id]["genres"] else "не выбраны"

    text = (
        "⚙️ *Настройки*\n\n"
        f"🔔 Уведомления: {status}\n"
        f"📚 Жанры: {genres}\n\n"
        "Выберите действие:"
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=settings_keyboard())


@dp.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    user_id = callback.from_user.id
    init_user(user_id)

    user_data[user_id]["notifications"] = not user_data[user_id]["notifications"]
    status = "включены" if user_data[user_id]["notifications"] else "отключены"

    await callback.answer(f"Уведомления {status}!")
    # Обновляем клавиатуру настроек
    await callback.message.edit_reply_markup(reply_markup=settings_keyboard())


@dp.callback_query(F.data == "change_genres")
async def change_genres(callback: CallbackQuery):
    user_id = callback.from_user.id
    init_user(user_id)

    # Отправляем сообщение с клавиатурой выбора жанров
    sent_message = await callback.message.answer(
        "📚 Выберите интересующие жанры:",
        reply_markup=genres_keyboard(user_data[user_id]["genres"])
    )

    # Сохраняем ID сообщения для последующего редактирования
    user_data[user_id]["genre_message_id"] = sent_message.message_id
    await callback.answer()


@dp.callback_query(F.data.startswith("genre_"))
async def toggle_genre(callback: CallbackQuery):
    user_id = callback.from_user.id
    genre = callback.data.split("_", 1)[1]

    if genre in user_data[user_id]["genres"]:
        user_data[user_id]["genres"].remove(genre)
    else:
        user_data[user_id]["genres"].append(genre)

    # Редактируем сообщение с выбором жанров
    message_id = user_data[user_id].get("genre_message_id")
    if message_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback.message.chat.id,
                message_id=message_id,
                reply_markup=genres_keyboard(user_data[user_id]["genres"])
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")

    await callback.answer()


@dp.callback_query(F.data == "genres_done")
async def genres_done(callback: CallbackQuery):
    user_id = callback.from_user.id
    count = len(user_data[user_id]["genres"])

    # Удаляем сообщение с выбором жанров
    message_id = user_data[user_id].get("genre_message_id")
    if message_id:
        try:
            await bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=message_id
            )
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")
        user_data[user_id]["genre_message_id"] = None

    await callback.message.answer(
        f"✅ Выбрано жанров: {count}",
        reply_markup=main_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("save_"))
async def save_book(callback: CallbackQuery):
    user_id = callback.from_user.id
    book_id = callback.data.split("_", 1)[1]

    # Ищем книгу в текущем поиске
    current_books = user_data[user_id]["current_search"].get("books", [])
    book_to_save = next((b for b in current_books if b["id"] == book_id), None)

    # Или в новинках
    if not book_to_save:
        books = await get_new_books(user_data[user_id]["genres"])
        book_to_save = next((b for b in books if b["id"] == book_id), None)

    if not book_to_save:
        await callback.answer("Книга не найдена 😔")
        return

    # Сохраняем книгу
    if book_to_save not in saved_books[user_id]:
        saved_books[user_id].append(book_to_save)
        await callback.answer("✅ Книга сохранена!")
    else:
        await callback.answer("❌ Книга уже сохранена")


# Запуск бота
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    logger.info("Бот запущен")
    asyncio.run(main())

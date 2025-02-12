
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)
from geopy.geocoders import Nominatim
import requests
import sqlite3
from datetime import datetime
import logging


TOKEN = "7817341523:AAFgMhThFwSZ0YJncnXvNcpY_brD8IiQqXU"
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

conn = sqlite3.connect('prayer_bot.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (chat_id INTEGER PRIMARY KEY, city TEXT, latitude REAL, longitude REAL, method INTEGER)''')
conn.commit()

# Функции
async def get_prayer_times(lat: float, lon: float, method: int = 2) -> dict:
    today = datetime.today().strftime("%d-%m-%Y")
    url = f"http://api.aladhan.com/v1/timings/{today}?latitude={lat}&longitude={lon}&method={method}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def save_user(chat_id: int, city: str = None, lat: float = None, lon: float = None, method: int = 2):
    cursor.execute("REPLACE INTO users VALUES (?, ?, ?, ?, ?)", (chat_id, city, lat, lon, method))
    conn.commit()

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [KeyboardButton("🌆 Город"), KeyboardButton("📍 Отправить местоположение", request_location=True)],
        [KeyboardButton("⚙ Настройки"), KeyboardButton("❓ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text(
        "Ас-саляму алейкум! Я бот для определения времени намаза.\nВыберите действие:",
        reply_markup=reply_markup
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    save_user(update.message.chat_id, lat=lat, lon=lon)
    await send_prayer_times(update, lat, lon)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🌆 Город":
        await update.message.reply_text("Введите название города (например, Душанбе):")
    elif text == "⚙ Настройки":
        await show_settings(update)
    elif text == "❓ Помощь":
        await update.message.reply_text("Как использовать:\n1. Выберите город/местоположение\n2. Получите время намаза!")
    else:
        try:
            geolocator = Nominatim(user_agent="prayer_bot")
            location = geolocator.geocode(text)
            if location:
                save_user(update.message.chat_id, city=text, lat=location.latitude, lon=location.longitude)
                await send_prayer_times(update, location.latitude, location.longitude)
            else:
                await update.message.reply_text("Город не найден! Попробуйте еще раз.")
        except Exception as e:
            logging.error(e)
            await update.message.reply_text("Ошибка! Пожалуйста, используйте кнопки.")

async def send_prayer_times(update: Update, lat: float, lon: float):
    data = await get_prayer_times(lat, lon)
    if data and data["code"] == 200:
        timings = data['data']['timings']
        text = (
            f"🕌 Время намаза сегодня:\n"
            f"Фаджр: {timings['Fajr']}\n"
            f"Зухр: {timings['Dhuhr']}\n"
            f"Аср: {timings['Asr']}\n"
            f"Магриб: {timings['Maghrib']}\n"
            f"Иша: {timings['Isha']}"
        )
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("Ошибка получения данных!")

async def show_settings(update: Update):
    keyboard = [
        [InlineKeyboardButton("Метод расчета", callback_data='method')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Настройки:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'method':
        methods = [
            [InlineKeyboardButton("Мекка (Umm al-Qura)", callback_data='method_4')],
            [InlineKeyboardButton("Дубай (ISNA)", callback_data='method_2')]
        ]
        reply_markup = InlineKeyboardMarkup(methods)
        await query.edit_message_text("Выберите метод расчета:", reply_markup=reply_markup)
    elif query.data.startswith('method_'):
        new_method = int(query.data.split('_')[1])
        cursor.execute("UPDATE users SET method = ? WHERE chat_id = ?", (new_method, query.message.chat_id))
        conn.commit()
        await query.edit_message_text("Метод расчета успешно изменен!")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()


    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

   
    app.run_polling()
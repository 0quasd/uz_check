# check_tickets.py
import requests
import os
import logging
import sys

# --- Налаштування ---
# Ці змінні будуть зчитуватися з секретів GitHub
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Параметри пошуку квитків
STATION_FROM_CODE = '2200300'  # Код станції Хмельницький
STATION_TO_CODE = '2218214'    # Код станції Лазещина
DEPARTURE_DATE = '2025-06-29'  # Дата, яку ви шукаєте (РРРР-ММ-ДД)
MIN_SEATS_REQUIRED = 8         # Мінімальна кількість місць
SEAT_TYPE_LETTER = 'К'         # "К" - Купе, "Л" - Люкс, "П" - Плацкарт

# Налаштування логування для GitHub Actions
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_telegram_message(message):
    """Надсилає повідомлення в Telegram."""
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("TELEGRAM_BOT_TOKEN або TELEGRAM_CHAT_ID не встановлено. Повідомлення не може бути надіслано.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("Повідомлення успішно надіслано в Telegram.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Помилка надсилання повідомлення в Telegram: {e}")

def check_uz_tickets():
    """Перевіряє наявність квитків на сайті Укрзалізниці."""
    search_url = "https://booking.uz.gov.ua/train_search/"
    
    # Додаємо заголовок User-Agent, щоб імітувати запит від реального браузера
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    data = {
        'from': STATION_FROM_CODE,
        'to': STATION_TO_CODE,
        'date': DEPARTURE_DATE,
        'time': '00:00'
    }

    try:
        logging.info(f"Надсилаю запит до УЗ: {STATION_FROM_CODE} -> {STATION_TO_CODE} на {DEPARTURE_DATE}")
        # Передаємо в запит оновлені заголовки
        response = requests.post(search_url, headers=headers, data=data)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get('error') or not api_data.get('data', {}).get('list'):
            logging.info("Потягів на заданому напрямку чи дату не знайдено.")
            return

        found_tickets = []
        for train in api_data['data']['list']:
            for seat_type in train['types']:
                if seat_type['letter'] == SEAT_TYPE_LETTER and seat_type['places'] >= MIN_SEATS_REQUIRED:
                    message = (
                        f"🎉 **Знайдено квитки!** 🎉\n\n"
                        f"**Маршрут:** {train['from']['station']} -> {train['to']['station']}\n"
                        f"**Потяг:** `{train['num']}`\n"
                        f"**Дата відправлення:** {train['from']['date']}\n"
                        f"**Час:** {train['from']['time']} -> {train['to']['time']}\n"
                        f"**Тип місць:** Купе ({SEAT_TYPE_LETTER})\n"
                        f"**Знайдено вільних місць:** *{seat_type['places']}* (потрібно {MIN_SEATS_REQUIRED})"
                    )
                    found_tickets.append(message)

        if found_tickets:
            full_message = "\n\n---\n\n".join(found_tickets)
            send_telegram_message(full_message)
        else:
            logging.info(f"Квитків не знайдено. Тип: Купе ({SEAT_TYPE_LETTER}), Кількість: {MIN_SEATS_REQUIRED}. Продовжую пошук...")

    except requests.exceptions.RequestException as e:
        logging.error(f"Помилка запиту до API УЗ: {e}")
    except ValueError as e:
        logging.error(f"Помилка розбору відповіді від API УЗ: {e}. Можливо, змінилася структура API.")
    except Exception as e:
        logging.error(f"Сталася невідома помилка: {e}")


if __name__ == "__main__":
    if not all([BOT_TOKEN, CHAT_ID]):
        print("ПОМИЛКА: Необхідно встановити змінні середовища TELEGRAM_BOT_TOKEN та TELEGRAM_CHAT_ID.", file=sys.stderr)
        sys.exit(1)
    check_uz_tickets()

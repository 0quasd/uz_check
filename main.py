import logging
import os
import requests
import sys

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- Завантаження конфігурації з GitHub Secrets (змінних середовища) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
STATION_FROM_NAME = os.getenv("STATION_FROM_NAME")
STATION_TO_NAME = os.getenv("STATION_TO_NAME")
STATION_FROM_CODE = os.getenv("STATION_FROM_CODE")
STATION_TO_CODE = os.getenv("STATION_TO_CODE")
DEPARTURE_DATE = os.getenv("DEPARTURE_DATE")

# --- Налаштування логування ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_telegram_message(message):
    """Надсилає повідомлення в Telegram."""
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("BOT_TOKEN або CHAT_ID не знайдено.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Повідомлення успішно надіслано в Telegram.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Помилка надсилання повідомлення в Telegram: {e}")

def check_for_trains():
    """
    Перевіряє наявність потягів. Якщо знайдено, надсилає сповіщення.
    """
    search_url = f"https://booking.uz.gov.ua/train-search/{STATION_FROM_CODE}/{STATION_TO_CODE}/?date={DEPARTURE_DATE}&time=00:00&by_route=1"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = None
    try:
        # У середовищі GitHub Actions шлях до драйвера зазвичай встановлюється автоматично
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(search_url)
        
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.results-list-item"))
        )
        
        logging.info("!!! ЗНАЙДЕНО ПОТЯГ !!!")
        alarm_message = (
            f"🚨 *УВАГА! З'ЯВИВСЯ ПОТЯГ!* 🚨\n\n"
            f"Маршрут: *{STATION_FROM_NAME} → {STATION_TO_NAME}*\n"
            f"Дата: *{DEPARTURE_DATE}*\n\n"
            f"*[ТЕРМІНОВО ПЕРЕВІРЯЙТЕ САЙТ](https://booking.uz.gov.ua/)*"
        )
        send_telegram_message(alarm_message)

    except TimeoutException:
        logging.info("Потяги на маршруті не знайдено. Все спокійно.")
    except Exception as e:
        logging.error(f"Сталася помилка під час перевірки: {e}")
        send_telegram_message(f"❌ *Помилка в роботі бота!*\n\n`{e}`")
    finally:
        if driver:
            driver.quit()

def main():
    """Головна функція запуску."""
    if not all([BOT_TOKEN, CHAT_ID, STATION_FROM_CODE, STATION_TO_CODE, DEPARTURE_DATE]):
        logging.error("Критична помилка: не всі секрети (змінні середовища) задані.")
        sys.exit(1) # Завершуємо роботу з помилкою

    logging.info(f"Запуск перевірки: {STATION_FROM_NAME} -> {STATION_TO_NAME} на {DEPARTURE_DATE}")
    check_for_trains()
    logging.info("Перевірку завершено.")

if __name__ == "__main__":
    main()

import logging
import time
import os
import requests

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- Завантаження конфігурації з .env файлу ---
load_dotenv()

# --- Налаштування Telegram ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- Параметри пошуку квитків ---
STATION_FROM_NAME = os.getenv("STATION_FROM_NAME")
STATION_TO_NAME = os.getenv("STATION_TO_NAME")
STATION_FROM_CODE = os.getenv("STATION_FROM_CODE")
STATION_TO_CODE = os.getenv("STATION_TO_CODE")
DEPARTURE_DATE = os.getenv("DEPARTURE_DATE")

# --- Інтервали перевірки (з перетворенням в число) ---
try:
    SEARCH_INTERVAL_SECONDS = int(os.getenv("SEARCH_INTERVAL_SECONDS", 120))
    ALARM_INTERVAL_SECONDS = int(os.getenv("ALARM_INTERVAL_SECONDS", 5))
except (TypeError, ValueError):
    logging.error("Невірні значення для інтервалів у .env файлі. Використовую стандартні.")
    SEARCH_INTERVAL_SECONDS = 120
    ALARM_INTERVAL_SECONDS = 5

# --- Налаштування логування ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_telegram_message(message):
    """Надсилає повідомлення в Telegram."""
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
    Перевіряє наявність потягів на сайті booking.uz.gov.ua.
    Повертає True, якщо знайдено хоча б один потяг, інакше False.
    """
    search_url = f"https://booking.uz.gov.ua/train-search/{STATION_FROM_CODE}/{STATION_TO_CODE}/?date={DEPARTURE_DATE}&time=00:00&by_route=1"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage") # Важливо для роботи в Docker/Linux
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
    
    driver = None
    try:
        # Selenium 4+ автоматично керує драйверами, якщо вони є в PATH.
        # Це набагато краще, ніж жорстко прописувати шлях.
        service = ChromeService() 
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(search_url)
        
        # Чекаємо до 20 секунд на появу хоча б однієї картки потяга
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.results-list-item"))
        )
        
        logging.info("ЗНАЙДЕНО КАРТКУ ПОТЯГА!")
        return True

    except TimeoutException:
        logging.info("Потяги на маршруті не знайдено.")
        return False
    except WebDriverException as e:
        logging.error(f"Помилка WebDriver: {e}. Можливо, chromedriver не знайдено або він застарів.")
        return False
    except Exception as e:
        logging.error(f"Сталася невідома помилка під час перевірки: {e}")
        return False
    finally:
        if driver:
            driver.quit()

def main():
    """Головна функція запуску бота."""
    if not all([BOT_TOKEN, CHAT_ID, STATION_FROM_CODE, STATION_TO_CODE, DEPARTURE_DATE]):
        logging.error("Критична помилка: не всі змінні середовища задані в .env файлі. Перевірте BOT_TOKEN, CHAT_ID та параметри пошуку.")
        return

    logging.info("Бот запущено.")
    
    start_message = (
        f"✅ *Бот запущений!*\n\n"
        f"Починаю моніторинг потягів за маршрутом *{STATION_FROM_NAME} → {STATION_TO_NAME}* "
        f"на *{DEPARTURE_DATE}*.\n\n"
        f"Інтервал пошуку: *{SEARCH_INTERVAL_SECONDS}* секунд. "
        f"У разі знахідки, інтервал сповіщень: *{ALARM_INTERVAL_SECONDS}* секунд."
    )
    send_telegram_message(start_message)
    
    try:
        while True:
            if check_for_trains():
                logging.info("ПОТЯГ ЗНАЙДЕНО! Переходжу в режим сигналізації.")
                alarm_message = (
                    f"🚨 *УВАГА! З'ЯВИВСЯ ПОТЯГ!* 🚨\n\n"
                    f"Маршрут: *{STATION_FROM_NAME} → {STATION_TO_NAME}*\n"
                    f"Дата: *{DEPARTURE_DATE}*\n\n"
                    f"*[ТЕРМІНОВО ПЕРЕВІРЯЙТЕ САЙТ](https://booking.uz.gov.ua/)*"
                )
                # Внутрішній цикл для сповіщень, доки потяг є в наявності
                while check_for_trains():
                    send_telegram_message(alarm_message)
                    time.sleep(ALARM_INTERVAL_SECONDS)
                
                logging.info("Потяг зник. Повертаюся до звичайного режиму пошуку.")
                send_telegram_message("✅ *Потяг зник*. Повертаюся до звичайного режиму пошуку.")

            else:
                logging.info(f"Потягів немає. Наступна перевірка через {SEARCH_INTERVAL_SECONDS / 60:.1f} хв.")
                time.sleep(SEARCH_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logging.info("Роботу бота зупинено вручну.")
        send_telegram_message("끄 *Роботу бота зупинено.*")
    except Exception as e:
        logging.critical(f"Критична помилка в головному циклі: {e}")
        send_telegram_message(f"❌ *Критична помилка бота!* \n\n`{e}`")


if __name__ == "__main__":
    main()

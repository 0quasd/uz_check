# uz_monitor_github.py
import logging
import time
import os
from bs4 import BeautifulSoup

# --- Бібліотеки для автоматизації браузера ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

# ==============================================================================
# --- НАЛАШТУВАННЯ ---
# Токен і Chat ID тепер будуть зчитуватися з GitHub Secrets
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# --- Параметри пошуку квитків ---
STATION_FROM_CODE = '2200300'
STATION_TO_CODE = '2218214'
DEPARTURE_DATE = '2025-06-29'
MIN_SEATS_REQUIRED = 1 # Змінено на 1, щоб реагувати на будь-яку кількість
SEAT_TYPE_LETTER = 'К'

# --- Інтервал перевірки (5 хвилин) ---
CHECK_INTERVAL_SECONDS = 300
# --- Інтервал для звітів (15 хвилин = 3 цикли по 5 хвилин) ---
HEARTBEAT_INTERVAL_LOOPS = 3
# ==============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_telegram_message(message):
    import requests
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("BOT_TOKEN або CHAT_ID не знайдено! Перевірте GitHub Secrets.")
        return
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10).raise_for_status()
        logging.info("Повідомлення успішно надіслано в Telegram.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Помилка надсилання повідомлення в Telegram: {e}")

def check_uz_tickets():
    search_url = f"https://booking.uz.gov.ua/search-trips/{STATION_FROM_CODE}/{STATION_TO_CODE}/list?startDate={DEPARTURE_DATE}"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    # Ці два аргументи критично важливі для роботи в середовищі GitHub Actions
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = None
    try:
        # У GitHub Actions Chrome і chromedriver будуть встановлені автоматично
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        logging.info(f"Запускаю браузер і заходжу на сторінку...")
        driver.get(search_url)
        
        logging.info("Чекаю, поки на сторінці з'являться картки з потягами...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "TripUnit"))
        )
        
        html_content = driver.page_source
        logging.info("Сторінку успішно завантажено, починаю аналіз...")
        soup = BeautifulSoup(html_content, 'lxml')
        
        trip_cards = soup.find_all('div', class_='TripUnit')
        logging.info(f"Знайдено {len(trip_cards)} карток з потягами.")
        
        if not trip_cards:
            return False

        found_tickets_messages = []
        for card in trip_cards:
            train_number_div = card.find('div', class_='train-number')
            train_number = train_number_div.get_text(strip=True) if train_number_div else 'N/A'
            
            # ... (решта логіки аналізу залишається такою ж)
            wagon_types = card.find_all('div', class_='wagon-type')
            for wagon in wagon_types:
                wagon_type_name_div = wagon.find('div', class_='name')
                wagon_type_name = wagon_type_name_div.get_text(strip=True) if wagon_type_name_div else ''

                free_seats_div = wagon.find('div', class_='free-seats')
                free_seats = 0
                if free_seats_div:
                    try:
                        free_seats = int(free_seats_div.get_text(strip=True).split()[0])
                    except (ValueError, IndexError):
                        continue
                
                # Надсилаємо, як тільки знайдено хоча б 1 квиток потрібного типу
                if "купе" in wagon_type_name.lower() and free_seats >= MIN_SEATS_REQUIRED:
                    station_from_div = card.find('div', class_='station-from')
                    station_from = station_from_div.find('span', class_='name').get_text(strip=True) if station_from_div else 'N/A'
                    station_to_div = card.find('div', class_='station-to')
                    station_to = station_to_div.find('span', class_='name').get_text(strip=True) if station_to_div else 'N/A'
                    
                    message = (f"🎉 **ЗНАЙДЕНО КВИТОК!** 🎉\n\n"
                               f"**Маршрут:** {station_from} -> {station_to}\n"
                               f"**Потяг:** `{train_number}`\n"
                               f"**Тип місць:** {wagon_type_name}\n"
                               f"**Вільних місць:** *{free_seats}*")
                    send_telegram_message(message)
                    return True # Повертаємо True, щоб зупинити скрипт
        
        logging.info("Знайдено потяги, але місць потрібного типу/кількості немає.")
        return False

    except TimeoutException:
        logging.info("За 15 секунд потяги на сторінці не з'явились. Ймовірно, їх немає.")
        return False
    except Exception as e:
        logging.error(f"Сталася невідома помилка: {e}")
        return False
    finally:
        if driver:
            driver.quit()
            logging.info("Браузер закрито.")

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("Необхідно налаштувати секрети BOT_TOKEN та CHAT_ID в репозиторії GitHub.")
    else:
        logging.info("Бот-моніторинг квитків запущено на GitHub Actions.")
        send_telegram_message("✅ **Бот запущений!**\n\nПочинаю моніторинг квитків. Звіт про роботу - кожні 15 хвилин.")
        
        loop_counter = 0
        while True:
            if check_uz_tickets():
                logging.info("Квитки знайдено! Завершую роботу.")
                send_telegram_message("✅ **Квитки знайдено!**\n\nМоніторинг завершено. Для нового пошуку перезапустіть бота.")
                break
            
            loop_counter += 1
            time.sleep(CHECK_INTERVAL_SECONDS) # Чекаємо 5 хвилин

            if loop_counter % HEARTBEAT_INTERVAL_LOOPS == 0:
                send_telegram_message(f"⌛️ *Звіт:* Бот працює, квитків поки немає. Наступна перевірка через {int(CHECK_INTERVAL_SECONDS/60)} хв.")

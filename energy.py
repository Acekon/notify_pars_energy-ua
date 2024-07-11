import logging
import os
import time
from datetime import datetime

import cloudscraper
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import sqlite3

load_dotenv()
CHANNELS = {
    1: os.environ.get("CHANNEL_1"),
    2: os.environ.get("CHANNEL_2"),
    3: os.environ.get("CHANNEL_3"),
    4: os.environ.get("CHANNEL_4"),
    5: os.environ.get("CHANNEL_5"),
    6: os.environ.get("CHANNEL_6"),
}
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT")
TELEGRAM_ADMIN = os.environ.get("TELEGRAM_ADMIN")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("logs/app.log")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(asctime)s - %(module)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


def formated_array(array: list) -> list:
    arr = list(filter(None, array))
    result = []
    i = 0
    for _ in range(0, int(len(arr)/2)):
        result.append(f'{arr[i]} {arr[i + 1]}')
        i += 2
    return result


def telegram_send_text(chat_id: str, text: str):
    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage"
    response = requests.post(tg_url, json={"chat_id": chat_id, "parse_mode": "html", "text": text})
    if response.json().get("ok"):
        logger.info(response.json())
    else:
        logger.error(response.json())
    return response.json().get("result").get("message_id")


def telegram_update_message(chat_id: str, message_id, text: str):
    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT}/editMessageText"
    response = requests.post(
        tg_url,
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "parse_mode": "html",
            "text": text,
        },
    )
    if response.json().get("ok"):
        logger.info({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})
    else:
        logger.error({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})


def telegram_delete_message(chat_id: str, message_id):
    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT}/deleteMessage"
    response = requests.post(tg_url, json={"chat_id": chat_id, "message_id": message_id})
    if response.json().get("ok"):
        logger.info({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})
    else:
        logger.error({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})


def save_schedule_db(queue: int, text: str, day: str):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'UPDATE energy SET {day} = "{text}" WHERE queue = "{queue}";'
    c.execute(sql_query)
    conn.commit()
    conn.close()


def save_message_id_db(message_id: int, queue: int):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'UPDATE energy SET message_id = "{message_id}" WHERE queue = "{queue}";'
    c.execute(sql_query)
    conn.commit()
    conn.close()


def get_db(queue: int, day: str):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'Select {day}, queue  from energy where queue = "{queue}";'
    c.execute(sql_query)
    now_day, queue = c.fetchone()
    return now_day


def get_message_id_db(queue: int) -> int:
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'Select message_id from energy where queue = "{queue}";'
    c.execute(sql_query)
    message_id = c.fetchone()
    return message_id[0]


def get_schedules(queue: int):
    scraper = cloudscraper.create_scraper(
        browser={
            "browser": "chrome",
            "platform": "linux",
            "desktop": True,
            "mobile": False,
        }
    )
    url = f"https://esvitlo.info/cherga-{queue}/"
    response = scraper.get(url)
    if response.status_code != 200:
        logger.error(f"response.status_code: {response.status_code}")
        telegram_send_text(
            chat_id=TELEGRAM_ADMIN,
            text=f"Error\n{response.url}: {response.status_code}",
        )
        raise SystemExit()
    soup = BeautifulSoup(response.text, "html.parser")
    schedules = soup.find_all(class_="outage-periods-list")
    formated_now_day = "\n".join(formated_array(schedules[0].text.strip().split("\n")))
    formated_next_day = "\n".join(formated_array(schedules[1].text.strip().split("\n")))
    now_day_db = get_db(queue, "now_day")
    next_day_db = get_db(queue, "next_day")
    return (formated_now_day, now_day_db), (formated_next_day, next_day_db)


def main():
    day = [i for i in range(6, 20)]  # send only in number hours
    night = [i for i in range(21, 24)]  # send only in number hours
    logger.info("Start")
    for i in range(1, 7):  # count queue
        now_day, next_day = get_schedules(i)
        site_now_day, db_now_day = now_day
        site_next_day, db_next_day = next_day
        current_time = int(datetime.now().strftime("%#H"))
        message_id_db = get_message_id_db(queue=i)
        if site_now_day != db_now_day and current_time in day:
            text = f'Черга {i}, Відключення на сьогодні:\n'
            save_schedule_db(queue=i, text=site_now_day, day="now_day")
            telegram_send_text(text=text + site_now_day, chat_id=CHANNELS.get(i))
            logger.info(f"Now day queue: {i} send")
        else:
            logger.info(f"Queue: {i} now not update")
        if site_now_day != db_now_day and current_time == day[0]:
            telegram_delete_message(chat_id=CHANNELS.get(i), message_id=message_id_db)
        if site_next_day != db_next_day and current_time in night and (site_next_day.find("ще очікуються") == -1):
            text = f'Черга {i}, Відключення на завтра:\n'
            save_schedule_db(queue=i, text=site_next_day, day="next_day")
            message_id = telegram_send_text(text=text + site_next_day, chat_id=CHANNELS.get(i))
            save_message_id_db(message_id=message_id, queue=i)
            logger.info(f"Next day queue: {i} update")
        else:
            logger.info(f"Queue: {i} next not update")
        time.sleep(2)


if __name__ == "__main__":
    main()

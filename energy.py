import os
import time
from datetime import datetime

import cloudscraper
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import sqlite3

load_dotenv()
CHANNELS = {1: os.environ.get('CHANNEL_1'),
            2: os.environ.get('CHANNEL_2'),
            3: os.environ.get('CHANNEL_3'),
            4: os.environ.get('CHANNEL_4'),
            5: os.environ.get('CHANNEL_5'),
            6: os.environ.get('CHANNEL_6'),
            }
TELEGRAM_BOT = os.environ.get('TELEGRAM_BOT')


def telegram_send_text(chat_id: str, text: str):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage'
    res = requests.post(tg_url, json={'chat_id': chat_id, 'parse_mode': 'html', 'text': text})
    print(datetime.now().strftime("%H:%M:%S"), res.json())


def save_db(queue: int, text: str, day: str):
    conn = sqlite3.connect('energy.db')
    c = conn.cursor()
    sql_query = f'UPDATE energy SET {day} = "{text}" WHERE queue = "{queue}";'
    c.execute(sql_query)
    conn.commit()
    conn.close()


def get_db(queue: int, day: str):
    conn = sqlite3.connect('energy.db')
    c = conn.cursor()
    sql_query = f'Select {day}, queue  from energy where queue = "{queue}";'
    c.execute(sql_query)
    now_day, queue = c.fetchone()
    return now_day


def get_schedules(queue: int):
    scraper = cloudscraper.create_scraper()
    url = f'https://energy-ua.info/cherga/{queue}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/91.0.4472.124 Safari/537.36'
    }
    response = scraper.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    schedules = soup.find_all(class_='grafik_string')
    formated_now_day = '\n'.join(schedules[0].text.strip().split('\n'))
    formated_next_day = '\n'.join(schedules[1].text.strip().split('\n'))
    now_day_db = get_db(queue, 'now_day')
    next_day_db = get_db(queue, 'next_day')
    time.sleep(2)
    return (formated_now_day, now_day_db), (formated_next_day, next_day_db)


def main():
    day = [i for i in range(6, 19)]  # send only in number hours
    night = [i for i in range(20, 24)]  # send only in number hours
    for i in range(1, 7):  # count queue
        print(f'{datetime.now().strftime("%H:%M:%S")} Start Queue: {i}')
        now_day, next_day = get_schedules(i)
        site_now_day, db_now_day = now_day
        site_next_day, db_next_day = next_day
        current_time = int(datetime.now().strftime('%#H'))
        if site_now_day != db_now_day and current_time in day:
            save_db(queue=i, text=site_now_day, day='now_day')
            telegram_send_text(text=site_now_day, chat_id=CHANNELS.get(i))
            print(f'{datetime.now().strftime("%H:%M:%S")} Now day queue: {i} send')
        elif site_next_day != db_next_day and current_time in night:
            save_db(queue=i, text=site_next_day, day='next_day')
            telegram_send_text(text='🔜 ' + site_next_day, chat_id=CHANNELS.get(i))
            print(f'{datetime.now().strftime("%H:%M:%S")} Next day queue: {i} send')
        else:
            print(f'{datetime.now().strftime("%H:%M:%S")} Queue: {i} not update')


if __name__ == '__main__':
    main()

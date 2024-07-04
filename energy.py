import os
import time
from datetime import datetime

import cloudscraper
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import sqlite3

load_dotenv()
channels = {1: os.environ.get('CHANNEL_1'),
            2: os.environ.get('CHANNEL_2'),
            3: os.environ.get('CHANNEL_3'),
            4: os.environ.get('CHANNEL_4'),
            5: os.environ.get('CHANNEL_5'),
            6: os.environ.get('CHANNEL_6'),
            }
TELEGRAM_BOT = os.environ.get('TELEGRAM_BOT')


def telegram_send_text(chat_id: str, text: str):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage'
    requests.post(tg_url, json={'chat_id': chat_id, 'parse_mode': 'html', 'text': text})


def save_db(queue: int, text: str, day: str):
    conn = sqlite3.connect('energy.db')
    c = conn.cursor()
    sql_query = (f'UPDATE energy '
                 f'SET {day} = "{text}"'
                 f'WHERE queue = "{queue}";')
    c.execute(sql_query)
    conn.commit()
    conn.close()


def if_update(queue: int, day: str):
    conn = sqlite3.connect('energy.db')
    c = conn.cursor()
    sql_query = f'Select {day}, queue  from energy where queue = "{queue}";'
    c.execute(sql_query)
    now_day, queue = c.fetchone()
    return now_day


def parse(queue: int):
    scraper = cloudscraper.create_scraper()
    url = f'https://energy-ua.info/cherga/{queue}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/91.0.4472.124 Safari/537.36'
    }
    response = scraper.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    grafiks = soup.find_all(class_='grafik_string')
    formated_now_day = '\n'.join(grafiks[0].text.strip().split('\n'))
    formated_next_day = '\n'.join(grafiks[1].text.strip().split('\n'))
    now_day = if_update(queue, 'now_day')
    next_day = if_update(queue, 'next_day')
    time.sleep(2)
    return (formated_now_day, now_day), (formated_next_day, next_day)


def main():
    for i in range(1, 7):
        now_day, next_day = parse(i)
        site_now_day, db_now_day = now_day
        site_next_day, db_next_day = next_day
        current_time = int(datetime.now().strftime('%#H'))
        if site_now_day != db_now_day:
            save_db(queue=i, text=site_now_day, day='now_day')
            telegram_send_text(text=f'Черга: {i}\n' + site_now_day, chat_id=channels.get(i))
            print(f'Now day queue: {i} send')
        elif site_next_day != db_next_day and current_time in [20, 21, 22, 23]:  # send only in number hours
            save_db(queue=i, text=site_next_day, day='next_day')
            telegram_send_text(text=f'Черга: {i}\n' + site_next_day, chat_id=channels.get(i))
            print(f'Next day queue: {i} send')
        else:
            print(f'Queue: {i} is skipped')


if __name__ == '__main__':
    main()

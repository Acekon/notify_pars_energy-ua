import logging
import os
import time
from datetime import datetime

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
file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
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


def telegram_send_text(chat_id: str, text: str):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage'
    response = requests.post(tg_url, json={"chat_id": chat_id, "parse_mode": "html", "text": text})
    if response.json().get("ok"):
        logger.info(response.json())
    else:
        logger.error(response.json())
    return response.json().get("result").get("message_id")


def telegram_update_message(chat_id: str, message_id, text: str):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/editMessageText'
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
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/deleteMessage'
    response = requests.post(tg_url, json={"chat_id": chat_id, "message_id": message_id})
    if response.json().get("ok"):
        logger.info({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})
    else:
        logger.error({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})


def site_poe_gvp(date_in):
    url = "https://www.poe.pl.ua/customs/newgpv-info.php"
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "ru-RU,ru;q=0.9,uk;q=0.8,en-US;q=0.7,en;q=0.6",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "dnt": "1",
        "origin": "https://www.poe.pl.ua",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.poe.pl.ua/disconnection/power-outages/",
        "sec-ch-ua": '"Opera";v="111", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
                      " Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0",
        "x-requested-with": "XMLHttpRequest"
    }
    data = {"seldate": f'{{"date_in":"{date_in}"}}'}
    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        logger.error(response.status_code,response.text)
        telegram_send_text(chat_id=TELEGRAM_ADMIN, text=f'Status code error {response.status_code}\n{response.text}')
    return response.text


def convert_date(date_str: str):
    months = {
        "січня": "January", "лютого": "February", "березня": "March",
        "квітня": "April", "травня": "May", "червня": "June",
        "липня": "July", "серпня": "August", "вересня": "September",
        "жовтня": "October", "листопада": "November", "грудня": "December"
    }
    for ukr_month, eng_month in months.items():
        if ukr_month in date_str:
            date_str = date_str.replace(ukr_month, eng_month)
            break
    date_str = date_str.replace(" року", "")
    date_format = "%d %B %Y"
    date_obj = datetime.strptime(date_str, date_format)
    return date_obj.strftime('%d-%m-%Y')


def pars_poe_gvp(response):
    all_gvp = []
    soup = BeautifulSoup(response, 'html.parser')
    gvps = soup.find_all('div', class_='gpvinfodetail')
    for gvp in gvps:
        result_dict = {'date': '', 'sequence': '', 'schedulers': []}
        p_tags = gvp.find_all('b')
        date = gvp.find('b', style='color: red;')
        result_dict['date'] = convert_date(date.text)
        arr_periods = []
        for p in p_tags:
            arr_text = p.text.split()
            if len(arr_text) == 4 and ':' in arr_text[1]:
                arr_periods.append(arr_text[1])
                arr_periods.append(arr_text[3])
            if len(arr_text) == 1:
                arr_periods.append(arr_text[0])
        len_periods = int(len(arr_periods) / 3)
        i = 0
        schedulers = []
        for _ in range(len_periods):
            period = {'start': arr_periods[i], 'end': arr_periods[i + 1], 'class_': arr_periods[i + 2]}
            i += 3
            schedulers.append(period)
        result_dict['schedulers'] = schedulers
        all_gvp.append(result_dict)
    return all_gvp


def get_start_end_schedule(day):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'SELECT date, start, end, class FROM schedulers WHERE date = "{day}" AND enable = 1;'
    c.execute(sql_query)
    return c.fetchall()


def get_list_schedule(day):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'SELECT start, end, class FROM schedulers WHERE date = "{day}" AND enable = 1;'
    c.execute(sql_query)
    return c.fetchall()


def get_next_sequence():
    letters = ['A', 'B', 'C']
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'SELECT sequence FROM schedulers WHERE enable = 1 ORDER BY id DESC LIMIT 1;'
    c.execute(sql_query)
    current_index = letters.index(c.fetchall()[0][0])
    next_index = (current_index + 1) % len(letters)
    return letters[next_index]


def get_current_sequence(date):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'SELECT sequence FROM schedulers WHERE date="{date}" AND enable = 1 ORDER BY id DESC LIMIT 1;'
    c.execute(sql_query)
    return c.fetchone()[0]


def disable_periods(date_schedulers):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f"UPDATE schedulers SET enable = 0 WHERE date = '{date_schedulers}';"
    c.execute(sql_query)
    conn.commit()
    conn.close()


def get_schedule(day, sequence, queue):
    start_end_schedulers = get_start_end_schedule(day=day)
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    result_text = []
    for start_end_schedule in start_end_schedulers:
        class_ = start_end_schedule[-1]
        sql_query = f'SELECT {sequence}{class_} FROM {sequence} WHERE queue = "{queue}";'
        c.execute(sql_query)
        all_schedulers = c.fetchall()
        for schedule in all_schedulers:
            try:
                start, end = schedule[0].split(' ')
            except AttributeError:
                continue
            all_range = [i for i in range(int(start_end_schedule[1]), int(start_end_schedule[2]))]
            if int(start.split(':')[0]) in all_range:
                result_text.append(f'{sequence}{class_}: {start} ~{end}')
    return result_text


def save_list_schedulers(data_schedulers):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sequence = get_next_sequence()
    for scheduler in data_schedulers.get("schedulers"):
        sql_query = (f'INSERT INTO "main"."schedulers"'
                     f'("date",'
                     f'"start","end",'
                     f'"class","sequence") '
                     f'VALUES '
                     f'("{data_schedulers.get("date")}",'
                     f'"{scheduler.get("start").split(":")[0]}","{scheduler.get("end").split(":")[0]}",'
                     f'"{scheduler.get("class_")}","{sequence}");')
        c.execute(sql_query)
        logger.info(sql_query)
        conn.commit()


def save_schedule_db(queue: int, text: str, day: str):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'UPDATE energy SET {day} = "{text}" WHERE queue = "{queue}";'
    c.execute(sql_query)
    conn.commit()
    conn.close()


def get_schedule_db(queue: int, day: str):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'SELECT {day} FROM energy WHERE queue = "{queue}";'
    c.execute(sql_query)
    conn.commit()
    return c.fetchone()


def get_count_all_time_schedule(schedule_arr: list) -> str:
    total_times = 0
    for row in schedule_arr:
        row = row.replace('~', '').split(' ')
        start_time_obj = datetime.strptime(row[-2], '%H:%M')
        end_time_obj = datetime.strptime(row[-1], '%H:%M')
        time_difference = end_time_obj - start_time_obj
        total_times += time_difference.seconds
    total_times = total_times / 60
    hours = total_times // 60
    minutes = total_times % 60
    return f"{hours.__int__()} годин {minutes.__int__()} хвилин"


def fix_periods(data_schedulers):
    for i, scheduler in enumerate(data_schedulers.get("schedulers")):
        if i == 0:
            scheduler.update({'start': '00:00'})
        if i == len(data_schedulers.get("schedulers")) - 1:
            scheduler.update({'end': '24:00'})
    return data_schedulers


def compare_periods(db_period, site_period):
    if len(db_period) != len(site_period):
        return False
    for i in range(len(db_period)):
        if db_period[i][0] != site_period[i].get('start').split(':')[0]:
            return False
        if db_period[i][1] != site_period[i].get('end').split(':')[0]:
            return False
    return True


def send_notification(data_schedulers, sequence, day):
    for i in range(1, 7):  # count queue
        message = get_schedule(day=data_schedulers.get("date"), sequence=sequence, queue=i)
        if ''.join(message) != ''.join(get_schedule_db(day=day, queue=i)):
            save_schedule_db(text=''.join(message), day=day, queue=i)
            all_time_schedule = get_count_all_time_schedule(message)
            text_all_time_schedule = f'\nЗагалом час відключення ~{all_time_schedule}'
            text = f'Черга {i}, Відключення на {data_schedulers.get("date")}:\n' + "\n".join(
                message) + text_all_time_schedule
            telegram_send_text(chat_id=CHANNELS.get(i), text=text)
            logger.info(f"Send - Date: {data_schedulers.get('date')} Queue: {i}")
            time.sleep(0.5)
        else:
            logger.info(f"Scip - Date: {data_schedulers.get('date')} Queue: {i} ")


def main():
    current_day_period = [i for i in range(6, 24)]  # period send current day
    next_day_period = [i for i in range(16, 24)]  # period check and send next day
    current_date = datetime.now()
    formatted_date = current_date.strftime('%d-%m-%Y')
    response = site_poe_gvp(formatted_date)
    data_schedulers = pars_poe_gvp(response)
    if current_date.time().hour in current_day_period:
        data_schedulers_now_day = fix_periods(data_schedulers[0])  # 0 current day
        periods = get_list_schedule(data_schedulers_now_day.get("date"))
        if not compare_periods(periods, data_schedulers[0].get('schedulers')):
            disable_periods(data_schedulers_now_day.get("date"))
            periods = []
        if not periods:
            save_list_schedulers(data_schedulers_now_day)
            logger.info('Save now day list schedule')
        sequence = get_current_sequence(data_schedulers_now_day.get("date"))
        send_notification(data_schedulers_now_day, sequence, day='now_day')
    if current_date.time().hour in next_day_period and len(data_schedulers) == 2:
        data_schedulers_next_day = fix_periods(data_schedulers[1])  # 1 next day
        periods = get_list_schedule(data_schedulers_next_day.get("date"))
        if not compare_periods(periods, data_schedulers[1].get('schedulers')):
            disable_periods(data_schedulers_next_day.get("date"))
            periods = []
        if not periods:
            save_list_schedulers(data_schedulers_next_day)
            logger.info('Save next day list schedule')
        sequence = get_current_sequence(data_schedulers_next_day.get("date"))
        send_notification(data_schedulers_next_day, sequence, day='next_day')


if __name__ == "__main__":
    main()

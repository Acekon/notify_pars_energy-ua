import logging
import os
import time
from datetime import datetime, timedelta
from sched import scheduler

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
file_formatter = logging.Formatter("%(asctime)s - %(module)s - %(levelname)s - %(message)s")
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
        logger.error(f'Status code error {response.status_code}\n{response.text}')
        telegram_send_text(chat_id=TELEGRAM_ADMIN,
                           text=f'Status code error {response.status_code}\n{response.text}')
        return False
    logger.info(f'Load new info {response.url} http:{response.status_code}')
    # todo remove deploy
    with open(f'logs/{datetime.now().strftime("%d_%m_%Y_%H_%M_%S")}.html', "w", encoding='UTF-8') as file:
        file.write(response.text)
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


def save_schedule_send_log(queue: int, text: str, date: str):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query_select = f'SELECT * FROM send_log WHERE date = "{date}" AND queue = {queue};'
    c.execute(sql_query_select)
    db = c.fetchone()
    if db:
        sql_query = f'UPDATE send_log SET text = "{text}" WHERE date = "{date}" and queue = "{queue}";'
        logger.info(sql_query)
        c.execute(sql_query)
        conn.commit()
        conn.close()
        return True
    sql_query = f'INSERT OR IGNORE INTO send_log (date,text,queue) VALUES ("{date}","{text}",{queue})'
    logger.info(sql_query)
    c.execute(sql_query)
    conn.commit()
    conn.close()


def get_schedule_send_log(queue: int, date: str):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'SELECT text FROM send_log WHERE queue = "{queue}" AND date = "{date}";'
    c.execute(sql_query)
    conn.commit()
    result = c.fetchone()
    if not result:
        return ['']
    return result


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


def send_notification_old(data_schedulers: dict[str, str | list | list[dict[str, str]]], sequence: str):
    for i in range(1, 7):  # count queue
        time.sleep(0.5)

        if ''.join(message) != ''.join(get_schedule_send_log(date=data_schedulers.get("date"), queue=i)):
            save_schedule_send_log(text=''.join(message), date=data_schedulers.get("date"), queue=i)
            all_time_schedule = get_count_all_time_schedule(message)
            text_all_time_schedule = f'\nЗагалом час відключення ~{all_time_schedule}'
            text = f'Черга {i}, Відключення на {data_schedulers.get("date")}:\n' + "\n".join(
                message) + text_all_time_schedule
            telegram_send_text(chat_id=CHANNELS.get(i), text=text)
            logger.info(f"Send notification - Date: {data_schedulers.get('date')} Queue: {i}")
        else:
            logger.info(f"Skip notification is no update - Date: {data_schedulers.get('date')} Queue: {i} ")


def pars_table_poe(response):
    soup = BeautifulSoup(response, 'html.parser')
    gvps_table = soup.find('table', class_='turnoff-scheduleui-table')
    head_table, data_table = gvps_table
    queue = data_table.find_all('tr')
    data_queues = []
    for row in queue:
        cells = row.find_all('td')
        row_data = []
        for cell in cells:
            if 'light_1' in cell.get('class', []):
                row_data.append(0)
                continue
            if 'light_2' in cell.get('class', []):
                row_data.append(1)
                continue
            if 'light_3' in cell.get('class', []):
                row_data.append(1)
                continue
            if 'turnoff-scheduleui-table-queue' in cell.get('class', []):
                continue
            if '12' in cell.get('rowspan', []):
                continue
            else:
                continue
        data_queues.append(row_data)
    num = 1
    sub_num = 1
    flag = 0
    resul_queue = []
    for queue in data_queues:
        resul_queue.append(queue_time_data(queue_num=num, queue_sub_num=sub_num, time_slots=queue))
        if flag == 0:
            flag = 1
            sub_num = 2
            continue
        if flag == 1:
            flag = 0
            num += 1
            sub_num = 1
    return resul_queue


def index_to_time(index):
    hours = index // 2
    minutes = (index % 2) * 30
    return f"{hours:02}:{minutes:02}"


def queue_time_data(queue_num, queue_sub_num, time_slots):
    active_periods = []
    start = None

    for i, value in enumerate(time_slots):
        if value == 1 and start is None:
            start = i
        elif value == 0 and start is not None:
            active_periods.append((start, i - 1))
            start = None

    if start is not None:
        active_periods.append((start, len(time_slots) - 1))

    time_intervals = [(index_to_time(start), index_to_time(end + 1)) for start, end in active_periods]
    result_queue = []
    for start_time, end_time in time_intervals:
        queue = {'queue': f'{queue_num}.{queue_sub_num}', 'data': [start_time, end_time]}
        result_queue.append(queue)
    return result_queue


def send_notification(schedulers, date):
    for schedule in schedulers:
        time.sleep(0.5)
        num_queue = schedule[0].get('queue').split('.')[0]
        merged_data = {}

        for entry in schedule:
            queue = entry['queue']
            if queue not in merged_data:
                merged_data[queue] = []
            merged_data[queue].extend(entry['data'])
        source_schedule = [{'queue': queue, 'data': times} for queue, times in merged_data.items()]
        mess_schedule = source_schedule[0].get("data")
        time_pairs = [f"{mess_schedule[i]} {mess_schedule[i + 1]}" for i in range(0, len(mess_schedule), 2)]
        times = '\n'.join(time_pairs)
        text = f'Черга {schedule[0].get("queue")}, Відключення на {date}:\n' + f"{times}"
        telegram_send_text(chat_id=CHANNELS.get(int(num_queue)), text=text)
        logger.info(f"Send notification - Date: {date} Queue: {num_queue}")


def main():
    work_period = [i for i in range(6, 23)]  # period send current day
    current_date = datetime.now()
    if not current_date.time().hour in work_period:
        return logger.info('Skip check outside time period')
    formatted_date = current_date.strftime('%d-%m-%Y')
    # response = site_poe_gvp(formatted_date)
    # if not response:
    #    return logger.info('The site returns bad html code of the website')
    with open('logs/16_12_2024_07_18_18.html', 'r', encoding='utf-8') as f:  # todo remove deploy
        response = f.read()
    send_notification(schedulers=pars_table_poe(response), date=formatted_date)


if __name__ == "__main__":
    main()

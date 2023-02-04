import os
import sys
import time
import logging
import requests
import telegram
from dotenv import load_dotenv

load_dotenv()
PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TG_CHAT_ID')

logger = logging.getLogger(__name__)
formatter = logging.Formatter(
    '%(asctime)s - %(lineno)s - %(name)s - %(levelname)s - %(message)s'
)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class BotException(Exception):
    """Вызов исключения, если в боте ошибка уровня error и выше."""

    pass


def check_tokens():
    """Проверка переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        logger.critical('Ошибка в переменных окружения.')


def send_message(bot, message):
    """Отправка сообщения ботом в телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправленно.')
    except telegram.error.TelegramError:
        logger.error('Сбой в отправке сообщения.')


def get_api_answer(timestamp):
    """Получение ответа API."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
    except requests.exceptions.RequestException:
        logger.error('Ошибка при запросе к API.')
        raise BotException('Ошибка при запросе к API.')
    if response.status_code != 200:
        logger.error('Статус код ответа API отличен от 200.')
        raise BotException('Статус код ответа API отличен от 200.')
    response = response.json()
    return response


def check_response(response):
    """Проверка ответа API."""
    if type(response) is not dict:
        logger.error('Ответ API не является словарем.')
        raise TypeError('Ответ API не является словарем.')
    elif type(response.get('homeworks')) is not list:
        logger.error('Ответ API получен не в списке.')
        raise TypeError('Ответ API получен не в списке.')
    elif response.get('homeworks') != []:
        try:
            response = response.get('homeworks')[0]
        except BotException:
            logger.error('Ответ API не содержит домашку.')
            raise BotException('Ответ API не содержит домашку.')
        return response
    logger.debug('Отсутствие в ответе API новых статусов домашней работы.')
    return None


def parse_status(homework):
    """Проверка статуса домашней работы."""
    if homework.get('homework_name') and homework.get('status'):
        homework_name = homework.get('homework_name')
        status = homework.get('status')
        if status not in HOMEWORK_VERDICTS:
            logger.error('Не корректный статус в ключах ответа API.')
            raise BotException('Не корректный статус в ключах ответа API.')
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}".{verdict}'
    raise BotException('Нет значений по ключам homework_name или status.')


def main():
    """Основная логика работы бота."""
    timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    SUM_ATTEMPTS_SEND_MESSEAGE_IN_TG = 0
    while True:
        if check_tokens():
            try:
                api_answer = get_api_answer(timestamp)
                homework = check_response(api_answer)
                if homework is not None:
                    status = parse_status(homework)
                    send_message(bot, status)
                    time.sleep(RETRY_PERIOD)
                time.sleep(RETRY_PERIOD)
            except BotException as error:
                message = f'Сбой в работе программы: {error}'
                logger.critical(message)
                time.sleep(RETRY_PERIOD)
                if SUM_ATTEMPTS_SEND_MESSEAGE_IN_TG == 0:
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                    SUM_ATTEMPTS_SEND_MESSEAGE_IN_TG += 1
        break


if __name__ == '__main__':
    main()

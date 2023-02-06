import logging
import os
import sys
import time
from typing import Any, Union
from http import HTTPStatus

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


def check_tokens() -> bool:
    """Проверка переменных окружения."""
    if all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))
    else:
        return False


def send_message(bot: Any, message: str) -> None:
    """Отправка сообщения ботом в телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправленно.')
    except telegram.error.TelegramError:
        logger.error('Сбой в отправке сообщения.')
        raise BotException('Сбой в отправке сообщения')


def get_api_answer(timestamp: int) -> dict:
    """Получение ответа API."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
    except requests.exceptions.RequestException:
        logger.error('Ошибка при запросе к API.')
        raise BotException('Ошибка при запросе к API.')
    if response.status_code != HTTPStatus.OK:
        logger.error('Статус код ответа API отличен от 200.')
        raise BotException('Статус код ответа API отличен от 200.')
    return response.json()


def check_response(response: dict) -> Union[dict, None]:
    """Проверка ответа API."""
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарем.')
        raise TypeError('Ответ API не является словарем.')
    elif not isinstance(response.get('homeworks'), list):
        logger.error('Ответ API получен не в списке.')
        raise TypeError('Ответ API получен не в списке.')
    elif response.get('homeworks'):
        return response.get('homeworks')[0]
    logger.debug('Отсутствие в ответе API новых статусов домашней работы.')


def parse_status(homework: dict) -> str:
    """Проверка статуса домашней работы."""
    if 'homework_name' not in homework:
        logger.error('Нет ключа homework_name в ответе API.')
        raise BotException('Нет ключа homework_name в ответе API.')
    if 'status' not in homework:
        logger.error('Нет ключа status в ответе API.')
        raise BotException('Нет ключа status в ответе API.')
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        logger.error('Нет ключа status в ожидаемом словаре.')
        raise BotException('Нет ключа status в ожидаемом словаре.')
    verdict = HOMEWORK_VERDICTS[status]
    logger.info(f'Изменился статус работы "{homework_name}".{verdict}')
    return f'Изменился статус проверки работы "{homework_name}".{verdict}'


def main() -> None:
    """Основная логика работы бота."""
    timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    status_now = ''
    error_send_message_in_tg = []
    if not check_tokens():
        logger.critical('Ошибка в переменных окружения.')
        raise BotException('Ошибка в переменных окружения.')
    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homework = check_response(api_answer)
            if homework is not None:
                if homework.get('status') != status_now:
                    status_now = homework.get('status')
                    status = parse_status(homework)
                    send_message(bot, status)
        except (BotException, TypeError) as error:
            # Я если честно думал, что если я наследую BotException от
            # Exception, то TypeError сюда попадет, т.к. она входит в
            # иерархию Exception
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            if str(error) not in error_send_message_in_tg:
                # В задании просят, чтобы сообщение об ошибке в телеграм
                # отправлялось 1 раз только, а логировалось постоянно.
                # Поэтому я создаю пустой список, добавляю в него ошибки,
                # которые уже отправлялись в телеграм при этом их нет в этом
                # списке, т.е. они новые и еще не отправлялись в телеграм
                try:
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                except telegram.error.TelegramError:
                    logger.error('Сбой в отправке сообщения об ошибке')
                error_send_message_in_tg.append(str(error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

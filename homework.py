import logging
import os
import sys
import time
from typing import Any

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

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
        return True
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


def check_response(response: dict) -> dict:
    """Проверка ответа API."""
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарем.')
        raise TypeError('Ответ API не является словарем.')
    elif not isinstance(response.get('homeworks'), list):
        logger.error('Ответ API получен не в списке.')
        raise TypeError('Ответ API получен не в списке.')
    elif response.get('homeworks') != []:
        result = response.get('homeworks')[0]
        return result
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
    error_send_message_in_tg = []
    if not check_tokens():
        logger.critical('Ошибка в переменных окружения.')
        raise BotException('Ошибка в переменных окружения.')
    while True:
        try:
            api_answer = get_api_answer(timestamp)
            timestamp = api_answer.get('current_date')
            # добавил изменение переменной timestamp, по логике он время
            # первого запроса оставит изначальным, а начиная со 2 запроса
            # будет его менять на предыдущий. Тогда мы избежим повторов статуса
            # или лучше делать проверку что прошлый статус != новому?
            homework = check_response(api_answer)
            if homework is not None:
                status = parse_status(homework)
                send_message(bot, status)
            # Все, понял, try будет пытаться выполнить весь код в своем блоке
            # не смотря на условие, как и с break в конце если без else
            time.sleep(RETRY_PERIOD)
        except BotException as error:
            # У меня же как получается, что BotException наследует
            # Exception. А где перехваты исключений, не входящих в Exception
            # там я делаю raise BotException, т.е. по идее сюда должны все
            # исключения прилетать
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            time.sleep(RETRY_PERIOD)
            if error not in error_send_message_in_tg:
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                error_send_message_in_tg.append(error)


if __name__ == '__main__':
    main()

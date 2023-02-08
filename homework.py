import logging
import os
import sys
import time
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
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot: telegram.Bot, message: str) -> None:
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
        raise BotException('Ошибка при запросе к API.')
    if response.status_code != HTTPStatus.OK:
        raise BotException('Статус код ответа API отличен от 200.')
    return response.json()


def check_response(response: dict) -> dict:
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем.')
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        raise TypeError('Ответ API получен не в списке.')
    return homework[0]


def parse_status(homework: dict) -> str:
    """Проверка статуса домашней работы."""
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS.get(homework.get('status'))
    if not homework_name:
        raise BotException('Ошибка запроса по ключу homework_name.')
    if not verdict:
        raise BotException('Нет корректного ключа status.')
    logger.info(f'Изменился статус работы "{homework_name}".{verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    timestamp = 0
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
            if homework.get('status') != status_now:
                status_now = homework.get('status')
                status = parse_status(homework)
                send_message(bot, status)
            else:
                logger.debug('Статус домашней работы не изменился')
        except (BotException, TypeError) as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            if str(error) not in error_send_message_in_tg:
                try:
                    send_message(bot, message)
                except telegram.error.TelegramError:
                    logger.error('Сбой в отправке сообщения об ошибке')
                error_send_message_in_tg.append(str(error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

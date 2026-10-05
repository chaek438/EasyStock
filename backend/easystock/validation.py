import re
from decimal import Decimal, InvalidOperation

class ApiError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def text(data, key, maximum=200, required=True):
    value = data.get(key, '')
    if not isinstance(value, str):
        raise ApiError(f'Поле «{key}» має бути текстом.')
    value = value.strip()
    if (required and not value) or len(value) > maximum:
        raise ApiError(f'Поле «{key}»: введіть від 1 до {maximum} символів.' if required else f'Поле «{key}»: максимум {maximum} символів.')
    return value

def integer(value, field='Кількість', minimum=0, maximum=1000000000):
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r'\d+', str(value)):
        raise ApiError(f'{field}: потрібне ціле число.')
    result = int(value)
    if not minimum <= result <= maximum:
        raise ApiError(f'{field}: допустиме значення від {minimum} до {maximum}.')
    return result

def cents(value):
    try:
        price = Decimal(str(value))
        if not price.is_finite() or price < 0 or price > 10000000 or price.as_tuple().exponent < -2:
            raise ApiError('Ціна має бути невід’ємною та містити не більше 2 знаків після коми.')
        return int(price * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise ApiError('Введіть коректну ціну.')

def email(data, required=True):
    value = text(data, 'email', 200, required).lower()
    if value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ApiError('Введіть коректну електронну адресу.')
    return value

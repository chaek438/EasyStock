# Діаграми актуального релізу

Виконав: Бондаренко Сергій

Architecture.png і Architecture.svg показують спрощений шлях складської операції через чотири компоненти. Для входу та читання каталогів Flask також звертається до моделей SQLAlchemy. Схема не описує всі HTTP-маршрути. Джерела: Architecture.dot та Architecture.puml.

ER.puml доповнює схему Lab3 таблицею stock_requests із складеним первинним ключем user_id + request_key, а також полями products.unit і products.created_at. Десять таблиць відповідають backend/easystock/models.py. Попередні діаграми Lab3 збережено без зміни.

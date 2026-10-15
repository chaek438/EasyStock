# Самоперевірка інкременту MVP

Виконав: Бондаренко Сергій

Issue: https://github.com/chaek438/EasyStock/issues/1

Гілка: https://github.com/chaek438/EasyStock/tree/test/1-mvp-smoke

## F1 Збереження після перезапуску

У попередніх виконаних API-тестах не завершувався й не запускався реальний HTTP процес. Додано scripts/smoke_mvp.py: власний Waitress, тимчасова SQLite база, повний restart і звірка stock=34 та історії. Результат: PASS.

## F2 Недоступність БД

Попередній тест інжектував IntegrityError і перевіряв 409. Додано test_database_failure_returns_503_and_rolls_back: OperationalError, HTTP 503, зрозуміле повідомлення без внутрішнього шляху чи типу винятку та повний rollback. Результат: PASS; 40 API-тестів.

## Межі висновку

Це письмова самоперевірка одного автора. Незалежний review іншою людиною не підтверджено. React DOM не є перевіркою верстки або Chromium/Firefox. Повторний POST не має idempotency key. Жодних фіктивних учасників або схвалень не додано.

Pull request: https://github.com/chaek438/EasyStock/pull/2

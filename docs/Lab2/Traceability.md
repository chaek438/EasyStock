# Трасування вимог до реалізації

Інтерв’ю та персони в `Original_report.pdf` є змодельованими навчальними артефактами. Усі 14 історій мають реалізацію у версії 1.0.

| ID | Функція | API / реалізація | Доказ |
|---|---|---|---|
| US-01 | Вхід | /auth/login, серверний сеанс | test_auth_success_wrong_and_logout, React DOM |
| US-02 | Товари | /products, пагінація | test_search_case_unicode_and_literal_wildcards |
| US-03 | Пошук | name_search casefold / SKU | API + React DOM uppercase українська |
| US-04 | Створення товару | POST /products, нульовий stock | test_product_crud_duplicate_sku_and_category, React DOM |
| US-05 | Редагування | PUT /products/:id | API CRUD |
| US-06 | Категорії | /categories CRUD | test_category_supplier_crud |
| US-07 | Постачальники | /suppliers CRUD | test_category_supplier_crud |
| US-08 | Надходження | Stock Service, Receipt, Items | critical + multi-item + rollback + React DOM |
| US-09 | Списання | conditional SQL decrement | critical + concurrent + React DOM |
| US-10 | Автоматичний залишок | одна транзакція Stock + Movement | failure_between_stock_and_audit, concurrent |
| US-11 | Історія | /stock/history, автор/UTC/тип/кількість | critical + filters + React DOM |
| US-12 | Низький залишок | quantity <= min_stock | API filters, dashboard, badge |
| US-13 | Користувачі | /users, role/active/password | deactivation, self-protection |
| US-14 | Вихід | видалення серверного AuthSession | cookie replay test + React DOM |

| NFR | Перевірка |
|---|---|
| 01: p95 <=2с / 500 товарів | 30 запитів із 500 товарами, фактичний результат у TESTING.md |
| 02: цілісність | Від’ємний залишок, FK, відкат, конкурентне списання |
| 03: безпека | Хеші паролів, серверні ролі, CSRF, expiry, logout replay, блокування |
| 04: два браузери | Підготовлено сценарій Chromium / Firefox; запуск у середовищі заблоковано. Потрібен локальний прогін, деталі у TESTING.md |
| 05: поля після помилки | React DOM: quantity=40 і коментар збережені після відхилення |
| 06: аудит | автор, UTC-час, тип, кількість, залишок після, receipt_id |

MoSCoW та Given/When/Then з вихідного звіту збережено. Для людського review використайте сценарій у README та шаблон Lab3/Walkthrough.md.

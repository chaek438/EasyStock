# REST API EasyStock

Base URL: `http://127.0.0.1:5000/api`. Відповіді — JSON. Для операцій запису: `Content-Type: application/json`, cookie `easystock_session` та заголовок `X-CSRF-Token`, повернутий `auth/login` або `auth/me`. Токен сеансу не зберігається у localStorage. Login не вимагає CSRF, cookie має SameSite=Strict.

| Метод | Шлях | Доступ | Результат |
|---|---|---|---|
| GET | /health | Усі | Перевірка сервера |
| POST | /auth/login | Усі | `{email,password}` → `{user,csrf_token}` + HttpOnly cookie |
| GET | /auth/me | Авторизовані | Поточний користувач і CSRF |
| POST | /auth/logout | Авторизовані | Відкликання сеансу |
| GET | /dashboard | Авторизовані | Показники, low_products, recent, activity |
| GET | /products | Авторизовані | Пошук і пагінація |
| GET | /products/:id | Авторизовані | Деталі товару |
| POST | /products | Admin | Створення із stock=0 |
| PUT | /products/:id | Admin | Повна заміна полів каталогу |
| DELETE | /products/:id | Admin | Архівація при stock=0, історія збережена |
| GET | /categories, /suppliers | Авторизовані | `{items:[…]}` |
| POST | /categories, /suppliers | Admin | Створення |
| PUT | /categories/:id, /suppliers/:id | Admin | Редагування |
| DELETE | /categories/:id, /suppliers/:id | Admin | Видалення незв’язаних записів |
| POST | /stock/receipt | Admin, Keeper | Надходження, stock + audit + receipt |
| POST | /stock/writeoff | Admin, Keeper | Списання із перевіркою залишку |
| GET | /stock/history | Авторизовані | Історія та пагінація |
| GET, POST | /users | Admin | Список / створення |
| PUT | /users/:id | Admin | Поля, роль, активність, новий пароль |

Пагінація: `page=1`, `per_page=25` (максимум 100), відповідь `{items,total,page,per_page}`. Каталог: `q`, `category_id`, `status=available|low|empty`. `available` означає вище мінімального залишку; `low` включає нуль. Історія: `q`, `product_id`, `type=receipt|writeoff`, `from=YYYY-MM-DD`, `to=YYYY-MM-DD`. Дати фільтрів — UTC, межі дат включні; відображення часу — у локальній зоні браузера.

Товар:

```json
{"name":"SSD Kingston A400 480 GB","sku":"SSD-480","category_id":1,"supplier_id":1,"price":1450,"min_stock":5,"unit":"шт."}
```

Надходження:

```json
{"supplier_id":1,"items":[{"product_id":1,"quantity":20,"price":1250.50}],"note":"Накладна 001"}
```

Допускається скорочена форма `{product_id,quantity,price?,supplier_id?,note?}`. До 50 різних товарів. Якщо supplier_id не задано, береться постачальник першого товару. Ціна — закупівельна на момент надходження; не змінює ціну каталогу. Номер документа повертається як `receipt_id`.

Списання:

```json
{"product_id":1,"quantity":3,"note":"Продаж"}
```

Відповідь успіху складської операції (201):

```json
{"message":"Надходження збережено.","receipt_id":13,"items":[{"product_id":1,"quantity":37}]}
```

`items[].quantity` у відповіді — **новий залишок**, а не кількість руху.

Категорія: `{name}`. Постачальник: `{name,phone?,email?}`. Користувач: `{name,email,password,role}`; PUT також підтримує `active`. Ролі: `admin|keeper|manager`. Мінімум 8 символів пароля. Ніколи не повертаються хеші чи паролі.

Помилки: `{error:"Зрозуміле повідомлення"}`; 400 — валідація, 401 — відсутній/прострочений сеанс, 403 — роль/CSRF, 404 — запис відсутній, 409 — конфлікт або недостатній залишок, 429 — забагато спроб входу, 503 — БД тимчасово недоступна. При будь-якій помилці транзакція відкатується.

Сума грошей зберігається цілим числом копійок. Кількість — ціле число від 1 до 1 000 000 000 для руху; залишок від 0 до 1 000 000 000. SKU нормалізується у верхній регістр; назви шукаються через Unicode casefold, `%` і `_` трактуються буквально.

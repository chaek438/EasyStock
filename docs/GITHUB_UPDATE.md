# Як оновити EasyStock у GitHub

Виконав: Бондаренко Сергій

У папці `replacement-files` уже готові `.gitignore`, README, документація, звіти й скрипти очищення. Вміст цієї папки потрібно перенести в корінь EasyStock зі збереженням структури. Саму папку `replacement-files` у репозиторій не завантажуйте.

## Варіант через сайт GitHub

1. Відкрийте https://github.com/chaek438/EasyStock і гілку main.
2. Оновіть кореневий `README.md`: відкрийте файл, натисніть редагування й вставте текст із готового README. Збережіть коміт.
3. Створіть файл `.gitignore` у корені через **Add file → Create new file**, вставте готовий вміст і збережіть. Назва — саме `.gitignore`, без `.txt`.
4. Завантажте папки `docs` і `scripts` з `replacement-files` через **Add file → Upload files**, зберігаючи відносні шляхи. У результаті звіт 1 має бути саме в `docs/Lab1/Report.pdf`, а не в `replacement-files/docs/Lab1/Report.pdf`. Існуючі файли з однаковими шляхами потрібно замінити.
5. Видаліть із поточної версії репозиторію **лише** ці три файли: `database/easystock.db`, `database/easystock.db-wal`, `database/easystock.db-shm`. Відкрийте кожен файл, виберіть **… → Delete file** і збережіть коміт. `database/schema.sql` залиште.
6. Видаліть папку `backend/easystock/__pycache__` через меню **… → Delete directory**. Якщо кнопки видалення папки немає, видаліть сім `.pyc` файлів окремо; список наведено нижче. Файли `.py` у `backend/easystock` залиште.
7. Перевірте main: README і 3 PDF відкриваються, `.gitignore` є, трьох DB/WAL/SHM і папки `__pycache__` немає. Додавання `.gitignore` саме по собі не видаляє старі файли.

Після видалення службових файлів нова демобаза створиться при першому `run_demo.bat` / `--demo`. Раніше зроблені коміти залишаються в історії Git.

## Варіант через Git на комп’ютері

Якщо у вас лише папка з Download ZIP, спочатку отримайте Git-робочу копію:

```bash
git clone https://github.com/chaek438/EasyStock.git
cd EasyStock
```

Скопіюйте вміст `replacement-files` у цю папку. На Windows запустіть `scripts/cleanup_git.bat`; Linux/macOS:

```bash
bash scripts/cleanup_git.sh
```

Скрипти виконують `git rm --cached`: файли залишаються на комп’ютері, а видалення з індексу готується до коміту. Після цього:

```bash
git add .gitignore README.md docs scripts
git diff --cached --stat
git commit -m "Update reports and clean repository"
git push origin main
```

Команди commit і push потрібно виконати після перегляду підготовлених змін. Якщо Git повідомить, що remote має нові коміти, спочатку синхронізуйте main; force push не потрібен.

## Точний список службових файлів у перевіреній main

```text
database/easystock.db
database/easystock.db-wal
database/easystock.db-shm
backend/easystock/__pycache__/__init__.cpython-311.pyc
backend/easystock/__pycache__/auth.cpython-311.pyc
backend/easystock/__pycache__/models.cpython-311.pyc
backend/easystock/__pycache__/routes.cpython-311.pyc
backend/easystock/__pycache__/seed.cpython-311.pyc
backend/easystock/__pycache__/stock_service.cpython-311.pyc
backend/easystock/__pycache__/validation.cpython-311.pyc
```

## Створення дошки задач

1. У своєму профілі GitHub відкрийте **Projects → New project**. Оберіть **Board** і назвіть проєкт `EasyStock — практичні роботи`.
2. У **Settings → поле Status** налаштуйте значення: **Backlog**, **To Do**, **In Progress**, **Review/Test**, **Done**. У вигляді Board виберіть View → Column field → Status. Щоб показати всі п’ять колонок, скористайтеся кнопкою додавання колонок праворуч і позначте потрібні значення.
3. Додайте картки з `docs/PROJECT_BOARD.md`: назви, опис і початкові статуси вже готові. У кожній вкажіть «Виконав: Бондаренко Сергій»; якщо використовуєте Issues, призначте їх обліковому запису `chaek438`.
4. У налаштуваннях проєкту встановіть **Danger zone → Visibility → Public**, щоб викладач міг переглядати дошку без запрошення.
5. Відкрийте репозиторій EasyStock: **Projects → Link a project**, знайдіть і прив’яжіть створену дошку.
6. Скопіюйте фактичну адресу дошки з браузера й додайте в README рядок `Дошка задач: [GitHub Projects](фактична адреса)`. Сам номер проєкту не потрібно вгадувати.
7. Відкрийте код, PDF і дошку у приватному вікні браузера без входу, щоб перевірити доступ викладача.

Файл Markdown не створює інтерактивний GitHub Project. Для цих кроків потрібен ваш вхід у GitHub; сам проєкт до створення не заявлено як готовий.

## Документація

- Git ignore: https://git-scm.com/docs/gitignore
- Git rm: https://git-scm.com/docs/git-rm
- GitHub Projects: https://docs.github.com/en/issues/planning-and-tracking-with-projects/creating-projects/creating-a-project
- Статуси: https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields/about-single-select-fields
- Доступ: https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-your-project/managing-visibility-of-your-projects
- Прив’язування до репозиторію: https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-your-project/adding-your-project-to-a-repository
- Видалення файлів: https://docs.github.com/en/repositories/working-with-files/managing-files/deleting-files-in-a-repository

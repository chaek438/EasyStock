# Репозиторій EasyStock

Виконав: Бондаренко Сергій

Публічний репозиторій: https://github.com/chaek438/EasyStock. Викладач може переглядати код і PDF за посиланням.

## Отримання робочої копії

```bash
git clone https://github.com/chaek438/EasyStock.git
cd EasyStock
```

Готовий інтерфейс `frontend/dist` включено до main. Для першого демозапуску Node.js не потрібен; інструкція є в README.

## Збереження наступних змін

```bash
git status --short
git add .gitignore README.md docs scripts
git diff --cached --stat
git commit -m "Update reports and repository documentation"
git push origin main
```

Для локального завантаження через ZIP команда `git push` не працюватиме без Git-робочої копії. Можна оновити файли через вебінтерфейс GitHub за `docs/GITHUB_UPDATE.md`.

## Службові файли

У поточній версії `main` робочу БД, WAL/SHM та кеш Python уже видалено звичайними комітами. `database/schema.sql` залишається. `.gitignore` запобігає їх повторному додаванню. Для старих локальних Git-копій скрипти `scripts/cleanup_git.bat` і `scripts/cleanup_git.sh` прибирають ці файли з індексу, залишаючи локальні копії; після запуску потрібно закомітити зміни й виконати push.

## Історія та дошка

На перевіреній версії `8e8a046cee04` головна гілка мала один коміт `Add files via upload`. `docs/EasyStock.git.bundle` — збережений локальний знімок попередньої історії; він не є поточною історією main і не оновлюється автоматично. Для роботи з опублікованою версією слід клонувати GitHub-репозиторій за посиланням вище.

Публічну [дошку GitHub Projects](https://github.com/users/chaek438/projects/2/views/1) створено та пов’язано з EasyStock. Вона містить 5 колонок і 14 карток; усі призначені єдиному виконавцю `chaek438` — Бондаренку Сергію. Посилання є в README. Поточний план: [PROJECT_BOARD.md](PROJECT_BOARD.md).

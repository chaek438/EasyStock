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

`.gitignore` не припиняє відстежувати файли, які вже були закомічені. Скрипти `scripts/cleanup_git.bat` і `scripts/cleanup_git.sh` прибирають з індексу робочу БД, WAL/SHM та кеш Python, залишаючи локальні копії. Після запуску треба закомітити зміни й виконати push. `database/schema.sql` залишається.

## Історія та дошка

На перевіреній версії `8e8a046cee04` головна гілка мала один коміт `Add files via upload`. `docs/EasyStock.git.bundle` — збережений локальний знімок попередньої історії; він не є поточною історією main і не оновлюється автоматично. Для роботи з опублікованою версією слід клонувати GitHub-репозиторій за посиланням вище.

Готовий план для Projects: `docs/PROJECT_BOARD.md`. Інтерактивну дошку потрібно створити за `docs/GITHUB_UPDATE.md`, зв’язати з цим репозиторієм та додати її фактичне посилання в README.

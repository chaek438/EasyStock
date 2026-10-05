# Репозиторій

Підготовлена локальна Git-історія з окремими документаційним і реалізаційним комітами. У комплекті `EasyStock.git.bundle` — переносна копія репозиторію.

Відновлення (Git має бути встановлено):

```bash
git clone EasyStock/docs/EasyStock.git.bundle EasyStock-repository
```

Git-репозиторій містить вихідний код і документацію. Для нього frontend потрібно зібрати через npm; основна папка у ZIP уже містить готовий `frontend/dist`.

Власний remote можна додати після створення порожнього репозиторію у вашому GitHub/GitLab:

```bash
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

Фактичне зовнішнє посилання не задане. Не використовуйте приклад YOUR_REPOSITORY_URL як адресу.

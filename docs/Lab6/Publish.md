# Публікація EasyStock 1.0.0

Виконав: Бондаренко Сергій

Роботу виконано індивідуально. Код, тести, звіт і докази додано до main через [PR №3](https://github.com/chaek438/EasyStock/pull/3). Готовий проєкт і матеріали доступні в [GitHub Release v1.0.0](https://github.com/chaek438/EasyStock/releases/tag/v1.0.0).

## Відповідність перевіреному коду

Початковий перевірений локальний commit: `6d7f8d951a23f205477960efdc3ec79648f6bb78`. Публікація виконана вебкомітами через гілку release/lab6-v1.0.0, тому SHA комітів відрізняються. SHA-256 виконуваного коду, тестів, lockfile, схеми та готового frontend: `d728dc96c147a7d24a13144fdcb0946cd8116ab2ec0a2908e4ff2f979cd47f00`. Документація до цього відбитка не входить.

EasyStock_Lab6_History.bundle містить опубліковану main і початкову локальну історію тестів до виправлення. Локальна гілка evidence/lab6-verified-local та тег lab6-local-v1.0.0 зберігають первинне збирання; lab6-baseline позначає `0eabc81b33955948421838e0a98db920a799a640`. Ці локальні посилання є доказами в bundle, а не твердженням про окремі віддалені гілки чи теги.

## Отримання проєкту

Завантажити архів із релізу або виконати:

```bash
git clone https://github.com/chaek438/EasyStock.git
cd EasyStock
git switch --detach v1.0.0
```

Для відновлення повної історії без мережі:

```bash
git clone EasyStock_Lab6_History.bundle EasyStock
cd EasyStock
git switch main
```

Правила запуску й оновлення SQLite наведені в README та Release_Notes.md. Не надсилати початкову локальну історію поверх опублікованої main через force push.

# Запуск на VPS (PS Cloud / любой Ubuntu-сервер)

Почасовой сервер на время демо: создали → запустили → после показа удалили.

## 1. Создать сервер
PS Cloud (ps.kz) → Облачные серверы (VPC) → регион **Almaty**, ОС **Ubuntu 22.04/24.04**,
1–2 vCPU, 2 ГБ RAM, 20 ГБ диска, оплата **почасовая (PAYG)**. Открыть входящий порт **80** (и 22 для SSH).

## 2. Подключиться и установить Docker
```bash
ssh root@<IP_СЕРВЕРА>
curl -fsSL https://get.docker.com | sh
```

## 3. Скачать проект и заполнить ключи
```bash
git clone https://github.com/ylriad/ai-location-scout.git
cd ai-location-scout
cp .env.example .env
nano .env        # TWOGIS_API_KEY, ANTHROPIC_API_KEY, APIFY_API_TOKEN, JWT_SECRET
```
`JWT_SECRET` — любая длинная случайная строка, например вывод `openssl rand -hex 32`.

## 4. Собрать и запустить
```bash
docker build -t scout .
docker run -d --name scout --restart unless-stopped \
  -p 80:8000 --env-file .env -v scout-db:/app/db scout
```
Сайт: `http://<IP_СЕРВЕРА>/`. Логи: `docker logs -f scout`.

## Обновить после изменений в GitHub
```bash
cd ai-location-scout && git pull
docker build -t scout . && docker rm -f scout
docker run -d --name scout --restart unless-stopped \
  -p 80:8000 --env-file .env -v scout-db:/app/db scout
```
Аккаунты сохраняются в томе `scout-db` и переживают перезапуск.

## После презентации
Удалить сервер в панели PS Cloud — почасовая оплата прекратится.

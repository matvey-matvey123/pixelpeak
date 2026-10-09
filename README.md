# PixelPeak

Полноценный лаунчер Minecraft с собственными аккаунтами: десктоп-лаунчер (Python + PySide6),
бэкенд авторизации (FastAPI) и сайт регистрации.

```
PixelPeak/
├─ launcher/     десктоп-лаунчер (PySide6)
│  ├─ main.py            точка входа
│  ├─ core/              конфиг, API-клиент, авторизация, minecraft-lib
│  ├─ ui/                окна, тема, фоновые потоки
│  ├─ assets/            icon.ico / icon.png
│  ├─ tools/make_icon.py генерация иконки
│  ├─ build.ps1          сборка PixelPeak.exe
│  └─ requirements.txt
├─ server/       API и хостинг сайта (FastAPI + SQLite)
│  ├─ app.py             эндпоинты /api/*
│  ├─ database.py        пользователи и сессии
│  ├─ security.py        хеши паролей, токены
│  └─ requirements.txt
└─ site/         сайт регистрации/входа (статичный)
   ├─ index.html  login.html  register.html
   ├─ css/style.css
   └─ js/config.js  js/app.js
```

## Возможности лаунчера

- Вход по аккаунту PixelPeak (созданному на сайте или в лаунчере).
- Офлайн-вход по нику (без сервера).
- Выбор ника, версии игры, загрузчика: **Vanilla, Fabric, Forge, NeoForge**.
- Полный список релизов Minecraft, авто-скачивание версии и библиотек.
- Настройка ОЗУ, пути к Java, папки игры.
- Авто-поиск установленной Java.
- Прогресс установки и встроенная консоль игры.
- Запоминание сессии (не нужно логиниться каждый раз).

## Быстрый старт (локально)

### 1. Бэкенд + сайт

```powershell
cd server
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Сайт и API будут на `http://127.0.0.1:8000` (регистрация: `/register.html`).

### 2. Лаунчер

```powershell
cd launcher
python -m pip install -r requirements.txt
python main.py
```

Поле **API** внизу окна входа должно указывать на бэкенд (`http://127.0.0.1:8000`).

### 3. Собрать .exe

```powershell
cd launcher
powershell -ExecutionPolicy Bypass -File build.ps1
```

Готовый файл: `launcher/dist/PixelPeak.exe`.

## Иконка

Положи картинку в `launcher/assets/icon_source.png` и запусти:

```powershell
cd launcher
python tools/make_icon.py
```

Скрипт создаст `icon.png` и multi-size `icon.ico`. Пока исходника нет — используется
плейсхолдер `PP`.

## Сервер: настройки через переменные окружения

| Переменная          | Назначение                          | По умолчанию            |
|---------------------|-------------------------------------|-------------------------|
| `PIXELPEAK_SECRET`  | секрет для подписи токенов          | dev-значение (сменить!) |
| `PIXELPEAK_DB`      | путь к файлу SQLite                 | `server/pixelpeak.db`   |
| `PIXELPEAK_API`     | адрес API в лаунчере (по умолч.)    | `http://127.0.0.1:8000` |

> Обязательно задай свой `PIXELPEAK_SECRET` на продакшене.

## API

| Метод | Путь             | Тело / Заголовок                         | Ответ             |
|-------|------------------|------------------------------------------|-------------------|
| GET   | `/api/health`    | —                                        | `{status}`        |
| POST  | `/api/register`  | `{username,email,password}`              | `{token,user}`    |
| POST  | `/api/login`     | `{username,password}` (ник или email)    | `{token,user}`    |
| GET   | `/api/me`        | `Authorization: Bearer <token>`          | `{user}`          |
| POST  | `/api/logout`    | `Authorization: Bearer <token>`          | `{ok}`            |

## Деплой

См. `DEPLOY.md`.

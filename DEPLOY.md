# Деплой PixelPeak

Проект состоит из двух частей, которые хостятся по-разному:

1. **Сайт** (`site/`) — статика. Хостится на **Cloudflare Pages** или **GitHub Pages**.
2. **Бэкенд** (`server/`) — Python/FastAPI с базой. Нужен хост с Python:
   **Render**, **Railway**, **Fly.io**, VPS или любой сервер.

Лаунчер (`launcher/`) кладётся в **GitHub Releases** как `PixelPeak.exe`.

---

## 1. GitHub

```powershell
cd "C:\Users\GamerssPC\Documents\Default Project\PixelPeak"
git init
git add .
git commit -m "PixelPeak: launcher + server + site"
git branch -M main

# create repo (нужен свой токен)
$env:GH_TOKEN = "ghp_ТВОЙ_НОВЫЙ_ТОКЕН"
git remote add origin https://$env:GH_TOKEN@github.com/ТВОЙ_ЛОГИН/pixelpeak.git
git push -u origin main
```

> Токен НЕ попадает в репозиторий: он передаётся только через переменную окружения.
> Токен, опубликованный в чате, обязательно отзови и сделай новый.

Сборка лаунчера:

```powershell
cd launcher
powershell -ExecutionPolicy Bypass -File build.ps1
# загрузи dist/PixelPeak.exe в Releases репозитория
```

Затем укажи ссылку на файл в `site/js/config.js`:

```js
window.PIXELPEAK = {
  API_BASE: "https://ВАШ-БЭКЕНД",         // адрес бэкенда
  DOWNLOAD_URL: "https://github.com/ЛОГИН/pixelpeak/releases/latest/download/PixelPeak.exe",
};
```

---

## 2. Бэкенд (Render — бесплатно)

1. Зайди на https://render.com → **New → Web Service** → подключи GitHub-репозиторий.
2. Настройки:
   - **Root Directory:** `server`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
3. Переменные окружения (Environment):
   - `PIXELPEAK_SECRET` = длинная случайная строка
   - `PIXELPEAK_DB` = `/var/data/pixelpeak.db` (и подключи Disk, если нужен постоянный файл)
4. Deploy. Получишь адрес вида `https://pixelpeak.onrender.com`.

Аналогично на **Railway** (`server/Procfile` уже включён) или **Fly.io**.

Проверка: открой `https://АДРЕС/api/health` — должно вернуть `{"status":"ok"}`.

### Свой сервер / VPS

```bash
cd PixelPeak/server
pip install -r requirements.txt
export PIXELPEAK_SECRET="случайная-строка"
uvicorn app:app --host 0.0.0.0 --port 8000
```

Если бэкенд локальный, а сайт в интернете — выставь наружу через
**Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:8000`.

---

## 3. Сайт (Cloudflare Pages)

1. https://dash.cloudflare.com → **Workers & Pages → Create → Pages → Connect to Git**.
2. Выбери репозиторий `pixelpeak`.
3. Настройки сборки:
   - **Framework preset:** None
   - **Build command:** (оставь пустым)
   - **Build output directory:** `site`
4. Deploy. Получишь `https://pixelpeak.pages.dev`.

После деплоя обязательно впиши адрес бэкенда в `site/js/config.js` (`API_BASE`)
и закоммить — или задай на Pages «Environment variable» и подставляй её.

### GitHub Pages (альтернатива)

Settings → Pages → Source: `Deploy from a branch` → Branch: `main`, папка `/site`.
Либо через Actions с `actions/upload-pages-artifact`.

> Важно: и Cloudflare Pages, и GitHub Pages отдают только статику.
> FastAPI-бэкенд там не запустится — он живёт на Render/Railway/VPS.

---

## 4. Переменные окружения (сводка)

| Где          | Переменная          | Значение                                |
|--------------|---------------------|-----------------------------------------|
| Backend      | `PIXELPEAK_SECRET`  | секрет подписи токенов (обязательно)    |
| Backend      | `PIXELPEAK_DB`      | путь к SQLite                            |
| Launcher/сайт| `API_BASE`          | публичный адрес бэкенда                  |

## Чек-лист

- [ ] Отозвал старый токен, создал новый.
- [ ] Задал `PIXELPEAK_SECRET` на бэкенде.
- [ ] `/api/health` отвечает.
- [ ] `API_BASE` в `site/js/config.js` = адрес бэкенда.
- [ ] `DOWNLOAD_URL` указывает на `PixelPeak.exe` в Releases.
- [ ] В лаунчере поле API = адрес бэкенда.

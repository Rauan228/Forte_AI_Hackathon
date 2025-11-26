# Forte AI Assistant — Полная документация и инициализация

## Описание
Интерактивная платформа для сбора и формализации бизнес‑требований: чат с ИИ‑ассистентом, генерация BRD (цель, описание, scope, бизнес‑правила, KPI), артефакты (Use Case, user stories, диаграммы) и автоматический экспорт в Confluence.

## Архитектура
- Backend: FastAPI, SQLAlchemy, Markdown→HTML, интеграция с Confluence (REST API).
- AI: переключаемый провайдер (Gemini по `GEMINI_API_KEY`, OpenAI по `OPENAI_API_KEY`, иначе Mock).
- Frontend: React + Vite, Router, чат, превью документа, экспорт/скачивание PDF, темы.
- DB: SQLite по умолчанию, поддержка PostgreSQL.

## Инициализация
### Требования
- Python ≥ 3.10, Node.js ≥ 18
- Установить `pip`, `npm`

### Шаги
1) Зависимости backend
```
python -m pip install -r backend/requirements.txt
```
2) Зависимости frontend
```
cd frontend
npm install
```
3) Переменные окружения (создайте `backend/.env` по образцу `backend/.env.example`)
- `DATABASE_URL` — строка подключения, напр. `sqlite:///./dev.db` или `postgresql+psycopg2://user:pass@host:5432/db`
- `GEMINI_API_KEY` — ключ Google Gemini
- `OPENAI_API_KEY` — ключ OpenAI (опционально, как резерв)
- `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_SPACE_KEY`, `CONFLUENCE_PARENT_PAGE_ID` (опц.)
- `FRONTEND_ORIGIN` — напр. `http://localhost:5173`

4) Запуск backend
```
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
5) Запуск frontend
```
cd frontend
npm run dev
```
Откройте `http://localhost:5173/`

## Использование
- Главная `/`: кнопка «Начать сессию».
- Чат `/session/new` → автоматический редирект на `/session/:id` после первого сообщения.
- «Завершить и сгенерировать»: формирует документ и сохраняет его в системе, а при настроенной интеграции публикует страницу в Confluence.
- «Скачать PDF»: выгружает текущий документ.
- «Мои сессии»: список сессий, открыть/удалить.

## API Backend
- `POST /chat/message` — отправить сообщение.
  - Вход: `{"session_id":"опц.", "message":"строка"}`
  - Выход: `{"session_id":"...", "reply":"...", "finished":false}`
- `GET /chat/history/{session_id}` — история диалога.
- `POST /chat/finish` — сгенерировать документ, сохранить и опубликовать в Confluence.
  - Вход: `{"session_id":"опц.", "title":"опц."}`
  - Выход: `{"session_id":"...","title":"...","content_markdown":"...","confluence_url":"..."}`
- `GET /sessions` — список сессий.
- `DELETE /sessions/{id}` — удалить сессию.
- `GET /document/{session_id}` — получить сохранённый документ.

## Важные файлы
- Backend
  - `backend/app/main.py` — маршруты, CORS, генерация документа. Эндпоинт чата `backend/app/main.py:28`, история `backend/app/main.py:36`, завершение `backend/app/main.py:41`, список сессий `backend/app/main.py:69`, документ `backend/app/main.py:77`, удаление `backend/app/main.py:84`.
  - `backend/app/ai/model.py` — провайдеры ИИ, системный промпт, фолбэк.
  - `backend/app/models.py` — модели БД (`DialogSession`, `Message`, `RequirementDocument`).
  - `backend/app/schemas.py` — Pydantic‑схемы запросов/ответов.
  - `backend/app/config.py` — загрузка `.env`, ключи, CORS.
  - `backend/app/integrations/confluence.py` — публикация страницы через REST (storage format).
- Frontend
  - `frontend/src/App.jsx` — Router, Header, темы.
  - `frontend/src/pages/Home.jsx` — презентационный экран.
  - `frontend/src/pages/Sessions.jsx` — список сессий.
  - `frontend/src/pages/ChatSession.jsx` — чат, превью, экспорт, pdf, тосты, модалка.
  - `frontend/src/styles.css` — палитра, темы, анимации, шиммер, типинг.
  - `frontend/src/api.js` — API‑клиент.

## Интеграция Confluence
- Установите переменные `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_SPACE_KEY`, `CONFLUENCE_PARENT_PAGE_ID` (опционально).
- После `/chat/finish` документ публикуется; в ответе и в UI появится ссылка `confluence_url`.

## Настройка ИИ
- Приоритет: если установлен `GEMINI_API_KEY`, используется Gemini. Если Gemini недоступен на вашей учётке или даёт ошибку модели — выполняется фолбэк на OpenAI (если есть ключ) или Mock.
- Системный промпт настроен на сбор структуры требований: цель, описание, scope, бизнес‑правила, KPI, Use Case, user stories, диаграмма (текст), leading indicators.

## База данных
- SQLite по умолчанию: `sqlite:///./dev.db`
- Для PostgreSQL: `postgresql+psycopg2://user:pass@host:5432/db`

## Сборка и предпросмотр фронта
```
cd frontend
npm run build
npm run preview
```

## Безопасность
- Никогда не храните ключи в коде. Используйте `.env`.
- Не публикуйте секреты в репозиторий.

## Отладка
- Проверка бэкенда: `Invoke-RestMethod -Method Get -Uri http://localhost:8000/health`
- Типичные проблемы:
  - 422 на `/chat/finish`: исправлено, `title` и `session_id` — опциональные.
  - Ошибки Gemini моделей: включается фолбэк, сервер не падает.
  - `Failed to fetch` на фронте: обычно из-за 500 — устранено фолбэком.

## План дальнейших улучшений
- Потоковые ответы (SSE/WebSocket), богатые карточки/селекты в чате.
- Импорт файлов в диалог с парсингом.
- Рендер Markdown как безопасного HTML‑превью.
- Docker Compose для быстрой демонстрации.


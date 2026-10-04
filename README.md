# mcp-my-itmo

MCP-сервер для [my.itmo.ru](https://my.itmo.ru).
Даёт MCP-клиенту доступ к расписанию, зачётке, профилю, бронированию аудиторий, финансам,
учебному плану и другим разделам кабинета.

## Установка и запуск

Требования: Python >= 3.11 и [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python -m mcp_my_itmo
```

### Переменные окружения

Все настройки используют префикс `MY_ITMO_`.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `MY_ITMO_TRANSPORT` | `stdio` | Транспорт MCP: `stdio` или `streamable-http` |
| `MY_ITMO_MCP_HOST` | `127.0.0.1` | Хост MCP-сервера (только для streamable-http) |
| `MY_ITMO_MCP_PORT` | `8000` | Порт MCP-сервера (только для streamable-http) |
| `MY_ITMO_MCP_PATH` | `/mcp` | HTTP-путь эндпоинта (только для streamable-http) |
| `MY_ITMO_TOKEN_PATH` | `%APPDATA%\mcp-my-itmo\tokens.json` на Windows, `~/.config/mcp-my-itmo/tokens.json` в остальных случаях | Файл с токенами |
| `MY_ITMO_LOGIN_HOST` | `127.0.0.1` | Хост локальной страницы входа |
| `MY_ITMO_LOGIN_PORT` | `0` (случайный свободный порт) | Порт локальной страницы входа |
| `MY_ITMO_OPEN_BROWSER` | `true` | Автоматически открывать страницу входа в браузере |

Дополнительные переопределения (провайдер идентификации и API): `MY_ITMO_REALM_BASE`,
`MY_ITMO_CLIENT_ID`, `MY_ITMO_REDIRECT_URI`, `MY_ITMO_SCOPE`, `MY_ITMO_CODE_CHALLENGE_METHOD`,
`MY_ITMO_API_BASE`.

## Вход

У клиента ITMO в Keycloak отключены все прямые гранты (в том числе password grant), поэтому вход
идёт через форму, которую обслуживает сам сервер:

1. Вызовите тул `login`. Сервер поднимет небольшую страницу на localhost и вернёт её URL
   (и откроет её в браузере, если не задано `MY_ITMO_OPEN_BROWSER=false`).
2. Введите логин и пароль ITMO ID (и одноразовый код, если включён OTP) **на этой локальной
   странице**. Пароль не проходит ни через MCP-клиент, ни через модель.
3. Токены сохраняются локально в файле с правами `0600` и продлеваются автоматически.
4. Вызовите `auth_status`, чтобы убедиться, что вход выполнен. Страница входа закрывается по
   таймауту через 10 минут без входа.

Тул `logout` завершает сессию и удаляет сохранённые токены.

## Тулы

Тулы, помеченные **(изменяет данные)**, выполняют реальные действия от имени студента: в их
описаниях модели предписано показать пользователю точные параметры и получить явное
подтверждение до вызова.

### Авторизация

- `login()` — открыть локальную страницу входа, вернуть её URL.
- `auth_status()` — есть ли действующая сессия (ISU, имя пользователя, срок токена).
- `logout()` — завершить и удалить сохранённую сессию.

### Расписание

- `get_schedule(date_start?, date_end?)` — личное расписание по дням (даты `YYYY-MM-DD`; без аргументов — текущая неделя).

### Зачётка

- `list_specializations()` — программы обучения с семестрами; `actual` отмечает текущий.
- `get_record_book(specialization_id?, semester?)` — оценки по предметам.

### Профиль

- `get_profile()` — личные данные (имя, ISU, почты, группы).

### Бронирование

- `list_room_groups()` — верхний уровень каталога аудиторий.
- `list_room_categories(group_id)` — категории внутри группы.
- `list_rooms_in_category(category_id)` — аудитории с вместимостью, адресом и оборудованием.
- `search_rooms(category_id, day)` — занятость аудиторий на день.
- `list_my_bookings(date_start?, date_end?)` — мои бронирования (по умолчанию сегодня + 60 дней).
- `create_booking(room_id, day, time_from, time_to, name?, participants=1, contact_phone?)` — создать бронь **(изменяет данные)**.
- `cancel_booking(booking_id)` — отменить бронь **(изменяет данные)**.

### Финансы

- `get_scholarship_account()` — назначенные стипендии и их выплаты.
- `get_scholarship_income()` — история ежемесячных стипендиальных поступлений.
- `get_scholarship_totals(date_from?, date_to?)` — итоги по стипендиям по категориям.
- `list_edu_contracts()` — договоры на платное обучение (первый — текущий).
- `get_edu_payments()` — графики платежей за обучение и проживание.

### Учебный план

- `list_study_plans()` — доступные учебные планы; `is_active` отмечает текущий.
- `get_study_plan(semester?, plan_id?)` — дисциплины семестра: кредиты, часы, форма контроля.

### Персоналии

- `search_people(query, limit?)` — поиск по справочнику (студенты, преподаватели, сотрудники).
- `get_person(person_id)` — публичная карточка человека по ISU.

### Спорт

- `get_my_sport()` — сводка по физкультуре: семестр, баллы, попытки записи, долг.
- `list_sport_sections(date_from?, date_to?, building_id?, sport_type_ids?)` — занятия, открытые для записи.
- `get_sport_schedule(date_from?, date_to?)` — мои занятия, в том числе прошедшие.
- `enroll_sport_lessons(lesson_ids)` — записаться на занятия **(изменяет данные)**.
- `cancel_sport_lessons(lesson_ids)` — отменить запись на занятия **(изменяет данные)**.
- `enroll_sport_group(lesson_group_id)` — записаться в группу секции **(изменяет данные)**.
- `cancel_sport_group(lesson_group_id)` — отменить запись в группу **(изменяет данные)**.

### Записи по выбору

- `list_election_offers(kind="election")` — курсы, доступные для выбора (`election`, `intro`, `facultative`).
- `get_my_elections()` — мой выбор по всем трём потокам, окна записи, конфликты расписания.
- `choose_election(offer_id, kind="facultative")` — забронировать поток **(изменяет данные)**.
- `confirm_election(kind="facultative")` — подтвердить текущую бронь **(изменяет данные)**.
- `withdraw_election(choice_id, kind="facultative")` — отказаться от потока **(изменяет данные)**.

### Практики

- `get_my_practices()` — мои практики по учебным годам.
- `get_practice(practice_id)` — одна практика: место, кураторы, этап, индивидуальное задание.

### Общежитие

- `get_dormitory()` — статус заселения (очередь, здание, адрес).
- `get_dormitory_payments()` — договоры проживания и графики платежей.

### Заявки и очереди

- `list_request_types()` — типы заявок и справок.
- `get_request_form(type_id)` — поля формы типа заявки.
- `list_my_requests(status?)` — мои заявки (`in_progress`, `done`, `rejected`).
- `get_request(request_id)` — детали заявки: статус, цепочка согласования, поля.
- `create_request(type_id, params?)` — подать заявку **(изменяет данные)**.
- `list_queues()` — электронные очереди и мои записи в них.
- `get_queue(queue_id)` — очередь со свободными слотами.
- `join_queue(queue_id, time_table_id, phone, comment?, request_id?)` — записаться в очередь **(изменяет данные)**.
- `leave_queue(application_id)` — отменить запись в очередь **(изменяет данные)**.

### Соглашения

- `list_agreements()` — соглашения и согласия с историей версий и статусами.
- `accept_agreement(agreement_id)` — принять соглашение (юридически значимо) **(изменяет данные)**.

### Навигатор

- `navigator_search(query="")` — здания кампуса с картой, фильтр по подстроке названия.

### Дашборд

- `get_dashboard()` — раскладка виджетов главной страницы.
- `get_menu()` — боковое меню кабинета.

### QR-пропуск

- `get_qr_pass()` — цифровой пропуск; `qr_hex` — текст для кодирования в QR.

### Обходной лист

- `get_checkout_status()` — обходной лист: долги по подразделениям (`decision_id`: 1 проблема, 2 предупреждение, 3 закрыто).

## Настройка MCP-клиента

По умолчанию сервер работает по stdio, поэтому клиент сам запускает его командой:

```json
{
  "mcpServers": {
    "my-itmo": {
      "command": "uv",
      "args": ["run", "--directory", "D:/dev/mcp-my-itmo", "python", "-m", "mcp_my_itmo"]
    }
  }
}
```

Для Claude Code: `claude mcp add my-itmo -- uv run --directory D:\dev\mcp-my-itmo python -m mcp_my_itmo`.

### Опционально: streamable-http

Запустите сервер с `MY_ITMO_TRANSPORT=streamable-http` и укажите в клиенте URL:

```json
{
  "mcpServers": {
    "my-itmo": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

Для Claude Code: `claude mcp add --transport http my-itmo http://127.0.0.1:8000/mcp`.

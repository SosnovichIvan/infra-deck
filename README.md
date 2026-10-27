# InfraDeck

Единая панель управления проектами и серверами VPS/VM.

Первый релиз: регистрация, login/password + одноразовый Telegram-код (30 секунд),
проекты и серверы CRUD, проверка SSH перед сохранением, зашифрованные реквизиты.
React/TypeScript/Tailwind frontend, FastAPI/Python backend, PostgreSQL 17.
Тёмная тема по умолчанию, оранжевая палитра, стилизованные селекты.

- [Запуск, тесты и Telegram proxy](docs/operations.md)
- [Сценарии первого релиза](docs/product.md)
- [Архитектура](docs/architecture.md)
- [Безопасность](docs/security.md)
- [Проверки и evidence](docs/quality.md)
- [План](docs/roadmap.md)
- [Правила разработки](CONTRIBUTING.md)

Runtime: apps/web и services/control-plane. Contracts: contracts/openapi.json.
UI не хранит секреты в localStorage; API возвращает только metadata. Удаление
записей не выключает и не удаляет реальные машины.

Сервисы, agents, monitoring, Grafana и переносы — следующий этап, в этом релизе
отсутствуют. Production bot/proxy и deployment на ваши VPS не настроены этой
реализацией; для них нужны отдельные секреты InfraDeck и операторская приёмка.

Работа идёт через PR feature → develop → main. Quality gate обязателен;
владелец может сливать свои PR без чужого review. Прямой push запрещён.

# Проверка первого релиза — 2026-10-27

Локальная проверка завершена. Отдельный удалённый результат — в required
[Quality gate PR #3](https://github.com/SosnovichIvan/infra-deck/pull/3);
локальные команды его не заменяют.

Проверено:

- 25 component/transport tests Vitest5.0.5, V8: frontend >=98% lines,
  >=95% branches; весь apps/web/src.
- Cypress15.21.1/Electron138: один полный сценарий browser → API → PostgreSQL17
  → Telegram adapter/local stub и ephemeral SSH, прошёл (59s).
- SSH tests реально проверили password, private key и user certificate.
- Backend/API/DB: 47 pytest tests, coverage.py: 99.30% lines (708/713),
  95.27% branches (141/148). Пустой upgrade в отдельной disposable schema,
  повтор с данными и FK/unique/cascade constraints проверены на PostgreSQL17.
- Ruff, mypy strict, ESLint, TypeScript и FSD graph прошли.
- make check, actionlint1.7.7 и negative aggregate tests прошли.
- npm audit: 0 известных уязвимостей; pip-audit2.10.1 по production lock: 0 известных уязвимостей
  после обновления cryptography до 50.0.2.
- GitHub rulesets active, прочитаны через API; required Quality gate сохраняется.

Пока не проверено: реальная доставка Telegram через инфраструктуру оператора,
production HTTPS, VPS credentials/network policy, restore backup с key files,
нагрузка, production SLO. Ротация Telegram и KMS adapter отсутствуют в v1.
Никаких реальных ключей, бот-токенов, сообщений или production миграций в tests.
# Production packaging verification — 2026-10-30

Локально scripts/production-smoke.sh прошёл на синтетических данных: сборка API/web/proxy,
инициализация PostgreSQL17 с раздельными ролями, двукратная migration, чтение таблиц
ролью app без superuser/CREATEDB/CREATEROLE/CREATE schema, API UID10001, web health,
SPA fallback и HTTP401 для /api/auth/me. SSH proxy image дополнительно проверен
через ssh -G без внешнего подключения. Production container smoke включён в Quality gate.
make check (9 tests), actionlint1.7.7 и shell syntax checks прошли. Эти проверки
не являются доказательством реальной Telegram-доставки или production deployment.

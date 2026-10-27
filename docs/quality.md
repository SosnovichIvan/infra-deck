# Матрица PR-проверок

Обязательный status context: `Quality gate` от GitHub Actions. Он требует success
всех jobs: Branch policy, Repository checks, Workflow validation, Backend and
PostgreSQL, Frontend, Cypress integration. Failure/cancelled/skipped/unknown
отклоняются отдельным тестируемым aggregate. Никаких path filters и production
secrets. Собственный PR владельца можно сливать без чужого approval; checks
по-прежнему обязательны. Remote rulesets перечитаны 2026-10-27: active на
main/develop, Quality gate App15368, no force/delete, review-only owner exception.

| Root | Команды | Зависимости / evidence | Coverage / gate |
| --- | --- | --- | --- |
| docs, rules, scripts/tests | make check | Python3.12+, inventory, links, manifests, JSON, branch/gate/coverage-negative tests | Runtime metrics N/A для docs; Repository checks |
| services/control-plane/src | make backend | uv0.13.6, Python3.12, Ruff/mypy, pytest API/Identity/Inventory/crypto, PostgreSQL17, real ephemeral SSH, controlled Telegram HTTP transport | >=90% lines и branches независимо; Backend and PostgreSQL |
| PostgreSQL migrations | тот же pytest | Новая схема upgrade001, повтор с данными, composite FK/unique/cascade, concurrent OTP/proof consume | DDL инварианты, SQL coverage N/A; Backend |
| apps/web/src | make frontend | Node24.12.0, npm lock; ESLint/TS/FSD/cycle/name checks, Vitest5 V8, Testing Library | >=90% lines/branches; весь src включая main и неимпортированные файлы |
| API contracts | export_openapi.py + npm run generate | OpenAPI Pydantic и generated TS diff проверяются в CI | Generated d.ts не исполняется; Backend + Frontend |
| apps/web/cypress + test harness | make e2e | Настоящие API/PostgreSQL17/Telegram adapter до local HTTP stub, ephemeral SSH; browser Electron, никаких intercept-success API | Cypress integration, обязательный |
| .github/workflows | actionlint1.7.7 | pinned full action SHAs, contents:read, timeouts, healthchecks | Workflow validation |
| deploy | compose config/operator templates | local isolated PostgreSQL; proxy overlay без публикуемых ports и credentials | Проверка конфигурации; реальный VPS не проверен |

Frontend exclusions: generated/non-executable *.d.ts, *.test.ts(x) и test-setup.ts;
не исключаются main, API client, страницы и компоненты. JSON coverage summary
содержит все исходники (text reporter может скрывать файлы со 100%).
Backend coverage.py7: source=infradeck, branch=true, без исключения модулей;
check_coverage.py отдельно сверяет точные отношения, округлённый combined coverage
не является достаточным. Нулевой denominator — ошибка, не 100%.

Cypress критический путь: регистрация → Telegram /start webhook → отправка OTP
через реальный Bot API adapter в локальный stub → ввод кода → проекты CRUD →
fingerprint/trust/SSH authentication → серверы CRUD/recheck → logout/login.
Mobile390 и dark/light смена, keyboard Select/Escape проверяются компонентами.
Отдельные backend tests проверяют Telegram forbidden/rate-limit/failure/proxy
ошибки, update replay и permissions; UI тесты их не заменяют.

Миграция001 создаёт новую схему: предыдущего runtime не было. Для новой версии
добавляется новый SQL, применённый 001 не редактируется. Upgrade на пустой БД и
повторный upgrade с сохранением данных входят в tests; restore общей БД не
выполнялся. RLS не используется: изоляцию обеспечивает owner-scoped application
API и composite FK; не выдаётся за проверенную RLS-policy.

Локальные результаты и удалённый CI фиксируются в [verification](verification.md).
Production acceptance (собственный bot, HTTPS webhook, private proxy, KEK backup
и разрешённый VPS) отдельно от synthetic PR tests и пока не выполнена.
Релизные wheel/static artifacts собираются только workflow release.yml по
MAJOR.MINOR.PATCH tag коммита из main; обычный PR делает только verification build.

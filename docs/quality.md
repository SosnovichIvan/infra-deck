# Матрица PR-проверок

Текущая фаза — bootstrap. Единственный обязательный status context:
`Quality gate`, источник GitHub Actions. Он зависит от Branch policy,
Repository checks и Workflow validation и требует success каждого job;
failure/cancelled/skipped не дают зелёный gate. Workflow работает на каждом PR
в develop/main, без paths filters, и вручную для проверки настройки.

| Компонент / root | Статус | Проверки / зависимости | Coverage | Gate |
| --- | --- | --- | --- | --- |
| Документация и rules | implemented | make check: JSON, локальные ссылки своих docs, skills presence, inventory, unittest, git diff --check; Python 3.12+ | N/A — не продуктовый runtime | Repository checks → Quality gate |
| GitHub Actions | implemented | actionlint 1.7.7; pin checkout SHA; read-only token; без deploy/secrets | N/A — YAML | Workflow validation → Quality gate |
| Web apps/web | planned, отсутствует | Lint/types, Vitest/component, Cypress через test backend, FSD import graph; locked Node/toolchain | ≥90% lines/branches отдельно | Добавить до первого runtime PR |
| API + worker services/control-plane | planned, отсутствует | Ruff/mypy, pytest API и worker, PostgreSQL integration, OpenAPI client diff, restart/retry | ≥90% lines/branches | Добавить до первого runtime PR |
| Agent services/agent | planned, отсутствует | Lint/types/unit, mTLS/contract, upgrade и SSH install на ephemeral VM | ≥90% lines/branches отдельно | Добавить до первого runtime PR |
| DB migrations | planned, отсутствуют | PostgreSQL, empty/populated upgrade, constraints, tenant isolation, drift/recovery | DDL N/A; migrator/repository ≥90% | Добавить вместе с backend |
| Contracts и infra | planned, отсутствуют | Schema compatibility, config/shell validators, isolated startup/health, Grafana isolation | Собственная runtime-логика по правилам delivery | Добавить при реализации |

Команды bootstrap определены в Makefile. Whitespace проверяется на PR diff;
неизменённые внешние snapshots skills исключены из этой проверки (в исходнике
есть trailing whitespace), их целостность проверяется SHA-256 manifest. Код внутри установленных skills —
внешние инструменты агента, не runtime продукта; он не выдаётся за протестированное
приложение. CI отклоняет новый путь за пределами текущего bootstrap allowlist;
при добавлении компонентов надо одновременно расширить scope и реальные jobs.

Пока нет runtime, product tests, нагрузочные тесты и product coverage — planned,
не «пройдены». Секреты production, внешние VPS и publish в PR запрещены.
Release workflow пока отсутствует, выпуск невозможен; будущий релиз допускается
только по immutable MAJOR.MINOR.PATCH tag на коммите из актуальной main.

Защита хранится в .github/rulesets/*.json: отдельный ruleset с PR без bypass,
checks, resolution, запретами force push/deletion и отдельный review ruleset
с исключением владельца только через PR. Исключение GitHub привязано к actor,
поэтому технически действует и на чужие PR, которые он сливает; правила проекта
разрешают применять его только к собственным PR. Проверки обходить нельзя.
Результаты настройки записываются в docs/bootstrap-verification.md.

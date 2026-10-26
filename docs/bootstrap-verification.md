# Проверка bootstrap

Дата: 2026-10-26. Репозиторий: SosnovichIvan/infra-deck, public.

Локально прошли make check (8 тестов) и actionlint 1.7.7. Проверены разрешённые
и запрещённые направления PR, запрет появления незарегистрированного runtime,
а также реальный код aggregate gate: success всех зависимостей допускается;
failure/cancelled/skipped/unknown и отсутствие зависимостей отклоняются.
Snapshots 11 skills проверяются по SHA-256 installation manifest.

[GitHub Actions bootstrap run](https://github.com/SosnovichIvan/infra-deck/actions/runs/40283908770):
Branch policy, Repository checks, Workflow validation, Quality gate — success.
Источник Quality gate подтверждён check-runs API: github-actions, App ID 15368.

Enforcement verified через повторный GET rulesets и effective branch rules
для обеих веток main/develop:

- Ruleset 25862257 active: обязательный PR, Quality gate от App 15368,
  strict up-to-date checks, разрешение review threads, запрет non-fast-forward
  и deletion. Bypass actors отсутствуют, включая владельца и администраторов.
- Ruleset 25862260 active: одно approval, dismissal stale reviews; только
  владелец (User 103642906) имеет bypass, только в pull_request mode.
- Merge method — merge commit; squash/rebase отключены для сохранения
  истории develop → main. Файлы desired config — .github/rulesets/*.json.

Native reviewer bypass действует на actor, а не автора PR; проектное правило
ограничивает его использование собственными PR владельца. Обход checks и
прямой push через это исключение недоступны. Установленные review skills
не являются автоматически подключённым AI reviewer GitHub App.

Защита direct/force push и deletion подтверждена API-конфигурацией; фактические
запрещённые push/delete не выполнялись. Неверные branch routes проверены локально,
без создания заведомо ошибочных PR. Теги и deploy не выпускались.

Продуктовые API/UI/agent/БД пока не реализованы. Их tests/coverage/E2E остаются
planned и добавляются вместе с компонентами; bootstrap checks их не заменяют.

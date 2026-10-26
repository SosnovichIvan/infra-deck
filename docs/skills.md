# Skills и правила

Источник: локальный каталог `/Users/ivansosnovich/Documents/codex/skils`,
Базовый commit `1eda5e0116ed60da34fd1c68bec67656aa9b6791`, с локальными
незакоммиченными изменениями источника на момент установки. Точные установленные
файлы определяются SHA-256 manifest, а не только базовым commit.
Установка через его `install.py`, adapter codex, профиль standard.
Фактические версии, выбранные references и SHA-256 записаны в
[manifest](../.agents/skills/.agent-skills-lab.json).

| Skill | Задача |
| --- | --- |
| project-architecture | Границы, контракты, ADR и отказные сценарии |
| frontend-engineering | React, TypeScript, FSD |
| backend-engineering | Python API, worker и agent |
| database-engineering | PostgreSQL, индексы, миграции |
| ui-ux-design | Плотные панели, таблицы, графики, доступность |
| ux-writing | Формы регистрации, ошибки, риски и подтверждение переноса |
| icon-system | Согласованные иконки статусов и действий |
| frontend-review | Проверка UI и функциональных регрессий |
| backend-review | Проверка прав, контрактов, retries и concurrency |
| database-review | Проверка SQL, tenant isolation и rollout |
| ci-engineering | Матрица компонентов и обязательные merge checks |

Правила установленных профилей и delivery включены в AGENTS.md.
Проектное уточнение владельца: собственные PR SosnovichIvan не требуют
чужого approval; tests/checks и запреты прямого push сохраняются.

Skills ревью используются при соответствующих задачах агентом. Их установка
не означает подключённый автоматический AI review GitHub App. Детерминированные
CI-проверки работают отдельно. Логотип, контент-маркетинг, бот-интеграции и
orchestration не добавлены: они не нужны для текущей подготовки проекта.

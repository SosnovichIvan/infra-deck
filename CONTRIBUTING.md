# Разработка и PR

Прочитайте [AGENTS.md](AGENTS.md), [безопасность](docs/security.md) и
[матрицу проверок](docs/quality.md).

Рабочая ветка `codex/<topic>` или `feature/<topic>` → PR в `develop`.
В `main` допускается только PR из `develop` того же репозитория.
Прямые push в обе ветки, force push и удаление запрещены.
`main` и `develop` сохраняют историю через merge commits.

Любой PR требует зелёный Quality gate и разрешённые review threads.
Собственные PR владельца `SosnovichIvan` можно сливать без чужого approval.
Для остальных PR нужно одно approval; owner bypass по ревью не применяется
к чужим PR. Review exemption не даёт bypass проверок или прямого push.
Настройка protection требует admin API, обычные изменения — только через PR.

Перед PR: `make check`, затем все проверки изменённых компонентов из матрицы.
Новый runtime и его реальные проверки добавляются одним PR. Не отмечайте
planned проверки пройденными. Build для проверки допустим, publish/deploy
и production migrations в PR запрещены. Версионные релизы — только по тегу
MAJOR.MINOR.PATCH на коммите main через .github/workflows/release.yml.

Bootstrap: первый коммит только с README создаёт новые ветки до защиты;
основа проекта доставляется последующим PR с checks. Это однократная
инициализация пустого репозитория, не исключение для дальнейшей разработки.

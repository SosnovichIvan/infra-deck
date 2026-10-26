# План реализации

Все этапы planned. Каждый реализуется отдельными небольшими PR с тестами.

1. Выбрать стек ADR, версии, Linux targets и масштаб. Добавить API/worker,
   PostgreSQL harness, OpenAPI и миграции с проверками пустой/заполненной БД.
2. Identity и tenant isolation. Регистрация, вход/выход, формы и реальная
   browser → backend → test DB проверка в Cypress.
3. Реестр серверов, зашифрованные credentials, KMS adapter и SSH bootstrap
   на одноразовой VM. Тестировать отказ/повтор без production credentials.
4. Agent enrollment/mTLS, heartbeat, discovery Linux/systemd и Docker/Compose,
   observed/stale/unknown в UI; compatibility/contract и upgrade tests.
5. Telemetry, отдельные определения registered/active users, dashboard binding
   и Grafana authorization; объяснимые capacity recommendations.
6. Migration plan и preflight; сначала один stateless adapter с cutover/recovery.
   Затем stateful adapter с consistency, backup/restore и failure injection.
7. End-to-end staging, threat review, нагрузочные измерения, recovery rehearsal,
   runbooks и релиз по тегу из main.

При реализации любого runtime одновременно заменить planned в матрице на
реальные команды, включить их в Quality gate и измерить coverage отдельно.
Приёмка этапа с UI включает loading/empty/error/stale, keyboard/focus и
responsive состояния. Синтетические данные и одноразовые узлы обязательны.

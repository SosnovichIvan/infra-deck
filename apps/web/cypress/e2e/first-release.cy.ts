/// <reference types="cypress" />
const password = "Correct-password-2026!";
function button(name: string) {
  return cy
    .get("button")
    .filter((_, element) => element.textContent?.trim() === name)
    .last();
}
function field(name: string) {
  return cy
    .contains("label", new RegExp("^" + name + "$"))
    .invoke("attr", "for")
    .then((id) => cy.get("#" + CSS.escape(id!)));
}
function enterOtp() {
  field("Одноразовый код").should("be.enabled");
  cy.request("http://127.0.0.1:8188/messages").then(({ body }) => {
    expect(body.code).to.match(/^\d{8}$/);
    field("Одноразовый код").type(body.code);
    button("Подтвердить вход").click();
  });
}
describe("InfraDeck v1: browser → API → PostgreSQL → Telegram stub / SSH", () => {
  it("registers with Telegram OTP and manages projects and verified servers", () => {
    cy.visit("/");
    button("Создать аккаунт").click();
    field("Логин").type("e2e-user");
    field("Пароль").type(password, { log: false });
    field("Подтверждение пароля").type(password, { log: false });
    button("Создать аккаунт").click();
    cy.contains("a", "Открыть Telegram")
      .invoke("attr", "href")
      .then((href) => {
        const token = new URL(href!).searchParams.get("start");
        cy.request({
          method: "POST",
          url: "/api/telegram/webhook",
          headers: { "X-Telegram-Bot-Api-Secret-Token": "s".repeat(32) },
          body: {
            update_id: 1,
            message: {
              message_id: 1,
              date: 1,
              chat: { id: 1234, type: "private" },
              from: { id: 1234, is_bot: false, first_name: "Synthetic" },
              text: "/start " + token,
            },
          },
        });
      });
    button("Telegram привязан — получить код").click();
    enterOtp();
    cy.contains("h1", "Сохраните коды восстановления").should("be.visible");
    button("Я сохранил коды").click();
    cy.contains("h1", "Проекты").should("be.visible");
    button("Создать проект").click();
    field("Название проекта").type("Platform");
    field("Описание").type("Production tools");
    button("Создать проект").click();
    cy.contains("a", "Platform").click();
    cy.contains("h1", "Серверы").should("be.visible");
    button("Добавить сервер").click();
    field("Название сервера").type("App node");
    field("IP-адрес или hostname").type("synthetic-vm");
    cy.request("http://127.0.0.1:8188/messages").then(({ body }) =>
      field("Порт").clear().type(String(body.ssh_port)),
    );
    field("Логин SSH").type("deploy");
    field("Пароль SSH").type("synthetic-ssh-password", { log: false });
    button("Добавить сервер").should("be.disabled");
    cy.contains("label", "Метод входа")
      .invoke("attr", "for")
      .then((id) => {
        cy.get("#" + CSS.escape(id!)).click();
        cy.get("[role=listbox]").should("be.visible");
        cy.get("[role=option]").contains("SSH-ключ").click();
      });
    field("Приватный SSH-ключ").should("be.visible");
    cy.get("[role=combobox]").last().click();
    cy.get("[role=option]").contains("Пароль").click();
    field("Пароль SSH").type("synthetic-ssh-password", { log: false });
    button("Получить SSH fingerprint").click();
    cy.contains("Я сверил fingerprint").click();
    button("Проверить доступ по SSH").click();
    cy.contains("[role=status]", "Доступ по SSH подтверждён").should(
      "be.visible",
    );
    button("Добавить сервер").click();
    cy.contains("h2", "App node").should("be.visible");
    button("Проверить связь").click();
    cy.contains("[role=status]", "Подключение к серверу проверено").should(
      "be.visible",
    );
    cy.get('[aria-label="Редактировать сервер App node"]').click();
    field("Название сервера").clear().type("App node renamed");
    button("Сохранить изменения").click();
    cy.contains("h2", "App node renamed").should("be.visible");
    cy.viewport(390, 844);
    cy.get('[aria-label="Светлая тема"]').click();
    cy.get("html").should("have.attr", "data-theme", "light");
    cy.get('[aria-label="Тёмная тема"]').click();
    cy.document().then((doc) =>
      expect(doc.documentElement.scrollWidth).to.be.at.most(390),
    );
    cy.screenshot("servers-mobile-dark");
    cy.viewport(1280, 720);
    cy.get('[aria-label="Удалить сервер App node renamed"]').click();
    cy.contains("Сам VPS или VM продолжит работать").should("be.visible");
    button("Удалить сервер").click();
    cy.contains("Добавьте первый сервер").should("be.visible");
    cy.contains("a", "Все проекты").click();
    cy.get('[aria-label="Редактировать проект Platform"]').click();
    field("Название проекта").clear().type("Platform renamed");
    button("Сохранить изменения").click();
    cy.get('[aria-label="Удалить проект Platform renamed"]').click();
    button("Удалить проект").click();
    cy.contains("Создайте первый проект").should("be.visible");
    cy.get('[aria-label="Выйти"]').click();
    field("Логин").type("e2e-user");
    field("Пароль").type(password, { log: false });
    button("Войти").click();
    enterOtp();
    cy.contains("h1", "Проекты").should("be.visible");
    cy.contains("Создайте первый проект").should("be.visible");
    for (const name of ["Platform", "Staging", "Sandbox"]) {
      button("Создать проект").click();
      field("Название проекта").type(name);
      button("Создать проект").click();
      cy.contains("a", name).should("be.visible");
    }
    cy.screenshot("projects-desktop-dark");
  });
});

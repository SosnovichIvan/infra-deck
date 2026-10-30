import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ServerForm } from "./server-form";
import { api, encryptConnection, type Server } from "../../shared/api/client";
vi.mock("../../shared/api/client", () => ({
  api: vi.fn(),
  encryptConnection: vi.fn(),
}));
const mock = vi.mocked(api);
const sample: Server = {
  id: "s",
  project_id: "p",
  name: "Web",
  kind: "VM",
  host: "old.example",
  port: 22,
  username: "deploy",
  method: "password",
  fingerprint: "SHA256:old",
  checked_at: 1,
};
function setup(server?: Server) {
  const close = vi.fn(),
    cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={cache}>
      <ServerForm projectId="p" server={server} onClose={close} />
    </QueryClientProvider>,
  );
  return { close, user: userEvent.setup() };
}
beforeEach(() => {
  mock.mockReset();
  vi.mocked(encryptConnection).mockReset().mockResolvedValue("encrypted");
});
async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Название сервера"), "New");
  await user.type(
    screen.getByLabelText("IP-адрес или hostname"),
    "example.com",
  );
  await user.type(screen.getByLabelText("Логин SSH"), "deploy");
  await user.type(screen.getByLabelText("Пароль SSH"), "secret");
}
async function choose(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  option: string,
) {
  await user.click(screen.getByRole("combobox", { name: label }));
  await user.click(screen.getByRole("option", { name: option }));
}
it("gates save, trusts fingerprint, checks encrypted credentials and invalidates after edit", async () => {
  const { user, close } = setup();
  expect(
    screen.getByRole("button", { name: "Добавить сервер" }),
  ).toBeDisabled();
  await fill(user);
  mock.mockResolvedValueOnce({ fingerprint: "SHA256:trusted" });
  await user.click(
    screen.getByRole("button", { name: "Получить SSH fingerprint" }),
  );
  const trust = await screen.findByRole("checkbox");
  expect(
    screen.getByRole("button", { name: "Проверить доступ по SSH" }),
  ).toBeDisabled();
  await user.click(trust);
  mock.mockResolvedValueOnce({
    proof: "proof",
    fingerprint: "SHA256:trusted",
    expires_at: Date.now() / 1000 + 120,
  });
  await user.click(
    screen.getByRole("button", { name: "Проверить доступ по SSH" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent("подтверждён");
  expect(encryptConnection).toHaveBeenCalledWith(
    expect.objectContaining({
      password: "secret",
      fingerprint: "SHA256:trusted",
    }),
  );
  await user.type(screen.getByLabelText("Логин SSH"), "2");
  expect(
    screen.getByRole("button", { name: "Добавить сервер" }),
  ).toBeDisabled();
  mock.mockResolvedValueOnce({
    proof: "newproof",
    expires_at: Date.now() / 1000 + 120,
  });
  await user.click(
    screen.getByRole("button", { name: "Проверить доступ по SSH" }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Добавить сервер" }),
    ).toBeEnabled(),
  );
  mock.mockResolvedValueOnce({});
  await user.click(screen.getByRole("button", { name: "Добавить сервер" }));
  await waitFor(() => expect(close).toHaveBeenCalled());
  expect(mock).toHaveBeenLastCalledWith("/projects/p/servers", "POST", {
    name: "New",
    kind: "VPS",
    proof: "newproof",
  });
});
it("supports key, certificate and type selects, failures and proof expiry", async () => {
  const { user } = setup();
  await fill(user);
  await choose(user, "Тип сервера", "VM");
  await choose(user, "Метод входа", "SSH-ключ");
  expect(screen.queryByLabelText("Пароль SSH")).toBeNull();
  await user.type(screen.getByLabelText("Приватный SSH-ключ"), "private");
  await user.type(
    screen.getByLabelText("Пароль ключа (если задан)"),
    "passphrase",
  );
  await choose(user, "Метод входа", "SSH-сертификат");
  await user.type(
    screen.getByLabelText("Публичный SSH-сертификат"),
    "certificate",
  );
  await user.type(screen.getByLabelText("Приватный SSH-ключ"), "private2");
  mock.mockRejectedValueOnce(new Error("Нет связи"));
  await user.click(
    screen.getByRole("button", { name: "Получить SSH fingerprint" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Нет связи");
  mock.mockResolvedValueOnce({ fingerprint: "SHA256:key" });
  await user.click(
    screen.getByRole("button", { name: "Получить SSH fingerprint" }),
  );
  await user.click(await screen.findByRole("checkbox"));
  mock.mockResolvedValueOnce({ proof: "expired", expires_at: 1 });
  await user.click(
    screen.getByRole("button", { name: "Проверить доступ по SSH" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Проверка устарела",
  );
  expect(
    screen.getByRole("button", { name: "Добавить сервер" }),
  ).toBeDisabled();
  await user.click(screen.getByRole("checkbox"));
  expect(
    screen.getByRole("button", { name: "Добавить сервер" }),
  ).toBeDisabled();
  await user.type(screen.getByLabelText("IP-адрес или hostname"), "2");
  expect(screen.queryByRole("checkbox")).toBeNull();
});
it("edits metadata without prefilled secrets, warns about changed key and can cancel", async () => {
  const { user, close } = setup(sample);
  expect(screen.queryByLabelText("Пароль SSH")).toBeNull();
  await user.clear(screen.getByLabelText("Название сервера"));
  await user.type(screen.getByLabelText("Название сервера"), "Renamed");
  mock.mockRejectedValueOnce(new Error("Не сохранено"));
  await user.click(screen.getByRole("button", { name: "Сохранить изменения" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Не сохранено");
  expect(mock).toHaveBeenLastCalledWith("/projects/p/servers/s", "PUT", {
    name: "Renamed",
    kind: "VM",
    proof: null,
  });
  await user.click(
    screen.getByRole("checkbox", { name: "Изменить параметры подключения" }),
  );
  expect(screen.getByLabelText("Пароль SSH")).toHaveValue("");
  await user.clear(screen.getByLabelText("Порт"));
  await user.type(screen.getByLabelText("Порт"), "2222");
  mock.mockResolvedValueOnce({ fingerprint: "SHA256:new" });
  await user.click(
    screen.getByRole("button", { name: "Получить SSH fingerprint" }),
  );
  expect(await screen.findByText(/отличается от сохранённого/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Отмена" }));
  expect(close).toHaveBeenCalled();
});
it("saves edited credentials and clears proof when connection disabled", async () => {
  const { user, close } = setup(sample);
  await user.click(screen.getByRole("checkbox"));
  await user.type(screen.getByLabelText("Пароль SSH"), "new-secret");
  mock.mockResolvedValueOnce({ fingerprint: "SHA256:old" });
  await user.click(
    screen.getByRole("button", { name: "Получить SSH fingerprint" }),
  );
  await user.click((await screen.findAllByRole("checkbox"))[1]);
  mock.mockRejectedValueOnce(new Error("Ошибка SSH"));
  await user.click(
    screen.getByRole("button", { name: "Проверить доступ по SSH" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Ошибка SSH");
  mock.mockResolvedValueOnce({
    proof: "edit-proof",
    expires_at: Date.now() / 1000 + 120,
  });
  await user.click(
    screen.getByRole("button", { name: "Проверить доступ по SSH" }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    ).toBeEnabled(),
  );
  mock.mockResolvedValueOnce({});
  await user.click(screen.getByRole("button", { name: "Сохранить изменения" }));
  await waitFor(() => expect(close).toHaveBeenCalled());
  expect(mock).toHaveBeenCalledWith(
    "/projects/p/checks",
    "POST",
    expect.anything(),
  );
});

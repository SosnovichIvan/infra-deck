import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ServersPage } from "./servers-page";
import { api } from "../../shared/api/client";
vi.mock("../../shared/api/client", () => ({
  api: vi.fn(),
  encryptConnection: vi.fn(),
}));
const mock = vi.mocked(api);
const server = {
  id: "s",
  project_id: "p",
  name: "Web",
  kind: "VM",
  host: "example.com",
  port: 22,
  username: "deploy",
  method: "password",
  fingerprint: "SHA256:key",
  checked_at: 1,
};
function setup() {
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/projects/p"]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ServersPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return userEvent.setup();
}
beforeEach(() => mock.mockReset());
it("shows loading, empty, opens forms and supports cancel", async () => {
  let resolve: (v: unknown) => void = () => {};
  mock.mockResolvedValueOnce({ name: "Platform" }).mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const user = setup();
  expect(screen.getByRole("status")).toHaveTextContent("Загружаем серверы");
  resolve([]);
  expect(await screen.findByText("Добавьте первый сервер")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Добавить сервер" }));
  expect(screen.getByRole("dialog")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Закрыть" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});
it("checks existing server, handles failures, edits and deletes", async () => {
  mock.mockImplementation(async (path, method = "GET") => {
    if (path === "/projects/p") return { name: "Platform" };
    if (method === "GET") return [server];
    throw new Error("Нет связи");
  });
  const user = setup();
  await screen.findByRole("button", { name: "Проверить связь" });
  await user.click(screen.getByRole("button", { name: "Проверить связь" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Нет связи");
  mock.mockImplementation(async (path) =>
    path === "/projects/p"
      ? { name: "Platform" }
      : path?.endsWith("/recheck")
        ? server
        : [server],
  );
  await user.click(screen.getByRole("button", { name: "Проверить связь" }));
  expect(await screen.findByRole("status")).toHaveTextContent("проверено");
  await user.click(
    screen.getByRole("button", { name: "Редактировать сервер Web" }),
  );
  expect(screen.getByLabelText("Название сервера")).toHaveValue("Web");
  await user.click(screen.getByRole("button", { name: "Отмена" }));
  await user.click(screen.getByRole("button", { name: "Удалить сервер Web" }));
  await user.click(screen.getByRole("button", { name: "Отмена" }));
  await user.click(screen.getByRole("button", { name: "Удалить сервер Web" }));
  mock.mockRejectedValueOnce(new Error("Не удалено"));
  await user.click(screen.getByRole("button", { name: "Удалить сервер" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Не удалено");
  mock.mockResolvedValueOnce(undefined).mockResolvedValueOnce([]);
  await user.click(screen.getByRole("button", { name: "Удалить сервер" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(await screen.findByText("Добавьте первый сервер")).toBeVisible();
});
it("retries loading and pages forward and back", async () => {
  mock
    .mockResolvedValueOnce({ name: "Platform" })
    .mockRejectedValueOnce(new Error("Не загружено"));
  const user = setup();
  expect(await screen.findByRole("alert")).toHaveTextContent("Не загружено");
  const many = Array.from({ length: 100 }, (_, i) => ({
    ...server,
    id: String(i),
    name: "Server " + i,
  }));
  mock.mockResolvedValueOnce(many);
  await user.click(screen.getByRole("button", { name: "Повторить" }));
  await screen.findByRole("button", { name: "Далее" });
  mock.mockResolvedValueOnce([]);
  await user.click(screen.getByRole("button", { name: "Далее" }));
  expect(await screen.findByText("Больше серверов нет")).toBeVisible();
  mock.mockResolvedValueOnce(many);
  await user.click(screen.getByRole("button", { name: "Назад" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Назад" })).toBeDisabled(),
  );
});

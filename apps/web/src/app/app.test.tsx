import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Application, App, queryClient } from "./app";
import { api, ApiError } from "../shared/api/client";
vi.mock("../shared/api/client", async () => {
  const actual = await vi.importActual("../shared/api/client");
  return { ...actual, api: vi.fn() };
});
vi.mock("../pages/projects", () => ({ ProjectsPage: () => <h1>Проекты</h1> }));
vi.mock("../pages/servers", () => ({ ServersPage: () => <h1>Серверы</h1> }));
vi.mock("../pages/auth", () => ({
  AuthPage: ({ onAuthenticated }: { onAuthenticated: () => void }) => (
    <button onClick={onAuthenticated}>Тестовый вход</button>
  ),
}));
const mock = vi.mocked(api);
function setup() {
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={cache}>
      <Application />
    </QueryClientProvider>,
  );
  return { user: userEvent.setup(), cache };
}
beforeEach(() => {
  mock.mockReset();
  window.history.replaceState(null, "", "/");
  localStorage.clear();
  queryClient.clear();
});
it("handles pending, unauthenticated and login invalidation", async () => {
  mock.mockRejectedValueOnce(new ApiError("Войдите", 401));
  const { user } = setup();
  expect(screen.getByRole("status")).toBeVisible();
  await screen.findByRole("button", { name: "Тестовый вход" });
  mock.mockResolvedValueOnce({ id: "u" });
  await user.click(screen.getByRole("button", { name: "Тестовый вход" }));
  expect(await screen.findByRole("heading", { name: "Проекты" })).toBeVisible();
});
it("reports network issue and retries", async () => {
  mock.mockRejectedValueOnce(new Error("Нет сети"));
  const { user } = setup();
  expect(await screen.findByRole("alert")).toHaveTextContent("Нет сети");
  mock.mockResolvedValueOnce({ id: "u" });
  await user.click(screen.getByRole("button", { name: "Повторить" }));
  expect(await screen.findByRole("heading", { name: "Проекты" })).toBeVisible();
});
it("switches themes, handles logout failure then clears tenant cache", async () => {
  mock.mockResolvedValueOnce({ id: "u" });
  const { user, cache } = setup();
  await user.click(await screen.findByRole("button", { name: "Светлая тема" }));
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(localStorage.getItem("theme")).toBe("light");
  await user.click(screen.getByRole("button", { name: "Тёмная тема" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  mock.mockRejectedValueOnce(new Error("Не вышли"));
  await user.click(screen.getByRole("button", { name: "Выйти" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Не вышли");
  cache.setQueryData(["projects"], [{ name: "Private" }]);
  mock.mockResolvedValueOnce(undefined);
  await user.click(screen.getByRole("button", { name: "Выйти" }));
  expect(
    await screen.findByRole("button", { name: "Тестовый вход" }),
  ).toBeVisible();
  expect(cache.getQueryData(["projects"])).toBeUndefined();
});
it("renders app provider, direct server URL and unknown route", async () => {
  window.history.replaceState(null, "", "/projects/p");
  mock.mockResolvedValueOnce({ id: "u" });
  const result = render(<App />);
  expect(await screen.findByRole("heading", { name: "Серверы" })).toBeVisible();
  result.unmount();
  window.history.replaceState(null, "", "/unknown");
  mock.mockResolvedValueOnce({ id: "u" });
  const { user } = setup();
  expect(
    await screen.findByRole("heading", { name: "Страница не найдена" }),
  ).toBeVisible();
  await user.click(screen.getByRole("link", { name: "Вернуться к проектам" }));
  expect(await screen.findByRole("heading", { name: "Проекты" })).toBeVisible();
});
it("drops previous owner data when an expired session signs into another account", async () => {
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  cache.setQueryData(["me"], { id: "owner-a" });
  cache.setQueryData(["projects"], [{ name: "Private A" }]);
  mock.mockRejectedValueOnce(new ApiError("Expired", 401));
  render(
    <QueryClientProvider client={cache}>
      <Application />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await screen.findByRole("button", { name: "Тестовый вход" });
  mock.mockResolvedValueOnce({ id: "owner-b" });
  await user.click(screen.getByRole("button", { name: "Тестовый вход" }));
  expect(await screen.findByRole("heading", { name: "Проекты" })).toBeVisible();
  expect(cache.getQueryData(["projects"])).toBeUndefined();
});

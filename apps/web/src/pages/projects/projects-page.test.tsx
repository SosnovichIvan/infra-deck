import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProjectsPage } from "./projects-page";
import { api } from "../../shared/api/client";
vi.mock("../../shared/api/client", () => ({ api: vi.fn() }));
const mock = vi.mocked(api);
const project = { id: "p", name: "Platform", description: "Description" };
function setup() {
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <ProjectsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return userEvent.setup();
}
beforeEach(() => mock.mockReset());
it("loads, creates and edits project with validated error and close", async () => {
  let resolve: (v: unknown) => void = () => {};
  mock.mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const user = setup();
  expect(screen.getByRole("status")).toHaveTextContent("Загружаем");
  resolve([]);
  expect(await screen.findByText("Создайте первый проект")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Создать проект" }));
  await user.type(screen.getByLabelText("Название проекта"), "New");
  await user.type(screen.getByLabelText("Описание"), "Details");
  mock.mockRejectedValueOnce(new Error("Ошибка сохранения"));
  await user.click(screen.getByRole("button", { name: "Создать проект" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Ошибка сохранения",
  );
  mock.mockResolvedValueOnce(project).mockResolvedValueOnce([project]);
  await user.click(screen.getByRole("button", { name: "Создать проект" }));
  expect(await screen.findByRole("link", { name: "Platform" })).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Редактировать проект Platform" }),
  );
  expect(screen.getByLabelText("Название проекта")).toHaveValue("Platform");
  await user.clear(screen.getByLabelText("Название проекта"));
  await user.type(screen.getByLabelText("Название проекта"), "Renamed");
  mock.mockResolvedValueOnce(project).mockResolvedValueOnce([project]);
  await user.click(screen.getByRole("button", { name: "Сохранить изменения" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(mock).toHaveBeenCalledWith("/projects/p", "PUT", {
    name: "Renamed",
    description: "Description",
  });
});
it("retries load, confirms and cancels delete, has pagination", async () => {
  mock.mockRejectedValueOnce(new Error("Нет связи"));
  const user = setup();
  expect(await screen.findByRole("alert")).toHaveTextContent("Нет связи");
  mock.mockResolvedValueOnce([
    project,
    { id: "empty", name: "Empty", description: "" },
  ]);
  await user.click(screen.getByRole("button", { name: "Повторить" }));
  expect(await screen.findByText("Описание не добавлено")).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Удалить проект Platform" }),
  );
  expect(screen.getByText(/Сами VPS и VM/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Отмена" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  await user.click(
    screen.getByRole("button", { name: "Удалить проект Platform" }),
  );
  mock.mockRejectedValueOnce(new Error("Удаление не удалось"));
  await user.click(screen.getByRole("button", { name: "Удалить проект" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Удаление не удалось",
  );
  mock.mockResolvedValueOnce(undefined).mockResolvedValueOnce([]);
  await user.click(screen.getByRole("button", { name: "Удалить проект" }));
  expect(await screen.findByText("Создайте первый проект")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Создать проект" }));
  await user.click(screen.getByRole("button", { name: "Отмена" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});
it("paginates through bounded lists", async () => {
  const many = Array.from({ length: 100 }, (_, i) => ({
    ...project,
    id: String(i),
    name: "Project " + i,
  }));
  mock.mockResolvedValueOnce(many);
  const user = setup();
  expect(await screen.findByRole("button", { name: "Далее" })).toBeEnabled();
  mock.mockResolvedValueOnce([]);
  await user.click(screen.getByRole("button", { name: "Далее" }));
  expect(await screen.findByText("Больше проектов нет")).toBeVisible();
  mock.mockResolvedValueOnce(many);
  await user.click(screen.getByRole("button", { name: "Назад" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Назад" })).toBeDisabled(),
  );
});

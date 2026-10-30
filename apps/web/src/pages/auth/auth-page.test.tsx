import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthPage } from "./auth-page";
import { api } from "../../shared/api/client";
vi.mock("../../shared/api/client", () => ({ api: vi.fn() }));
const mock = vi.mocked(api);
beforeEach(() => {
  mock.mockReset();
});
async function credentials(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Логин"), "tester");
  await user.type(
    screen.getByLabelText("Пароль", { exact: true }),
    "Correct-password-2026!",
  );
}
it("registers, binds Telegram and enters OTP including leading zero, saves recovery codes", async () => {
  const user = userEvent.setup(),
    done = vi.fn();
  render(<AuthPage onAuthenticated={done} />);
  await user.click(screen.getByRole("button", { name: "Создать аккаунт" }));
  await credentials(user);
  await user.type(
    screen.getByLabelText("Подтверждение пароля"),
    "Correct-password-2026!",
  );
  mock.mockResolvedValueOnce({
    state: "enrollment",
    telegram_url: "https://t.me/test?start=abc",
    recovery_codes: [],
  });
  await user.click(screen.getByRole("button", { name: "Создать аккаунт" }));
  expect(
    await screen.findByRole("link", { name: "Открыть Telegram" }),
  ).toHaveAttribute("href", "https://t.me/test?start=abc");
  mock.mockResolvedValueOnce({
    state: "otp",
    expires_at: Date.now() / 1000 + 30,
    recovery_codes: [],
  });
  await user.click(
    screen.getByRole("button", { name: "Telegram привязан — получить код" }),
  );
  await user.type(await screen.findByLabelText("Одноразовый код"), "01234567");
  mock.mockResolvedValueOnce({
    state: "authenticated",
    recovery_codes: ["abc-recovery-code-1"],
  });
  await user.click(screen.getByRole("button", { name: "Подтвердить вход" }));
  expect(await screen.findByText("abc-recovery-code-1")).toBeVisible();
  expect(mock).toHaveBeenLastCalledWith("/auth/verify", "POST", {
    code: "01234567",
  });
  await user.click(screen.getByRole("button", { name: "Я сохранил коды" }));
  expect(done).toHaveBeenCalled();
});
it("handles login send failure, resend, recovery and cancellation", async () => {
  const user = userEvent.setup(),
    done = vi.fn();
  render(<AuthPage onAuthenticated={done} />);
  await credentials(user);
  mock
    .mockResolvedValueOnce({ state: "otp" })
    .mockRejectedValueOnce(new Error("Telegram недоступен"));
  await user.click(screen.getByRole("button", { name: "Войти" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Telegram недоступен",
  );
  expect(screen.getByLabelText("Одноразовый код")).toBeDisabled();
  mock.mockResolvedValueOnce({
    state: "otp",
    expires_at: Date.now() / 1000 + 30,
  });
  await user.click(screen.getByRole("button", { name: "Отправить новый код" }));
  await waitFor(() =>
    expect(screen.getByLabelText("Одноразовый код")).toBeEnabled(),
  );
  await user.click(
    screen.getByRole("button", { name: "Нет доступа к Telegram" }),
  );
  await user.type(
    screen.getByLabelText("Код восстановления"),
    "abcdef1234567890",
  );
  mock.mockResolvedValueOnce({ state: "authenticated", recovery_codes: [] });
  await user.click(screen.getByRole("button", { name: "Подтвердить вход" }));
  await waitFor(() => expect(done).toHaveBeenCalled());
  await user.click(
    screen.getByRole("button", { name: "Вернуться к коду Telegram" }),
  );
  mock.mockResolvedValueOnce(undefined);
  await user.click(screen.getByRole("button", { name: "Вернуться ко входу" }));
  expect(
    await screen.findByRole("heading", { name: "Войти в InfraDeck" }),
  ).toBeVisible();
});
it("rejects mismatched passwords, reports bad credentials and expires code", async () => {
  const user = userEvent.setup();
  render(<AuthPage onAuthenticated={vi.fn()} />);
  await user.click(screen.getByRole("button", { name: "Создать аккаунт" }));
  await credentials(user);
  await user.type(
    screen.getByLabelText("Подтверждение пароля"),
    "Other-password-2026",
  );
  await user.click(screen.getByRole("button", { name: "Создать аккаунт" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Пароли не совпадают",
  );
  await user.click(
    screen.getByRole("button", { name: "Уже есть аккаунт — войти" }),
  );
  await user.type(
    screen.getByLabelText("Пароль", { exact: true }),
    "Correct-password-2026!",
  );
  mock.mockRejectedValueOnce(new Error("Неверный логин или пароль"));
  await user.click(screen.getByRole("button", { name: "Войти" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Неверный логин");
  mock
    .mockResolvedValueOnce({ state: "otp" })
    .mockResolvedValueOnce({ state: "otp", expires_at: Date.now() / 1000 + 1 });
  await user.click(screen.getByRole("button", { name: "Войти" }));
  await waitFor(() =>
    expect(screen.getByLabelText("Одноразовый код")).toBeEnabled(),
  );
  await waitFor(
    () => expect(screen.getByLabelText("Одноразовый код")).toBeDisabled(),
    { timeout: 3000 },
  );
  expect(
    screen.getByRole("button", { name: "Отправить новый код" }),
  ).toBeEnabled();
  vi.useRealTimers();
});

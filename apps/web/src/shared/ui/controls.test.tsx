import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import {
  Button,
  Input,
  Textarea,
  Choice,
  Modal,
  ErrorMessage,
} from "./controls";
it("provides labeled controls, keyboard select and focus return", async () => {
  const user = userEvent.setup();
  const close = vi.fn();
  function Example() {
    const [value, setValue] = useState("a");
    return (
      <Modal title="Форма" description="Описание" onClose={close}>
        <Input label="Имя" autoFocus />
        <Textarea label="Текст" />
        <Choice
          label="Метод"
          value={value}
          onChange={setValue}
          options={[
            { value: "a", label: "Пароль" },
            { value: "b", label: "Ключ" },
          ]}
        />
        <Button>Сохранить</Button>
        <ErrorMessage error={new Error("Ошибка")} />
      </Modal>
    );
  }
  render(<Example />);
  expect(screen.getByLabelText("Имя")).toHaveFocus();
  expect(screen.getByLabelText("Текст")).toBeVisible();
  const select = screen.getByRole("combobox", { name: "Метод" });
  select.focus();
  await user.keyboard("{Enter}");
  expect(screen.getByRole("listbox")).toBeVisible();
  await user.keyboard("{ArrowDown}{Enter}");
  expect(select).toHaveTextContent("Ключ");
  expect(close).not.toHaveBeenCalled();
  await user.keyboard("{Enter}{Escape}");
  expect(screen.getByRole("dialog")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Закрыть" }));
  expect(close).toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent("Ошибка");
});
it("renders disabled/default/error variations", () => {
  render(
    <>
      <Button variant="danger" disabled>
        Удалить
      </Button>
      <Input label="Поле" hint="Текст" />
      <Choice
        label="Тип"
        value="a"
        onChange={() => {}}
        options={[{ value: "a", label: "A" }]}
        disabled
      />
      <ErrorMessage error="unknown" />
      <ErrorMessage error={null} />
    </>,
  );
  expect(screen.getByRole("button")).toBeDisabled();
  expect(screen.getByRole("combobox")).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Не удалось выполнить действие",
  );
});
it("returns focus to the opener and blocks closure during a pending save", async () => {
  const user = userEvent.setup();
  function Scenario() {
    const [open, setOpen] = useState(false);
    return (
      <main>
        <button onClick={() => setOpen(true)}>Открыть</button>
        {open && (
          <Modal
            title="Тест"
            description="Фокус"
            onClose={() => setOpen(false)}
          >
            <Input label="Значение" autoFocus />
          </Modal>
        )}
      </main>
    );
  }
  const view = render(<Scenario />);
  await user.click(screen.getByRole("button", { name: "Открыть" }));
  await user.click(screen.getByRole("button", { name: "Закрыть" }));
  expect(screen.getByRole("button", { name: "Открыть" })).toHaveFocus();
  view.unmount();
  const close = vi.fn();
  render(
    <Modal title="Сохранение" description="Подождите" onClose={close} busy>
      <p>Отправляем</p>
    </Modal>,
  );
  expect(screen.getByRole("button", { name: "Закрыть" })).toBeDisabled();
  await user.keyboard("{Escape}");
  expect(close).not.toHaveBeenCalled();
});

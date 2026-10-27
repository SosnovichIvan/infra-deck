import * as Select from "@radix-ui/react-select";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, ChevronDown, X } from "lucide-react";
import {
  useId,
  useRef,
  useLayoutEffect,
  type ComponentProps,
  type ReactNode,
} from "react";
export function Button({
  className = "",
  variant = "primary",
  ...props
}: ComponentProps<"button"> & {
  variant?: "primary" | "secondary" | "danger";
}) {
  return <button {...props} className={`button ${variant} ${className}`} />;
}
export function Input({
  label,
  hint,
  ...props
}: ComponentProps<"input"> & { label: string; hint?: string }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        aria-describedby={hint ? id + "-hint" : undefined}
        {...props}
      />
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </div>
  );
}
export function Textarea({
  label,
  ...props
}: ComponentProps<"textarea"> & { label: string }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <textarea id={id} {...props} />
    </div>
  );
}
export function Choice({
  label,
  value,
  onChange,
  options,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly { value: string; label: string }[];
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <Select.Root value={value} onValueChange={onChange} disabled={disabled}>
        <Select.Trigger id={id} className="select-trigger">
          <Select.Value />
          <Select.Icon>
            <ChevronDown size={16} aria-hidden />
          </Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Content
            position="popper"
            sideOffset={6}
            className="select-popup"
          >
            <Select.Viewport>
              {options.map((option) => (
                <Select.Item
                  key={option.value}
                  value={option.value}
                  className="select-option"
                >
                  <Select.ItemText>{option.label}</Select.ItemText>
                  <Select.ItemIndicator>
                    <Check size={16} aria-hidden />
                  </Select.ItemIndicator>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </div>
  );
}
export function Modal({
  title,
  description,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  description: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const previousFocus = useRef<HTMLElement | null>(null);
  useLayoutEffect(() => {
    previousFocus.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
  }, []);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content
          className="modal"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (previousFocus.current?.isConnected)
              previousFocus.current.focus();
            else document.querySelector<HTMLElement>("main button")?.focus();
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="text-xl font-semibold">
              {title}
            </Dialog.Title>
            <Dialog.Close
              aria-label="Закрыть"
              className="icon-button"
              disabled={busy}
            >
              <X size={20} aria-hidden />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted mt-2 mb-6">
            {description}
          </Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function ErrorMessage({ error }: { error: unknown }) {
  return error ? (
    <p role="alert" className="error">
      {error instanceof Error ? error.message : "Не удалось выполнить действие"}
    </p>
  ) : null;
}

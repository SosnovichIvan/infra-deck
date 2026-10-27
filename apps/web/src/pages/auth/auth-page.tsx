import { useEffect, useState, type FormEvent } from "react";
import { Layers3, ArrowLeft, ShieldCheck } from "lucide-react";
import { api, type AuthState } from "../../shared/api/client";
import { Button, ErrorMessage, Input } from "../../shared/ui/controls";
export function AuthPage({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [register, setRegister] = useState(false),
    [flow, setFlow] = useState<AuthState | null>(null);
  const [login, setLogin] = useState(""),
    [password, setPassword] = useState(""),
    [confirmation, setConfirmation] = useState("");
  const [code, setCode] = useState(""),
    [recovery, setRecovery] = useState(false),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, []);
  const remaining = Math.max(
    0,
    Math.ceil(((flow?.expires_at ?? 0) * 1000 - now) / 1000),
  );
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function send() {
    setCode("");
    const result = await api<AuthState>("/auth/send-code", "POST");
    setFlow(result);
    setNow(Date.now());
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      if (flow) {
        const result = await api<AuthState>(
          recovery ? "/auth/recover" : "/auth/verify",
          "POST",
          { code },
        );
        setCode("");
        if (result.recovery_codes?.length) setFlow(result);
        else onAuthenticated();
      } else {
        if (register && password !== confirmation)
          throw new Error("Пароли не совпадают");
        const result = await api<AuthState>(
          register ? "/auth/register" : "/auth/login",
          "POST",
          { login, password, ...(register ? { confirmation } : {}) },
        );
        setPassword("");
        setConfirmation("");
        setFlow(result);
        if (result.state === "otp") await send();
      }
    });
  }
  return (
    <main className="auth-shell">
      <section className="panel auth-card">
        <div className="flex items-center gap-3 mb-8">
          <Layers3 className="brand-mark" size={32} aria-hidden />
          <span className="text-xl font-semibold">InfraDeck</span>
        </div>
        {flow?.state === "authenticated" ? (
          <div className="stack">
            <ShieldCheck className="brand-mark" size={36} aria-hidden />
            <h1 className="text-2xl font-semibold">
              Сохраните коды восстановления
            </h1>
            <p className="muted">
              Каждый код можно использовать один раз вместо кода Telegram.
              Сохраните их в менеджере паролей. После закрытия они больше не
              будут показаны.
            </p>
            <pre className="panel p-4 overflow-auto select-all">
              {flow.recovery_codes?.join("\n")}
            </pre>
            <Button onClick={onAuthenticated}>Я сохранил коды</Button>
          </div>
        ) : (
          <>
            <p className="eyebrow mb-3">Единая панель управления</p>
            <h1 className="text-2xl font-semibold mb-3">
              {flow?.state === "enrollment"
                ? "Привяжите Telegram"
                : flow?.state === "otp"
                  ? recovery
                    ? "Восстановление доступа"
                    : "Код из Telegram"
                  : register
                    ? "Создать аккаунт"
                    : "Войти в InfraDeck"}
            </h1>
            <p className="muted mb-7">
              {flow?.state === "enrollment"
                ? "Откройте бота и нажмите «Запустить». После привязки вернитесь за кодом входа."
                : flow?.state === "otp"
                  ? recovery
                    ? "Введите один из сохранённых кодов восстановления."
                    : "Введите одноразовый код. Он действует 30 секунд с момента отправки."
                  : register
                    ? "Создайте аккаунт, затем привяжите Telegram для подтверждения входа."
                    : "Ваши проекты и серверы в одном месте."}
            </p>
            <ErrorMessage error={error} />
            {flow?.state === "enrollment" ? (
              <div className="stack mt-4">
                <a
                  className="button primary"
                  href={flow.telegram_url ?? ""}
                  target="_blank"
                  rel="noreferrer"
                >
                  Открыть Telegram
                </a>
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void run(send)}
                >
                  Telegram привязан — получить код
                </Button>
              </div>
            ) : (
              <form onSubmit={submit} className="stack mt-4">
                {flow?.state === "otp" ? (
                  <>
                    <Input
                      label={
                        recovery ? "Код восстановления" : "Одноразовый код"
                      }
                      className={recovery ? "" : "otp"}
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      required
                      inputMode={recovery ? "text" : "numeric"}
                      autoComplete="one-time-code"
                      pattern={recovery ? undefined : "[0-9]{8}"}
                      minLength={recovery ? 16 : 8}
                      maxLength={recovery ? 64 : 8}
                      disabled={busy || (!recovery && remaining === 0)}
                      autoFocus
                    />
                    {!recovery && (
                      <p className="muted text-sm" role="status">
                        {remaining > 0
                          ? `Код действует ещё ${remaining} с`
                          : "Срок действия кода истёк. Запросите новый код."}
                      </p>
                    )}
                    <Button disabled={busy || (!recovery && remaining === 0)}>
                      {busy ? "Проверяем…" : "Подтвердить вход"}
                    </Button>
                    {!recovery && (
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={busy || remaining > 0}
                        onClick={() => void run(send)}
                      >
                        Отправить новый код
                      </Button>
                    )}
                    <button
                      type="button"
                      className="text-link text-sm"
                      onClick={() => {
                        setRecovery(!recovery);
                        setCode("");
                        setError(null);
                      }}
                    >
                      {recovery
                        ? "Вернуться к коду Telegram"
                        : "Нет доступа к Telegram"}
                    </button>
                  </>
                ) : (
                  <>
                    <Input
                      label="Логин"
                      autoComplete="username"
                      value={login}
                      onChange={(e) => setLogin(e.target.value)}
                      required
                      minLength={3}
                      maxLength={64}
                      pattern="[a-zA-Z0-9_.-]+"
                    />
                    <Input
                      label="Пароль"
                      type="password"
                      autoComplete={
                        register ? "new-password" : "current-password"
                      }
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={12}
                      maxLength={256}
                      hint="Не менее 12 символов"
                    />
                    {register && (
                      <Input
                        label="Подтверждение пароля"
                        type="password"
                        autoComplete="new-password"
                        value={confirmation}
                        onChange={(e) => setConfirmation(e.target.value)}
                        required
                        minLength={12}
                        maxLength={256}
                      />
                    )}
                    <Button disabled={busy}>
                      {busy
                        ? "Подождите…"
                        : register
                          ? "Создать аккаунт"
                          : "Войти"}
                    </Button>
                    <button
                      type="button"
                      className="text-link text-sm"
                      onClick={() => {
                        setRegister(!register);
                        setError(null);
                        setPassword("");
                        setConfirmation("");
                      }}
                    >
                      {register
                        ? "Уже есть аккаунт — войти"
                        : "Создать аккаунт"}
                    </button>
                  </>
                )}
              </form>
            )}
            {flow && (
              <button
                type="button"
                disabled={busy}
                className="flex items-center gap-2 mt-6 muted text-sm"
                onClick={() =>
                  void run(async () => {
                    await api("/auth/logout", "POST");
                    setFlow(null);
                    setCode("");
                    setRecovery(false);
                  })
                }
              >
                <ArrowLeft size={16} aria-hidden />
                Вернуться ко входу
              </button>
            )}
          </>
        )}
      </section>
    </main>
  );
}

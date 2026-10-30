import { useState, useEffect, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  api,
  encryptConnection,
  type Server,
  type Connection,
  type CheckResult,
} from "../../shared/api/client";
import {
  Button,
  Choice,
  ErrorMessage,
  Input,
  Textarea,
  Modal,
} from "../../shared/ui/controls";
const methods = [
  { value: "password", label: "Пароль" },
  { value: "key", label: "SSH-ключ" },
  { value: "certificate", label: "SSH-сертификат" },
];
const kinds = [
  { value: "VPS", label: "VPS" },
  { value: "VM", label: "VM" },
];
export function ServerForm({
  projectId,
  server,
  onClose,
}: {
  projectId: string;
  server?: Server;
  onClose: () => void;
}) {
  const cache = useQueryClient();
  const [name, setName] = useState(server?.name ?? ""),
    [kind, setKind] = useState(server?.kind ?? "VPS");
  const [port, setPort] = useState(String(server?.port ?? 22));
  const [changeConnection, setChangeConnection] = useState(!server);
  const [connection, setConnection] = useState<Connection>({
    host: server?.host ?? "",
    port: server?.port ?? 22,
    username: server?.username ?? "",
    method: server?.method ?? "password",
    password: "",
    private_key: "",
    certificate: "",
    passphrase: "",
    fingerprint: "",
  });
  const [fingerprint, setFingerprint] = useState(""),
    [trusted, setTrusted] = useState(false),
    [proof, setProof] = useState<CheckResult | null>(null);
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!proof) return;
    const timer = setTimeout(
      () => {
        setProof(null);
        setError(
          new Error("Проверка устарела. Проверьте подключение повторно"),
        );
      },
      Math.max(0, proof.expires_at * 1000 - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [proof]);
  function update(field: keyof Connection, value: string | number) {
    setConnection({
      ...connection,
      ...(field === "method"
        ? { password: "", private_key: "", certificate: "", passphrase: "" }
        : {}),
      [field]: value,
    });
    setProof(null);
    setError(null);
    if (field === "host" || field === "port") {
      setFingerprint("");
      setTrusted(false);
    }
  }
  async function test() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setProof(null);
    try {
      if (!fingerprint) {
        const result = await api<{ fingerprint: string }>(
          `/projects/${projectId}/probe`,
          "POST",
          { host: connection.host, port: connection.port },
        );
        setFingerprint(result.fingerprint);
        setTrusted(false);
      } else {
        if (!trusted)
          throw new Error("Подтвердите fingerprint по доверенному каналу");
        const jwe = await encryptConnection({ ...connection, fingerprint });
        setProof(
          await api<CheckResult>(`/projects/${projectId}/checks`, "POST", {
            jwe,
            server_id: server?.id ?? null,
          }),
        );
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const mutation = useMutation({
    mutationFn: async () => {
      if (changeConnection && (!proof || proof.expires_at * 1000 <= Date.now()))
        throw new Error("Проверка устарела. Проверьте подключение повторно");
      return api(
        `/projects/${projectId}/servers${server ? "/" + server.id : ""}`,
        server ? "PUT" : "POST",
        { name, kind, proof: changeConnection ? proof?.proof : null },
      );
    },
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["servers", projectId] });
      onClose();
    },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!mutation.isPending) mutation.mutate();
  }
  return (
    <Modal
      title={server ? "Редактировать сервер" : "Добавить сервер"}
      description="Сначала подтвердите SSH-ключ и проверьте доступ. Реквизиты передаются и хранятся в зашифрованном виде."
      onClose={onClose}
      busy={mutation.isPending}
    >
      <form onSubmit={submit} className="stack">
        <Input
          label="Название сервера"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          maxLength={80}
          autoFocus
        />
        <Choice
          label="Тип сервера"
          value={kind}
          onChange={(value) => setKind(value as "VPS" | "VM")}
          options={kinds}
        />
        {server && (
          <label className="flex gap-3 items-center">
            <input
              type="checkbox"
              checked={changeConnection}
              onChange={(e) => {
                setChangeConnection(e.target.checked);
                setProof(null);
              }}
            />
            Изменить параметры подключения
          </label>
        )}
        {changeConnection && (
          <fieldset disabled={busy} className="stack">
            <legend className="font-semibold mb-4">Подключение по SSH</legend>
            <div className="grid grid-cols-1 sm:grid-cols-[1fr_100px] gap-4">
              <Input
                label="IP-адрес или hostname"
                value={connection.host}
                onChange={(e) => update("host", e.target.value)}
                required
                maxLength={253}
              />
              <Input
                label="Порт"
                type="number"
                value={port}
                onChange={(e) => {
                  setPort(e.target.value);
                  update("port", Number(e.target.value));
                }}
                min={1}
                max={65535}
                required
              />
            </div>
            <Input
              label="Логин SSH"
              value={connection.username}
              onChange={(e) => update("username", e.target.value)}
              autoComplete="off"
              required
              maxLength={64}
            />
            <Choice
              label="Метод входа"
              value={connection.method}
              onChange={(value) => update("method", value)}
              options={methods}
              disabled={busy}
            />
            {connection.method === "password" ? (
              <Input
                label="Пароль SSH"
                type="password"
                value={connection.password}
                onChange={(e) => update("password", e.target.value)}
                autoComplete="off"
                required
                maxLength={4096}
              />
            ) : (
              <>
                <Textarea
                  label="Приватный SSH-ключ"
                  value={connection.private_key}
                  onChange={(e) => update("private_key", e.target.value)}
                  required
                  maxLength={16000}
                />
                {connection.method === "certificate" && (
                  <Textarea
                    label="Публичный SSH-сертификат"
                    value={connection.certificate}
                    onChange={(e) => update("certificate", e.target.value)}
                    required
                    maxLength={16000}
                  />
                )}
                <Input
                  label="Пароль ключа (если задан)"
                  type="password"
                  value={connection.passphrase}
                  onChange={(e) => update("passphrase", e.target.value)}
                  autoComplete="off"
                  maxLength={4096}
                />
              </>
            )}
            {fingerprint && (
              <div className="panel p-4 stack">
                <p className="text-sm font-semibold">SSH fingerprint</p>
                <p className="fingerprint">{fingerprint}</p>
                {server && server.fingerprint !== fingerprint && (
                  <p className="error">
                    SSH-ключ отличается от сохранённого. Уточните причину
                    изменения у администратора.
                  </p>
                )}
                <label className="flex gap-3 items-start text-sm">
                  <input
                    type="checkbox"
                    checked={trusted}
                    onChange={(e) => {
                      setTrusted(e.target.checked);
                      if (!e.target.checked) setProof(null);
                    }}
                  />
                  Я сверил fingerprint с консолью сервера или администратором
                </label>
              </div>
            )}
            <Button
              type="button"
              variant="secondary"
              disabled={busy || (!trusted && !!fingerprint)}
              onClick={() => void test()}
            >
              {busy
                ? "Проверяем подключение…"
                : fingerprint
                  ? "Проверить доступ по SSH"
                  : "Получить SSH fingerprint"}
            </Button>
            {proof && (
              <p role="status" className="success">
                Доступ по SSH подтверждён. Теперь можно сохранить сервер.
              </p>
            )}
          </fieldset>
        )}
        <ErrorMessage error={error ?? mutation.error} />
        <div className="actions">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Отмена
          </Button>
          <Button
            disabled={
              busy || mutation.isPending || (changeConnection && !proof)
            }
          >
            {mutation.isPending
              ? "Сохраняем…"
              : server
                ? "Сохранить изменения"
                : "Добавить сервер"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

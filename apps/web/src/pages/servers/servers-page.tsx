import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Server as ServerIcon,
  Pencil,
  Trash2,
  RefreshCw,
  ArrowLeft,
} from "lucide-react";
import { api, type Project, type Server } from "../../shared/api/client";
import { Button, ErrorMessage, Modal } from "../../shared/ui/controls";
import { ServerForm } from "./server-form";
export function ServersPage() {
  const { projectId = "" } = useParams();
  const cache = useQueryClient();
  const [editing, setEditing] = useState<Server | null | undefined>(undefined),
    [deleting, setDeleting] = useState<Server | null>(null),
    [offset, setOffset] = useState(0);
  const project = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => api<Project>("/projects/" + projectId),
  });
  const query = useQuery({
    queryKey: ["servers", projectId, offset],
    queryFn: () =>
      api<Server[]>(`/projects/${projectId}/servers?offset=${offset}`),
  });
  const deletion = useMutation({
    mutationFn: (id: string) =>
      api(`/projects/${projectId}/servers/${id}`, "DELETE"),
    onSuccess: async () => {
      setDeleting(null);
      await cache.invalidateQueries({ queryKey: ["servers", projectId] });
    },
  });
  const recheck = useMutation({
    mutationFn: (id: string) =>
      api<Server>(`/projects/${projectId}/servers/${id}/recheck`, "POST"),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["servers", projectId] });
    },
  });
  return (
    <>
      <Link to="/" className="flex items-center gap-2 muted text-sm mb-8">
        <ArrowLeft size={16} aria-hidden />
        Все проекты
      </Link>
      <header className="flex flex-wrap justify-between items-end gap-5 mb-9">
        <div>
          <p className="eyebrow mb-2">Проект · {project.data?.name ?? "…"}</p>
          <h1 className="text-3xl font-semibold">Серверы</h1>
          <p className="muted mt-3">
            Серверы VPS и виртуальные машины вашего проекта.
          </p>
        </div>
        <Button onClick={() => setEditing(null)} disabled={!project.data}>
          <Plus size={18} aria-hidden />
          Добавить сервер
        </Button>
      </header>
      <ErrorMessage error={project.error ?? recheck.error} />
      {recheck.isSuccess && (
        <p role="status" className="success mb-5">
          Подключение к серверу проверено.
        </p>
      )}
      {query.isPending ? (
        <p role="status">Загружаем серверы…</p>
      ) : query.isError ? (
        <>
          <ErrorMessage error={query.error} />
          <Button variant="secondary" onClick={() => void query.refetch()}>
            Повторить
          </Button>
        </>
      ) : query.data.length === 0 ? (
        <div className="panel p-10 text-center">
          <ServerIcon
            className="brand-mark mx-auto mb-4"
            size={36}
            aria-hidden
          />
          <h2 className="text-xl font-semibold">
            {offset ? "Больше серверов нет" : "Добавьте первый сервер"}
          </h2>
          <p className="muted mt-3">
            Перед добавлением InfraDeck проверит доступ по SSH.
          </p>
        </div>
      ) : (
        <div className="stack">
          {query.data.map((server) => (
            <article key={server.id} className="panel server-row">
              <div className="min-w-0">
                <div className="flex gap-3 items-center">
                  <ServerIcon
                    size={20}
                    className="brand-mark shrink-0"
                    aria-hidden
                  />
                  <h2 className="text-lg font-semibold">{server.name}</h2>
                  <span className="muted text-xs">{server.kind}</span>
                </div>
                <p className="muted text-sm mt-2 break-all">
                  {server.username}@{server.host}:{server.port}
                </p>
                <p className="muted text-xs mt-2">
                  Доступ проверен:{" "}
                  {new Date(server.checked_at * 1000).toLocaleString("ru-RU")}
                </p>
              </div>
              <div className="flex gap-2 flex-wrap">
                <Button
                  variant="secondary"
                  disabled={recheck.isPending}
                  onClick={() => recheck.mutate(server.id)}
                >
                  <RefreshCw size={16} aria-hidden />
                  {recheck.isPending && recheck.variables === server.id
                    ? "Проверяем…"
                    : "Проверить связь"}
                </Button>
                <button
                  className="icon-button"
                  aria-label={"Редактировать сервер " + server.name}
                  onClick={() => setEditing(server)}
                >
                  <Pencil size={16} aria-hidden />
                </button>
                <button
                  className="icon-button"
                  aria-label={"Удалить сервер " + server.name}
                  onClick={() => {
                    deletion.reset();
                    setDeleting(server);
                  }}
                >
                  <Trash2 size={16} aria-hidden />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {(offset > 0 || query.data?.length === 100) && (
        <div className="actions">
          <Button
            variant="secondary"
            disabled={offset === 0}
            onClick={() => setOffset(offset - 100)}
          >
            Назад
          </Button>
          <Button
            variant="secondary"
            disabled={query.data?.length !== 100}
            onClick={() => setOffset(offset + 100)}
          >
            Далее
          </Button>
        </div>
      )}
      {editing !== undefined && (
        <ServerForm
          projectId={projectId}
          server={editing ?? undefined}
          onClose={() => setEditing(undefined)}
        />
      )}
      {deleting && (
        <Modal
          busy={deletion.isPending}
          title={"Удалить сервер «" + deleting.name + "»?"}
          description="Будут удалены запись сервера и сохранённые реквизиты. Сам VPS или VM продолжит работать."
          onClose={() => setDeleting(null)}
        >
          <ErrorMessage error={deletion.error} />
          <div className="actions">
            <Button
              variant="secondary"
              onClick={() => setDeleting(null)}
              disabled={deletion.isPending}
            >
              Отмена
            </Button>
            <Button
              variant="danger"
              disabled={deletion.isPending}
              onClick={() => deletion.mutate(deleting.id)}
            >
              Удалить сервер
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

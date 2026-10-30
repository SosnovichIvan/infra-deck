import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Folder, Plus, Pencil, Trash2, ArrowUpRight } from "lucide-react";
import { api, type Project } from "../../shared/api/client";
import { Button, ErrorMessage, Modal } from "../../shared/ui/controls";
import { ProjectForm } from "./project-form";
export function ProjectsPage() {
  const cache = useQueryClient();
  const [editing, setEditing] = useState<Project | null | undefined>(undefined),
    [deleting, setDeleting] = useState<Project | null>(null),
    [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["projects", offset],
    queryFn: () => api<Project[]>("/projects?offset=" + offset),
  });
  const deletion = useMutation({
    mutationFn: (id: string) => api("/projects/" + id, "DELETE"),
    onSuccess: async () => {
      setDeleting(null);
      await cache.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-5 mb-9">
        <div>
          <p className="eyebrow mb-2">Рабочее пространство</p>
          <h1 className="text-3xl font-semibold">Проекты</h1>
          <p className="muted mt-3">
            Выберите проект, чтобы управлять его серверами.
          </p>
        </div>
        <Button onClick={() => setEditing(null)}>
          <Plus size={18} aria-hidden />
          Создать проект
        </Button>
      </header>
      {query.isPending ? (
        <p role="status">Загружаем проекты…</p>
      ) : query.isError ? (
        <>
          <ErrorMessage error={query.error} />
          <Button variant="secondary" onClick={() => void query.refetch()}>
            Повторить
          </Button>
        </>
      ) : query.data.length === 0 ? (
        <div className="panel p-10 text-center">
          <Folder className="brand-mark mx-auto mb-4" size={36} aria-hidden />
          <h2 className="text-xl font-semibold">
            {offset ? "Больше проектов нет" : "Создайте первый проект"}
          </h2>
          <p className="muted mt-3">
            В проекте будут храниться серверы и параметры подключения.
          </p>
        </div>
      ) : (
        <div className="project-grid">
          {query.data.map((project) => (
            <article key={project.id} className="panel project-card">
              <Folder className="brand-mark mb-5" size={24} aria-hidden />
              <Link
                to={"/projects/" + project.id}
                className="flex justify-between gap-3 font-semibold text-xl"
              >
                <span>{project.name}</span>
                <ArrowUpRight size={20} aria-hidden />
              </Link>
              <p className="muted text-sm mt-3 mb-6 grow">
                {project.description || "Описание не добавлено"}
              </p>
              <div className="flex gap-2 justify-end">
                <button
                  className="icon-button"
                  aria-label={"Редактировать проект " + project.name}
                  onClick={() => setEditing(project)}
                >
                  <Pencil size={16} aria-hidden />
                </button>
                <button
                  className="icon-button"
                  aria-label={"Удалить проект " + project.name}
                  onClick={() => {
                    deletion.reset();
                    setDeleting(project);
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
        <ProjectForm
          project={editing ?? undefined}
          onClose={() => setEditing(undefined)}
        />
      )}
      {deleting && (
        <Modal
          busy={deletion.isPending}
          title={"Удалить проект «" + deleting.name + "»?"}
          description="Будут удалены проект, записи его серверов и сохранённые реквизиты. Сами VPS и VM продолжат работать. Это действие нельзя отменить."
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
              Удалить проект
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

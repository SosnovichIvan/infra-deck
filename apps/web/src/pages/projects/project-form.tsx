import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Project } from "../../shared/api/client";
import {
  Button,
  Input,
  Textarea,
  ErrorMessage,
  Modal,
} from "../../shared/ui/controls";
export function ProjectForm({
  project,
  onClose,
}: {
  project?: Project;
  onClose: () => void;
}) {
  const [name, setName] = useState(project?.name ?? ""),
    [description, setDescription] = useState(project?.description ?? "");
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      api(
        "/projects" + (project ? "/" + project.id : ""),
        project ? "PUT" : "POST",
        { name, description },
      ),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["projects"] });
      onClose();
    },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!mutation.isPending) mutation.mutate();
  }
  return (
    <Modal
      title={project ? "Редактировать проект" : "Создать проект"}
      description="Объедините серверы одного проекта."
      onClose={onClose}
      busy={mutation.isPending}
    >
      <form onSubmit={submit} className="stack">
        <Input
          label="Название проекта"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          maxLength={80}
          autoFocus
        />
        <Textarea
          label="Описание"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
        />
        <ErrorMessage error={mutation.error} />
        <div className="actions">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Отмена
          </Button>
          <Button disabled={mutation.isPending}>
            {mutation.isPending
              ? "Сохраняем…"
              : project
                ? "Сохранить изменения"
                : "Создать проект"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

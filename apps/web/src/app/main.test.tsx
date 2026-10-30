import { vi, it, expect } from "vitest";
it("mounts the application entrypoint", async () => {
  const render = vi.fn();
  vi.doMock("react-dom/client", () => ({
    createRoot: vi.fn(() => ({ render })),
  }));
  const root = document.createElement("div");
  root.id = "root";
  document.body.append(root);
  await import("./main");
  expect(render).toHaveBeenCalled();
  root.remove();
  vi.doUnmock("react-dom/client");
});

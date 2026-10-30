import { useState, useEffect } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Layers3, LogOut, Sun, Moon } from "lucide-react";
import { api, ApiError } from "../shared/api/client";
import { Button, ErrorMessage } from "../shared/ui/controls";
import { AuthPage } from "../pages/auth";
import { ProjectsPage } from "../pages/projects";
import { ServersPage } from "../pages/servers";
export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: 10000 } },
});
export function Application() {
  const cache = useQueryClient();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api("/auth/me"),
    retry: false,
  });
  const [theme, setTheme] = useState(
      () => localStorage.getItem("theme") ?? "dark",
    ),
    [logoutError, setLogoutError] = useState<unknown>(null),
    [loggingOut, setLoggingOut] = useState(false);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  if (me.isPending)
    return (
      <main className="auth-shell">
        <p role="status">Загружаем InfraDeck…</p>
      </main>
    );
  if (me.error && !(me.error instanceof ApiError && me.error.status === 401))
    return (
      <main className="auth-shell">
        <section className="stack">
          <ErrorMessage error={me.error} />
          <Button onClick={() => void me.refetch()}>Повторить</Button>
        </section>
      </main>
    );
  if (!me.data || (me.error instanceof ApiError && me.error.status === 401))
    return (
      <AuthPage
        onAuthenticated={() => {
          cache.removeQueries({
            predicate: (query) => query.queryKey[0] !== "me",
          });
          void cache.invalidateQueries({ queryKey: ["me"] });
        }}
      />
    );
  return (
    <BrowserRouter>
      <aside className="rail">
        <Link to="/" aria-label="InfraDeck — проекты" className="brand-mark">
          <Layers3 size={32} aria-hidden />
        </Link>
        <div className="mt-auto flex flex-col gap-3">
          <button
            className="icon-button"
            aria-label={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
            onClick={() => {
              const next = theme === "dark" ? "light" : "dark";
              setTheme(next);
              localStorage.setItem("theme", next);
            }}
          >
            {theme === "dark" ? (
              <Sun size={20} aria-hidden />
            ) : (
              <Moon size={20} aria-hidden />
            )}
          </button>
          <button
            className="icon-button"
            aria-label="Выйти"
            disabled={loggingOut}
            onClick={async () => {
              setLoggingOut(true);
              setLogoutError(null);
              try {
                await api("/auth/logout", "POST");
                cache.removeQueries({
                  predicate: (query) => query.queryKey[0] !== "me",
                });
                cache.setQueryData(["me"], null);
                window.history.replaceState(null, "", "/");
              } catch (e) {
                setLogoutError(e);
              } finally {
                setLoggingOut(false);
              }
            }}
          >
            <LogOut size={20} aria-hidden />
          </button>
        </div>
      </aside>
      <main className="workspace">
        <ErrorMessage error={logoutError} />
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route
            path="/projects/:projectId"
            element={<ServersPage key={window.location.pathname} />}
          />
          <Route
            path="*"
            element={
              <>
                <h1>Страница не найдена</h1>
                <Link to="/">Вернуться к проектам</Link>
              </>
            }
          />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Application />
    </QueryClientProvider>
  );
}

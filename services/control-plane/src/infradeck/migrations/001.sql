CREATE TABLE users (
 id uuid PRIMARY KEY, login text UNIQUE NOT NULL, password_hash text NOT NULL,
 telegram_id bigint UNIQUE, created_at double precision NOT NULL
);
CREATE TABLE sessions (
 token text PRIMARY KEY, user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
 kind text NOT NULL CHECK (kind IN ('enrollment','preauth','full')),
 csrf text NOT NULL, expires_at double precision NOT NULL,
 enrollment_token text UNIQUE, enrollment_expires double precision,
 otp_digest text, otp_expires double precision, attempts integer NOT NULL DEFAULT 0,
 last_sent double precision NOT NULL DEFAULT 0
);
CREATE INDEX sessions_user ON sessions(user_id);
CREATE TABLE recovery_codes (
 user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE, digest text NOT NULL,
 PRIMARY KEY (user_id, digest)
);
CREATE TABLE telegram_updates (id bigint PRIMARY KEY, received_at double precision NOT NULL);
CREATE TABLE rate_limits (
 scope text PRIMARY KEY, window_start double precision NOT NULL, hits integer NOT NULL
);
CREATE TABLE projects (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
 name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 80),
 description text NOT NULL DEFAULT '', UNIQUE(id, owner_id)
);
CREATE INDEX projects_owner ON projects(owner_id,id);
CREATE TABLE servers (
 id uuid PRIMARY KEY, project_id uuid NOT NULL, owner_id uuid NOT NULL,
 name text NOT NULL, kind text NOT NULL CHECK (kind IN ('VPS','VM')),
 host text NOT NULL, port integer NOT NULL CHECK (port BETWEEN 1 AND 65535),
 username text NOT NULL, method text NOT NULL CHECK (method IN ('password','key','certificate')),
 fingerprint text NOT NULL, checked_at double precision NOT NULL,
 encrypted jsonb NOT NULL, aad text NOT NULL,
 FOREIGN KEY (project_id,owner_id) REFERENCES projects(id,owner_id) ON DELETE CASCADE
);
CREATE INDEX servers_project_owner ON servers(project_id,owner_id,id);
CREATE TABLE connection_checks (
 proof text PRIMARY KEY, owner_id uuid NOT NULL, project_id uuid NOT NULL,
 server_id uuid REFERENCES servers ON DELETE CASCADE,
 encrypted jsonb NOT NULL, aad text NOT NULL, expires_at double precision NOT NULL,
 FOREIGN KEY(project_id,owner_id) REFERENCES projects(id,owner_id) ON DELETE CASCADE
);
CREATE TABLE encryption_nonces (
 nonce text PRIMARY KEY, session_token text NOT NULL REFERENCES sessions ON DELETE CASCADE,
 expires_at double precision NOT NULL
);

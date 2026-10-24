"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { WorkspaceForm } from "./Auth";
import Chat from "./Chat";
import { migrateStorage } from "../lib/storage.mjs";
export default function Workspace() {
  const [session, setSession] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    try {
      migrateStorage(localStorage);
      migrateStorage(sessionStorage);
    } catch {
      /* Browser storage may be disabled. */
    }
    api("/api/session/")
      .then((data) => {
        if (!data.user) {
          location.replace("/accounts/login/");
          return;
        }
        setSession(data);
      })
      .catch((error) => setError(error.message));
  }, []);
  if (error)
    return (
      <main className="auth-simple">
        <p role="alert">{error}</p>
        <button onClick={() => location.reload()}>تلاش دوباره</button>
      </main>
    );
  if (!session)
    return (
      <main className="auth-simple" role="status">
        در حال بارگذاری…
      </main>
    );
  if (!session.workspaces.length)
    return (
      <main className="auth-simple">
        <section className="auth-card">
          <a className="brand" href="/">
            <img className="app-logo" src="/static/chat/logo.svg" width={28} height={28} alt="" /> اسنک
          </a>
          <h1>فضای کاری تیم شما کجاست؟</h1>
          <WorkspaceForm
            onCreated={(workspace) =>
              location.assign(`/?workspace=${workspace.id}`)
            }
          />
          <button
            className="text-link"
            onClick={async () => {
              await api("/api/auth/logout/", { method: "POST" });
              location.assign("/accounts/login/");
            }}
          >
            خروج از حساب
          </button>
        </section>
      </main>
    );
  const requested = new URLSearchParams(location.search).get("workspace");
  const workspace =
    session.workspaces.find((item) => String(item.id) === requested) ||
    session.workspaces[0];
  return (
    <Chat
      key={workspace.id}
      workspace={workspace}
      workspaces={session.workspaces}
      user={session.user}
    />
  );
}

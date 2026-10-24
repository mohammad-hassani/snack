"use client";
import { useEffect, useState } from "react";
import { Asterisk } from "lucide-react";
import { api } from "../lib/api";
export default function Invitation({ token }) {
  const [invite, setInvite] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api(`/api/invites/${token}/`)
      .then(setInvite)
      .catch((error) => setError(error.message));
  }, [token]);
  return (
    <main className="auth-simple">
      <section className="auth-card">
        <a href="/" className="brand">
          <Asterisk size={28} aria-hidden="true" /> اسنک
        </a>
        <h1>دعوت به {invite?.workspace || "فضای کاری"}</h1>
        {error && <p role="alert">{error}</p>}
        {invite && (
          <button
            className="primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                const result = await api(`/api/invites/${token}/`, {
                  method: "POST",
                });
                location.assign(`/?workspace=${result.workspace_id}`);
              } catch (error) {
                setError(error.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            پذیرش دعوت‌نامه
          </button>
        )}
        <p>
          <a
            href={`/accounts/login/?next=${encodeURIComponent(`/invite/${token}/`)}`}
          >
            ورود با حساب دیگر
          </a>
        </p>
      </section>
    </main>
  );
}

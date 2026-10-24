"use client";
import { useEffect, useState } from "react";
import { Asterisk, ArrowLeft } from "lucide-react";
import { api } from "../lib/api";

export function WorkspaceForm({ onCreated }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError("");
        try {
          const result = await api("/api/workspaces/", {
            method: "POST",
            body: Object.fromEntries(new FormData(event.currentTarget)),
          });
          onCreated(result);
        } catch (error) {
          setError(error.message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <label htmlFor="workspace-name">نام فضای کاری</label>
      <input
        id="workspace-name"
        name="name"
        dir="auto"
        maxLength={80}
        required
        placeholder="مثلاً استودیوی آفرین"
      />
      {error && (
        <p role="alert" className="errorlist">
          {error}
        </p>
      )}
      <button disabled={busy} className="primary full">
        ساخت فضای کاری <ArrowLeft size={18} aria-hidden="true" />
      </button>
    </form>
  );
}
export default function Auth({ path = [] }) {
  const mode = path[0] || "login";
  const signup = mode === "signup";
  const reset = mode === "password_reset";
  const confirm = mode === "reset";
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [nextQuery, setNextQuery] = useState("");
  useEffect(() => {
    setNextQuery(location.search);
    api("/api/session/").catch((error) => setError(error.message));
  }, []);
  const title = signup
    ? "حساب اسنک بسازید"
    : reset
      ? "بازنشانی گذرواژه"
      : confirm
        ? "گذرواژهٔ تازه"
        : "خوش برگشتید";
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = Object.fromEntries(new FormData(event.currentTarget));
    const endpoint = signup
      ? "signup/"
      : reset
        ? "password-reset/"
        : confirm
          ? `reset/${path[1]}/${path[2]}/`
          : "login/";
    try {
      await api(`/api/auth/${endpoint}`, { method: "POST", body });
      if (reset || confirm) {
        setDone(true);
        return;
      }
      const next = new URLSearchParams(location.search).get("next");
      const target = new URL(next || "/", location.origin);
      location.assign(target.origin === location.origin ? target.href : "/");
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-layout">
      <section className="auth-story">
        <a className="brand" href="/">
          <Asterisk size={28} aria-hidden="true" /> اسنک
        </a>
        <div>
          <span className="eyebrow">کار خوب با یک گفتگو شروع می‌شود</span>
          <h1>
            کمی نزدیک‌تر،
            <br />
            هماهنگ‌تر با هم.
          </h1>
          <p>
            یک جا برای همهٔ گفتگوهای تیم شما.
            <br />
            حاشیه کمتر، پیشرفت بیشتر.
          </p>
          <div className="story-chat">
            <span className="avatar peach">م</span>
            <div>
              <b>مینا</b>
              <p>صبح بخیر تیم! امروز روی چه چیزی کار می‌کنیم؟</p>
            </div>
          </div>
        </div>
        <small>فضایی برای بهترین کارهای شما</small>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <a className="brand" href="/">
            <Asterisk size={28} aria-hidden="true" /> اسنک
          </a>
          <h1>{title}</h1>
          {done ? (
            <p role="status">
              {reset
                ? "اگر حسابی با این ایمیل وجود داشته باشد، پیوند بازنشانی ارسال می‌شود."
                : "گذرواژه تغییر کرد."}{" "}
              <a href="/accounts/login/">ورود به حساب</a>
            </p>
          ) : (
            <form onSubmit={submit}>
              {signup && (
                <>
                  <label htmlFor="id_first_name">نام شما</label>
                  <input
                    id="id_first_name"
                    name="first_name"
                    dir="auto"
                    maxLength={80}
                    autoComplete="given-name"
                    required
                  />
                </>
              )}
              {!confirm && (
                <>
                  <label htmlFor="id_username">
                    {signup || reset ? "ایمیل" : "نام کاربری یا ایمیل"}
                  </label>
                  <input
                    id="id_username"
                    name={signup || reset ? "email" : "username"}
                    type={signup || reset ? "email" : "text"}
                    dir="ltr"
                    maxLength={150}
                    autoComplete="username"
                    required
                  />
                </>
              )}
              {!reset && (
                <>
                  <label htmlFor="id_password">گذرواژه</label>
                  <input
                    id="id_password"
                    name={
                      confirm
                        ? "new_password1"
                        : signup
                          ? "password1"
                          : "password"
                    }
                    type="password"
                    autoComplete={
                      signup || confirm ? "new-password" : "current-password"
                    }
                    required
                  />
                </>
              )}
              {(signup || confirm) && (
                <>
                  <label htmlFor="id_password2">تکرار گذرواژه</label>
                  <input
                    id="id_password2"
                    name={confirm ? "new_password2" : "password2"}
                    type="password"
                    autoComplete="new-password"
                    required
                  />
                  <p className="muted">
                    دست‌کم ۸ نویسه، متفاوت با اطلاعات شخصی و گذرواژه‌های رایج.
                  </p>
                </>
              )}
              {error && (
                <p className="errorlist" role="alert">
                  {error}
                </p>
              )}
              <button className="primary full" disabled={busy}>
                {busy
                  ? "در حال انجام…"
                  : signup
                    ? "ساخت حساب"
                    : reset
                      ? "ارسال پیوند بازنشانی"
                      : confirm
                        ? "ذخیرهٔ گذرواژه"
                        : "ورود به اسنک"}
              </button>
            </form>
          )}
          <p>
            <a
              href={`${signup ? "/accounts/login/" : "/accounts/signup/"}${nextQuery}`}
            >
              {signup ? "حساب دارید؟ وارد شوید" : "ساخت حساب تازه"}
            </a>
          </p>
          <a href="/accounts/password_reset/">گذرواژه را فراموش کرده‌اید؟</a>
        </div>
      </section>
    </main>
  );
}

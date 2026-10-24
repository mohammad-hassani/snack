"use client";
import { Fragment, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUp,
  ArrowUpRight,
  Asterisk,
  Bold,
  Code,
  CornerDownLeft,
  Download,
  Hash,
  House,
  Inbox,
  Italic,
  LayoutGrid,
  LockKeyhole,
  Menu,
  MessageCircle,
  Paperclip,
  Pencil,
  Plus,
  Reply,
  Search,
  Smile,
  Sparkles,
  Trash2,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { WorkspaceForm } from "./Auth";

const number = new Intl.NumberFormat("fa-IR");
const colors = ["lavender", "mint", "peach", "blue", "rose"];
function Avatar({ name, id, small = false }) {
  return (
    <span
      className={`avatar ${colors[id % colors.length]}${small ? " small-avatar" : ""}`}
    >
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}
function Form({ children, action, label }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        setBusy(true);
        setError("");
        try {
          await action(data);
        } catch (error) {
          setError(error.message);
        } finally {
          setBusy(false);
        }
      }}
    >
      {children}
      {error && (
        <p className="modal-error" role="alert">
          {error}
        </p>
      )}
      <button className="primary" type="submit" disabled={busy}>
        {label}
      </button>
    </form>
  );
}
function Field({ name, label, ...props }) {
  return (
    <>
      <label htmlFor={`field-${name}`}>{label}</label>
      <input id={`field-${name}`} name={name} dir="auto" required {...props} />
    </>
  );
}
function Dialog({ title, children, close }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog ref={ref} id="modal" aria-labelledby="modal-title" onCancel={close}>
      <div className="modal-head">
        <h2 id="modal-title">{title}</h2>
        <button
          id="close-modal"
          className="icon-button"
          aria-label="بستن پنجره"
          onClick={close}
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>
      <div id="modal-body">{children}</div>
    </dialog>
  );
}

export default function Chat({ workspace, workspaces, user }) {
  const [data, setData] = useState({ me: user, channels: [], members: [] });
  const [current, setCurrent] = useState(null),
    [messages, setMessages] = useState([]),
    [hasMore, setHasMore] = useState(false);
  const [body, setBody] = useState(""),
    [reply, setReply] = useState(null),
    [file, setFile] = useState(null);
  const [sending, setSending] = useState(false),
    [loading, setLoading] = useState(false),
    [olderLoading, setOlderLoading] = useState(false);
  const [connection, setConnection] = useState("در حال اتصال"),
    [typing, setTyping] = useState("");
  const [notice, setNotice] = useState(""),
    [modal, setModal] = useState(null),
    [sidebar, setSidebar] = useState(false),
    [results, setResults] = useState(null);
  const [query, setQuery] = useState(""),
    [kind, setKind] = useState("public");
  const socket = useRef(null),
    active = useRef(null),
    rows = useRef([]),
    generation = useRef(0),
    recovering = useRef(false);
  const scroll = useRef(null),
    input = useRef(null),
    upload = useRef(null),
    handlers = useRef({});
  const lastTyping = useRef(0),
    typingTimer = useRef(null),
    refreshTimer = useRef(null),
    pending = useRef(false);
  const draftKey = (id) => `snack:${user.id}:${workspace.id}:${id}`;
  const toast = (error) =>
    setNotice(typeof error === "string" ? error : error.message);
  useEffect(() => {
    if (notice) {
      const timer = setTimeout(() => setNotice(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [notice]);
  const bottom = () =>
    requestAnimationFrame(() => {
      if (scroll.current)
        scroll.current.scrollTop = scroll.current.scrollHeight;
    });
  function merge(items, replace = false) {
    const all = new Map(
      (replace ? [] : rows.current).map((message) => [message.id, message]),
    );
    items.forEach((message) => all.set(message.id, message));
    rows.current = [...all.values()].sort((a, b) => a.id - b.id);
    setMessages(rows.current);
  }
  function readDraft(id) {
    try {
      return JSON.parse(sessionStorage.getItem(draftKey(id)) || "{}");
    } catch {
      return {};
    }
  }
  function changeBody(value) {
    setBody(value);
    if (active.current) {
      const old = readDraft(active.current.id);
      try {
        sessionStorage.setItem(
          draftKey(active.current.id),
          JSON.stringify({
            body: value,
            clientId: old.clientId || crypto.randomUUID(),
          }),
        );
      } catch {
        /* Browser storage may be disabled. */
      }
      if (Date.now() - lastTyping.current > 2000) {
        lastTyping.current = Date.now();
        socketSend({ event: "start:typing", channel_id: active.current.id });
      }
    }
  }
  function socketSend(event) {
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify(event));
  }
  async function refresh() {
    const next = await api(`/api/workspaces/${workspace.id}/`);
    setData(next);
    return next;
  }
  function scheduleRefresh() {
    clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => refresh().catch(toast), 200);
  }
  async function markRead() {
    if (document.hidden || !active.current || !rows.current.length) return;
    const id = active.current.id,
      last = rows.current.at(-1).id;
    await api(`/api/channels/${id}/read/`, {
      method: "POST",
      body: { message_id: last },
    });
    setData((previous) => ({
      ...previous,
      channels: previous.channels.map((channel) =>
        channel.id === id ? { ...channel, unread: 0 } : channel,
      ),
    }));
  }
  async function openChannel(channel) {
    if (pending.current) {
      toast("منتظر بمانید تا ارسال پیام تمام شود.");
      return;
    }
    socketSend({ event: "stop:typing", channel_id: active.current?.id });
    const request = ++generation.current;
    active.current = channel;
    setCurrent(channel);
    merge([], true);
    setHasMore(false);
    setLoading(true);
    setBody(readDraft(channel.id).body || "");
    setReply(null);
    setFile(null);
    setTyping("");
    setSidebar(false);
    setResults(null);
    if (upload.current) upload.current.value = "";
    try {
      localStorage.setItem(`snack-channel:${workspace.id}`, channel.id);
    } catch {
      /* Optional preference. */
    }
    try {
      const page = await api(`/api/channels/${channel.id}/messages/`);
      if (request !== generation.current) return;
      // Preserve events delivered while the history request was in flight.
      const incoming = rows.current;
      merge(page.messages, true);
      merge(incoming);
      setHasMore(page.has_more);
      bottom();
      await markRead();
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }
  async function recover() {
    if (recovering.current) return;
    recovering.current = true;
    const request = generation.current;
    try {
      const next = await refresh();
      if (request !== generation.current || !active.current) return;
      const id = active.current.id;
      if (!next.channels.some((channel) => channel.id === id)) {
        ++generation.current;
        active.current = null;
        setCurrent(null);
        merge([], true);
        setHasMore(false);
        toast("این گفتگو دیگر در دسترس نیست.");
        return;
      }
      let after = rows.current.at(-1)?.id;
      if (after) {
        let more = true;
        while (more && request === generation.current) {
          const page = await api(
            `/api/channels/${id}/messages/?after=${after}`,
          );
          if (request !== generation.current) return;
          merge(page.messages);
          after = page.messages.at(-1)?.id || after;
          more = page.has_more;
        }
      }
      const page = await api(`/api/channels/${id}/messages/`);
      if (request !== generation.current) return;
      merge(page.messages);
      setHasMore(page.has_more && rows.current.length <= 50);
      bottom();
      await markRead();
    } finally {
      recovering.current = false;
    }
  }
  function receive(event) {
    if (event.event === "ready") {
      recover().catch(toast);
      return;
    }
    if (event.event === "error") {
      toast(event.error);
      return;
    }
    if (event.event === "update:presence") scheduleRefresh();
    if (event.channel_id === active.current?.id && event.user_id !== user.id) {
      if (event.event === "start:typing") {
        setTyping(`${event.name} در حال نوشتن است…`);
        clearTimeout(typingTimer.current);
        typingTimer.current = setTimeout(() => setTyping(""), 3500);
      }
      if (event.event === "stop:typing") setTyping("");
    }
    if (event.message) {
      if (event.message.channel_id === active.current?.id) {
        const nearBottom =
          !scroll.current ||
          scroll.current.scrollHeight -
            scroll.current.scrollTop -
            scroll.current.clientHeight <
            140;
        merge([event.message]);
        if (nearBottom || event.message.sender_id === user.id) {
          bottom();
          markRead().catch(toast);
        }
      }
      if (event.event === "new:message") scheduleRefresh();
    }
  }
  handlers.current = { receive, recover, refresh };
  useEffect(() => {
    let stopped = false,
      reconnectTimer,
      retry = 1000;
    async function initialize() {
      try {
        const next = await refresh();
        if (stopped) return;
        let stored;
        try {
          stored = Number(
            localStorage.getItem(`snack-channel:${workspace.id}`),
          );
        } catch {
          /* Optional preference. */
        }
        const first =
          next.channels.find((channel) => channel.id === stored) ||
          next.channels.find((channel) => channel.name === "general") ||
          next.channels[0];
        if (first) await openChannel(first);
        if (!stopped) connect();
      } catch (error) {
        if (!stopped) toast(error);
      }
    }
    function connect() {
      if (stopped) return;
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/workspaces/${workspace.id}/`,
      );
      socket.current = ws;
      ws.onopen = () => {
        if (stopped) {
          ws.close();
          return;
        }
        retry = 1000;
        setConnection("متصل");
      };
      ws.onmessage = ({ data }) => {
        try {
          handlers.current.receive(JSON.parse(data));
        } catch (error) {
          toast(error);
        }
      };
      ws.onerror = () => ws.close();
      ws.onclose = ({ code }) => {
        if (stopped) return;
        setConnection("اتصال مجدد");
        if (code === 4401) {
          location.assign("/accounts/login/");
          return;
        }
        if (code === 4403) {
          toast("دیگر به این فضای کاری دسترسی ندارید.");
          return;
        }
        reconnectTimer = setTimeout(connect, retry);
        retry = Math.min(retry * 2, 15000);
      };
    }
    const visible = () => {
      if (!document.hidden) handlers.current.recover().catch(toast);
    };
    const online = () => {
      if (socket.current?.readyState === WebSocket.CLOSED) {
        clearTimeout(reconnectTimer);
        connect();
      }
    };
    document.addEventListener("visibilitychange", visible);
    window.addEventListener("online", online);
    const heartbeat = setInterval(() => {
      socketSend({ event: "ping" });
      handlers.current.refresh().catch(() => {});
    }, 20000);
    initialize();
    return () => {
      stopped = true;
      ++generation.current;
      clearTimeout(reconnectTimer);
      clearTimeout(typingTimer.current);
      clearTimeout(refreshTimer.current);
      clearInterval(heartbeat);
      socket.current?.close();
      document.removeEventListener("visibilitychange", visible);
      window.removeEventListener("online", online);
    };
  }, [workspace.id]);
  async function send(event) {
    event.preventDefault();
    if (!active.current || pending.current || (!body.trim() && !file)) return;
    const id = active.current.id;
    const draft = readDraft(id),
      clientId = draft.clientId || crypto.randomUUID();
    try {
      sessionStorage.setItem(draftKey(id), JSON.stringify({ body, clientId }));
    } catch {
      /* In-memory form still retains failures. */
    }
    const payload = new FormData();
    payload.append("body", body);
    payload.append("client_message_id", clientId);
    if (reply) payload.append("reply_to", reply.id);
    if (file) payload.append("file", file);
    pending.current = true;
    setSending(true);
    try {
      const result = await api(`/api/channels/${id}/messages/`, {
        method: "POST",
        body: payload,
      });
      try {
        sessionStorage.removeItem(draftKey(id));
      } catch {
        /* Storage may be disabled. */
      }
      setBody("");
      setFile(null);
      upload.current.value = "";
      setReply(null);
      merge([result.message]);
      bottom();
      await markRead();
      socketSend({ event: "stop:typing", channel_id: id });
    } catch (error) {
      toast(error);
    } finally {
      pending.current = false;
      setSending(false);
    }
  }
  async function loadOlder() {
    if (olderLoading || !active.current || !rows.current.length) return;
    const request = generation.current,
      height = scroll.current.scrollHeight;
    setOlderLoading(true);
    try {
      const page = await api(
        `/api/channels/${active.current.id}/messages/?before=${rows.current[0].id}`,
      );
      if (request !== generation.current) return;
      merge(page.messages);
      setHasMore(page.has_more);
      requestAnimationFrame(() => {
        scroll.current.scrollTop += scroll.current.scrollHeight - height;
      });
    } catch (error) {
      toast(error);
    } finally {
      setOlderLoading(false);
    }
  }
  function edit(message) {
    setModal({
      title: "ویرایش پیام",
      content: (
        <Form
          label="ذخیرهٔ تغییرات"
          action={async (values) => {
            const result = await api(`/api/messages/${message.id}/`, {
              method: "PATCH",
              body: { body: values.get("body") },
            });
            if (active.current?.id === message.channel_id)
              merge([result.message]);
            setModal(null);
          }}
        >
          <textarea
            name="body"
            dir="auto"
            aria-label="ویرایش پیام"
            defaultValue={message.body}
            required
            maxLength={4000}
            rows={5}
          />
        </Form>
      ),
    });
  }
  function remove(message) {
    setModal({
      title: "حذف پیام",
      content: (
        <Form
          label="حذف پیام"
          action={async () => {
            const result = await api(`/api/messages/${message.id}/`, {
              method: "DELETE",
            });
            if (active.current?.id === message.channel_id)
              merge([result.message]);
            setModal(null);
          }}
        >
          <p>
            این پیام حذف شود؟ متن و پیوست آن دیگر در گفتگو نمایش داده نمی‌شوند.
          </p>
        </Form>
      ),
    });
  }
  function invite() {
    setModal({
      title: "دعوت هم‌تیمی‌ها",
      content: (
        <Form
          label="ارسال دعوت‌نامه"
          action={async (values) => {
            const result = await api(
              `/api/workspaces/${workspace.id}/invites/`,
              { method: "POST", body: { email: values.get("email") } },
            );
            setModal({
              title: "دعوت‌نامه آماده است",
              content: (
                <>
                  <p>دعوت‌نامه برای {result.email} ساخته شد.</p>
                  <a className="invite-result" dir="ltr" href={result.url}>
                    {result.url}
                  </a>
                  <button
                    className="primary full"
                    onClick={() =>
                      navigator.clipboard
                        .writeText(result.url)
                        .then(() => toast("پیوند کپی شد."))
                        .catch(() => toast("پیوند را انتخاب و کپی کنید."))
                    }
                  >
                    کپی پیوند دعوت‌نامه
                  </button>
                </>
              ),
            });
          }}
        >
          <p>
            پیوند تا هفت روز معتبر است و فقط با ایمیل هم‌تیمی شما کار می‌کند.
          </p>
          <Field label="نشانی ایمیل" name="email" type="email" dir="ltr" />
        </Form>
      ),
    });
  }
  async function direct(member) {
    const result = await api(`/api/workspaces/${workspace.id}/direct/`, {
      method: "POST",
      body: { user_id: member.id },
    });
    const next = await refresh();
    setModal(null);
    await openChannel(
      next.channels.find((channel) => channel.id === result.id),
    );
  }
  function activity(all = false) {
    setModal({
      title: all ? "همهٔ گفتگوها" : "گفتگوهای خوانده‌نشدهٔ شما",
      type: all ? "all" : "activity",
    });
  }
  function format(mark) {
    const start = input.current.selectionStart,
      end = input.current.selectionEnd;
    changeBody(
      body.slice(0, start) +
        mark +
        body.slice(start, end) +
        mark +
        body.slice(end),
    );
    input.current.focus();
  }
  const unread = data.channels.reduce(
    (sum, channel) => sum + channel.unread,
    0,
  );
  function nav(channel) {
    return (
      <button
        key={channel.id}
        data-channel={channel.id}
        className={`channel-row${current?.id === channel.id ? " active" : ""}`}
        aria-current={current?.id === channel.id ? "page" : "false"}
        onClick={() => openChannel(channel).catch(toast)}
      >
        {channel.kind === "dm" ? (
          <Avatar name={channel.name} id={channel.id} small />
        ) : (
          <span className="symbol">
            {channel.kind === "private" ? (
              <LockKeyhole size={16} aria-hidden="true" />
            ) : (
              <Hash size={18} aria-hidden="true" />
            )}
          </span>
        )}
        <span>{channel.name}</span>
        {channel.unread > 0 && (
          <span className="count">{number.format(channel.unread)}</span>
        )}
      </button>
    );
  }
  let date = "";
  return (
    <>
      <div id="app" className="app">
        <aside className="rail" aria-label="ناوبری اصلی">
          <a className="brand-mark" href="/" aria-label="صفحهٔ اصلی اسنک">
            <Asterisk size={32} aria-hidden="true" />
          </a>
          <button
            id="home-button"
            className="rail-item active"
            onClick={() => {
              if (data.channels[0]) openChannel(data.channels[0]).catch(toast);
            }}
          >
            <House size={24} aria-hidden="true" />
            <small>خانه</small>
          </button>
          <button
            id="activity-button"
            className="rail-item"
            onClick={() => activity()}
          >
            <Activity size={24} aria-hidden="true" />
            <small>فعالیت‌ها</small>
            <i id="activity-count" hidden={!unread} />
          </button>
          <div className="rail-bottom">
            <button
              id="workspace-button"
              className="rail-item"
              title="ساخت فضای کاری"
              onClick={() =>
                setModal({
                  title: "یک فضای کاری تازه برای تیم شما",
                  content: (
                    <WorkspaceForm
                      onCreated={(result) =>
                        location.assign(`/?workspace=${result.id}`)
                      }
                    />
                  ),
                })
              }
            >
              <Plus size={18} aria-hidden="true" />
            </button>
            <button
              id="profile"
              className="avatar lavender"
              title="خروج از حساب"
              onClick={() =>
                api("/api/auth/logout/", { method: "POST" })
                  .then(() => location.assign("/accounts/login/"))
                  .catch(toast)
              }
            >
              {user.name.slice(0, 1)}
            </button>
          </div>
        </aside>
        <aside id="sidebar" className={`sidebar${sidebar ? " open" : ""}`}>
          <div className="workspace-head">
            <div className="workspace-logo">{workspace.name.slice(0, 1)}</div>
            <label className="sr-only" htmlFor="workspace-select">
              فضای کاری
            </label>
            <select
              id="workspace-select"
              value={workspace.id}
              onChange={(event) =>
                location.assign(`/?workspace=${event.target.value}`)
              }
            >
              {workspaces.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <span className="workspace-dot" />
          </div>
          <div className="workspace-caption">تیم شما، هماهنگ‌تر از همیشه</div>
          <button
            className="nav-row"
            id="all-button"
            onClick={() => activity(true)}
          >
            <LayoutGrid size={18} aria-hidden="true" /> همهٔ گفتگوها
          </button>
          <button
            className="nav-row"
            id="unread-button"
            onClick={() => activity()}
          >
            <Inbox size={18} aria-hidden="true" /> خوانده‌نشده{" "}
            <span className="count" id="unread-count">
              {number.format(unread)}
            </span>
          </button>
          <div className="section-heading">
            <span>کانال‌ها</span>
            <button
              id="add-channel"
              aria-label="ساخت کانال"
              onClick={() => {
                setKind("public");
                setModal({ title: "ساخت کانال", type: "channel" });
              }}
            >
              <Plus size={18} aria-hidden="true" />
            </button>
          </div>
          <nav id="channels" aria-label="کانال‌ها">
            {data.channels.filter((channel) => channel.kind !== "dm").map(nav)}
          </nav>
          <div className="section-heading">
            <span>پیام‌های مستقیم</span>
            <button
              id="add-dm"
              aria-label="شروع گفتگوی مستقیم"
              onClick={() => setModal({ title: "شروع گفتگو", type: "direct" })}
            >
              <Plus size={18} aria-hidden="true" />
            </button>
          </div>
          <nav id="directs" aria-label="پیام‌های مستقیم">
            {data.channels.filter((channel) => channel.kind === "dm").map(nav)}
          </nav>
          <div className="sidebar-foot">
            <div className="invite-art">
              <Sparkles size={24} aria-hidden="true" />{" "}
              <span>با هم، بهتر.</span>
            </div>
            <p>با هم‌تیمی‌هایتان کارهای خوبی رقم بزنید.</p>
            <button
              id="invite-button"
              className="invite-button"
              hidden={data.me.role !== "admin"}
              onClick={invite}
            >
              <UserPlus size={17} aria-hidden="true" /> دعوت هم‌تیمی‌ها
            </button>
            <button
              id="members-button"
              className="text-link"
              onClick={() =>
                setModal({ title: "هم‌تیمی‌های شما", type: "members" })
              }
            >
              مدیریت اعضا
            </button>
          </div>
        </aside>
        <main className="main">
          <header className="topbar">
            <button
              id="mobile-menu"
              className="icon-button"
              aria-label="باز و بسته کردن منو"
              aria-expanded={sidebar}
              onClick={() => setSidebar(!sidebar)}
            >
              <Menu size={22} aria-hidden="true" />
            </button>
            <span className="breadcrumb">
              فضای کاری <span>/</span> <b>{workspace.name}</b>
            </span>
            <form
              id="search-form"
              className="search"
              onSubmit={async (event) => {
                event.preventDefault();
                setResults([]);
                try {
                  const result = await api(
                    `/api/workspaces/${workspace.id}/search/?q=${encodeURIComponent(query)}`,
                  );
                  setResults(result.messages);
                } catch (error) {
                  toast(error);
                }
              }}
            >
              <Search size={17} aria-hidden="true" />
              <input
                id="search"
                dir="auto"
                placeholder="جستجو در فضای کاری"
                aria-label="جستجوی پیام‌ها"
                minLength={2}
                maxLength={100}
                required
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <kbd aria-label="Enter">
                <CornerDownLeft size={13} aria-hidden="true" />
              </kbd>
            </form>
            <span
              id="connection"
              className={`connection ${connection === "متصل" ? "online" : "offline"}`}
              role="status"
            >
              {connection}
            </span>
          </header>
          <div className="channel-header">
            <div>
              <div className="channel-title">
                <span id="channel-symbol">
                  {current?.kind === "private" ? (
                    <LockKeyhole size={24} aria-hidden="true" />
                  ) : current?.kind === "dm" ? (
                    <MessageCircle size={24} aria-hidden="true" />
                  ) : (
                    <Hash size={26} aria-hidden="true" />
                  )}
                </span>
                <h1 id="channel-name">{current?.name || "فضای کاری شما"}</h1>
              </div>
              <p id="channel-description">
                {current?.description || "فضایی مشترک برای تیم شما."}
              </p>
            </div>
            <button
              id="channel-members"
              className="member-stack"
              title="مشاهدهٔ اعضا"
              onClick={() =>
                setModal({ title: "هم‌تیمی‌های شما", type: "members" })
              }
            >
              <Users size={18} aria-hidden="true" />
              <span id="member-count">
                {number.format(data.members.length)}
              </span>
              <span> عضو</span>
            </button>
          </div>
          <div className="conversation-tabs">
            <button
              className="selected"
              id="messages-tab"
              onClick={() => setResults(null)}
            >
              پیام‌ها
            </button>
            <span className="channel-note">
              <i /> فضایی برای تیم شما
            </span>
          </div>
          {results !== null && (
            <section id="search-results" className="search-results">
              <div className="results-heading">
                <h2>نتایج جستجو</h2>
                <button
                  id="close-search"
                  className="icon-button"
                  aria-label="بستن جستجو"
                  onClick={() => setResults(null)}
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </div>
              <div id="results-list">
                {results.map((message) => (
                  <button
                    key={message.id}
                    className="result"
                    onClick={async () => {
                      try {
                        const channel = data.channels.find(
                          (channel) => channel.id === message.channel_id,
                        );
                        if (!channel) return;
                        await openChannel(channel);
                        if (active.current?.id === channel.id) {
                          merge([message]);
                          requestAnimationFrame(() =>
                            document
                              .getElementById(`message-${message.id}`)
                              ?.scrollIntoView({ block: "center" }),
                          );
                        }
                      } catch (error) {
                        toast(error);
                      }
                    }}
                  >
                    <small>
                      #{message.channel_name} · {message.sender} ·{" "}
                      {new Date(message.created_at).toLocaleDateString("fa-IR")}
                    </small>
                    {message.body}
                  </button>
                ))}
                {!results.length && (
                  <p className="no-results">پیامی پیدا نشد.</p>
                )}
              </div>
            </section>
          )}
          <div ref={scroll} className="message-scroll" id="message-scroll">
            <div className="channel-welcome" id="channel-welcome">
              <div className="welcome-symbol">
                <Hash size={30} aria-hidden="true" />
              </div>
              <span className="eyebrow">شروع گفتگو از اینجاست</span>
              <h2>
                به{" "}
                <span id="welcome-name">{current?.name || workspace.name}</span>{" "}
                خوش آمدید
              </h2>
              <p>
                {current?.description ||
                  "فضایی مشترک برای ایده‌ها، خبرها و گفتگوهای روزمره."}
              </p>
              <div className="welcome-tags">
                <span>
                  <Sparkles size={14} aria-hidden="true" /> همه را در جریان
                  بگذارید
                </span>
                <span>
                  <ArrowUpRight size={14} aria-hidden="true" /> با هم کارهای
                  خوبی رقم بزنید
                </span>
              </div>
            </div>
            {hasMore && (
              <button
                id="load-older"
                className="load-older"
                disabled={olderLoading}
                onClick={loadOlder}
              >
                <ArrowUp size={14} aria-hidden="true" /> نمایش پیام‌های قدیمی‌تر
              </button>
            )}
            <div
              id="message-list"
              role="log"
              aria-label="پیام‌ها"
              aria-live="polite"
            >
              {loading && <p className="muted">در حال بارگذاری گفتگو…</p>}
              {messages.map((message) => {
                const label = new Date(message.created_at).toLocaleDateString(
                    "fa-IR",
                    { weekday: "long", month: "long", day: "numeric" },
                  ),
                  divider = label !== date;
                date = label;
                const original = messages.find(
                  (item) => item.id === message.reply_to,
                );
                return (
                  <Fragment key={message.id}>
                    {divider && <div className="date-divider">{label}</div>}
                    <article className="message" id={`message-${message.id}`}>
                      <Avatar name={message.sender} id={message.sender_id} />
                      <div className="message-content">
                        <div className="message-meta">
                          <b>{message.sender}</b>
                          {message.sender_id === user.id && (
                            <span className="you">شما</span>
                          )}
                          <time dateTime={message.created_at}>
                            {new Date(message.created_at).toLocaleTimeString(
                              "fa-IR",
                              { hour: "2-digit", minute: "2-digit" },
                            )}
                          </time>
                          {message.edited_at && (
                            <small className="you">ویرایش‌شده</small>
                          )}
                        </div>
                        {message.reply_to && !message.deleted && (
                          <div className="reply-ref">
                            <Reply size={14} aria-hidden="true" />{" "}
                            {original
                              ? `${original.sender}: ${original.deleted ? "پیام حذف شده" : original.body.slice(0, 120)}`
                              : "پاسخ به یک پیام قدیمی‌تر"}
                          </div>
                        )}
                        <p
                          dir="auto"
                          className={`message-body${message.deleted ? " deleted" : ""}`}
                        >
                          {message.deleted
                            ? "این پیام حذف شده است."
                            : message.body}
                        </p>
                        {message.attachment && !message.deleted && (
                          <a
                            className="attachment-link"
                            href={message.attachment.url}
                          >
                            <span>
                              <Download size={16} aria-hidden="true" />{" "}
                              {message.attachment.name}
                            </span>
                            <small>
                              {number.format(
                                Math.ceil(message.attachment.size / 1024),
                              )}{" "}
                              کیلوبایت
                            </small>
                          </a>
                        )}
                        {!message.deleted && (
                          <div className="message-actions">
                            <button
                              onClick={() => {
                                setReply(message);
                                input.current.focus();
                              }}
                            >
                              <Reply size={14} aria-hidden="true" /> پاسخ
                            </button>
                            {message.sender_id === user.id && (
                              <button onClick={() => edit(message)}>
                                <Pencil size={14} aria-hidden="true" /> ویرایش
                              </button>
                            )}
                            {(message.sender_id === user.id ||
                              data.me.role === "admin") && (
                              <button onClick={() => remove(message)}>
                                <Trash2 size={14} aria-hidden="true" /> حذف
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </article>
                  </Fragment>
                );
              })}
            </div>
            {!loading && !messages.length && (
              <div id="empty-state" className="empty-state">
                هنوز پیامی نیست. شما گفتگو را شروع کنید.
              </div>
            )}
          </div>
          <div className="compose-wrap">
            <div id="typing" className="typing" aria-live="polite">
              {typing}
            </div>
            <form id="compose" className="composer" onSubmit={send}>
              <div className="format-bar">
                {[
                  { mark: "**", Icon: Bold, label: "متن ضخیم" },
                  { mark: "_", Icon: Italic, label: "متن مورب" },
                  { mark: "`", Icon: Code, label: "کد" },
                ].map(({ mark, Icon, label }) => (
                  <button
                    key={mark}
                    type="button"
                    aria-label={label}
                    onClick={() => format(mark)}
                  >
                    <Icon size={16} aria-hidden="true" />
                  </button>
                ))}
                <span className="format-hint">
                  ایدهٔ بعدی شما از اینجا شروع می‌شود
                </span>
              </div>
              {reply && (
                <div id="reply-banner" className="reply-banner">
                  پاسخ به {reply.sender}: {reply.body.slice(0, 90)}
                  <button
                    type="button"
                    aria-label="لغو پاسخ"
                    onClick={() => setReply(null)}
                  >
                    <X size={18} aria-hidden="true" />
                  </button>
                </div>
              )}
              <label className="sr-only" htmlFor="message-input">
                پیام
              </label>
              <textarea
                ref={input}
                id="message-input"
                dir="auto"
                maxLength={4000}
                rows={2}
                placeholder={`پیام به ${current?.name || "تیم"}…`}
                required={!file}
                disabled={sending || !current}
                value={body}
                onChange={(event) => changeBody(event.target.value)}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey &&
                    !event.nativeEvent.isComposing
                  ) {
                    event.preventDefault();
                    if (!sending) event.currentTarget.form.requestSubmit();
                  }
                }}
              />
              {file && (
                <div id="file-preview">
                  <Paperclip size={16} aria-hidden="true" /> {file.name}
                  <button
                    type="button"
                    aria-label="حذف فایل"
                    onClick={() => {
                      setFile(null);
                      upload.current.value = "";
                    }}
                  >
                    <X size={18} aria-hidden="true" />
                  </button>
                </div>
              )}
              <div className="compose-actions">
                <div>
                  <button
                    type="button"
                    className="icon-button"
                    id="attach-button"
                    aria-label="پیوست فایل"
                    disabled={sending}
                    onClick={() => upload.current.click()}
                  >
                    <Paperclip size={18} aria-hidden="true" />
                  </button>
                  <input
                    ref={upload}
                    type="file"
                    id="attachment"
                    hidden
                    disabled={sending}
                    accept=".png,.jpg,.jpeg,.gif,.webp,.pdf,.txt,.csv,.md,.zip"
                    onChange={(event) => {
                      const next = event.target.files[0];
                      if (next?.size > 10 * 1024 * 1024) {
                        toast("حجم فایل باید حداکثر ۱۰ مگابایت باشد.");
                        event.target.value = "";
                        setFile(null);
                      } else setFile(next || null);
                    }}
                  />
                  <button
                    type="button"
                    className="icon-button"
                    id="emoji-button"
                    aria-label="افزودن شکلک"
                    disabled={sending}
                    onClick={() =>
                      setModal({
                        title: "یک شکلک انتخاب کنید",
                        content: (
                          <div className="emoji-picker">
                            {[
                              "👋",
                              "🎉",
                              "👍",
                              "💜",
                              "🙌",
                              "🚀",
                              "✅",
                              "😊",
                            ].map((emoji) => (
                              <button
                                key={emoji}
                                className="icon-button"
                                onClick={() => {
                                  changeBody(body + emoji);
                                  setModal(null);
                                  input.current.focus();
                                }}
                              >
                                {emoji}
                              </button>
                            ))}
                          </div>
                        ),
                      })
                    }
                  >
                    <Smile size={20} aria-hidden="true" />
                  </button>
                  <span className="compose-private">
                    گفتگوی شما در همین فضای کاری می‌ماند
                  </span>
                </div>
                <button
                  className="send-button"
                  id="send-button"
                  aria-label="ارسال پیام"
                  disabled={sending || !current || loading}
                >
                  <ArrowUp size={19} aria-hidden="true" />
                </button>
              </div>
            </form>
            <p className="composer-tip">
              <b dir="ltr">Enter</b> برای ارسال · <b dir="ltr">Shift + Enter</b>{" "}
              برای خط جدید{" "}
              <span>
                اینجا همکاری جریان دارد.{" "}
                <Asterisk size={32} aria-hidden="true" />
              </span>
            </p>
          </div>
        </main>
      </div>
      {modal && (
        <Dialog
          key={modal.title}
          title={modal.title}
          close={() => setModal(null)}
        >
          {modal.content}
          {modal.type === "channel" && (
            <Form
              label="ساخت کانال"
              action={async (values) => {
                const result = await api(
                  `/api/workspaces/${workspace.id}/channels/`,
                  {
                    method: "POST",
                    body: {
                      name: values.get("name"),
                      description: values.get("description"),
                      kind: values.get("kind"),
                      members: values.getAll("members").map(Number),
                    },
                  },
                );
                const next = await refresh();
                setModal(null);
                await openChannel(
                  next.channels.find((channel) => channel.id === result.id),
                );
              }}
            >
              <Field name="name" label="نام کانال" maxLength={80} />
              <Field
                name="description"
                label="موضوع این کانال"
                maxLength={240}
                required={false}
              />
              <label htmlFor="channel-kind">نوع کانال</label>
              <select
                id="channel-kind"
                name="kind"
                value={kind}
                onChange={(event) => setKind(event.target.value)}
              >
                <option value="public">عمومی</option>
                <option value="private">خصوصی</option>
              </select>
              {kind === "private" && (
                <fieldset>
                  <legend>اعضای کانال</legend>
                  {data.members
                    .filter((member) => member.id !== user.id)
                    .map((member) => (
                      <label key={member.id}>
                        <input
                          type="checkbox"
                          name="members"
                          value={member.id}
                        />{" "}
                        {member.name}
                      </label>
                    ))}
                </fieldset>
              )}
            </Form>
          )}
          {["members", "direct"].includes(modal.type) && (
            <div className="people-list">
              {data.members
                .filter(
                  (member) => modal.type !== "direct" || member.id !== user.id,
                )
                .map((member) => (
                  <div key={member.id} className="person-row">
                    <button
                      className="person"
                      onClick={() => {
                        if (member.id !== user.id) direct(member).catch(toast);
                      }}
                    >
                      <Avatar name={member.name} id={member.id} />
                      <span>
                        <b>{member.name}</b>
                        <small dir="ltr">{member.email}</small>
                        <small>{member.online ? "آنلاین" : "آفلاین"}</small>
                      </span>
                    </button>
                    {modal.type === "members" &&
                      (data.me.role === "admin" ? (
                        <>
                          <select
                            aria-label={`نقش ${member.name}`}
                            value={member.role}
                            onChange={(event) =>
                              api(
                                `/api/workspaces/${workspace.id}/members/${member.id}/`,
                                {
                                  method: "POST",
                                  body: { role: event.target.value },
                                },
                              )
                                .then(refresh)
                                .catch(toast)
                            }
                          >
                            <option value="member">عضو</option>
                            <option value="admin">مدیر</option>
                          </select>
                          <button
                            className="text-link"
                            onClick={() =>
                              setModal({
                                title: "حذف عضو",
                                content: (
                                  <Form
                                    label="حذف عضو"
                                    action={async () => {
                                      await api(
                                        `/api/workspaces/${workspace.id}/members/${member.id}/`,
                                        {
                                          method: "POST",
                                          body: { role: "remove" },
                                        },
                                      );
                                      if (member.id === user.id)
                                        location.assign("/");
                                      else {
                                        await refresh();
                                        setModal({
                                          title: "هم‌تیمی‌های شما",
                                          type: "members",
                                        });
                                      }
                                    }}
                                  >
                                    <p>{member.name} از فضای کاری حذف شود؟</p>
                                  </Form>
                                ),
                              })
                            }
                          >
                            <Trash2 size={14} aria-hidden="true" /> حذف
                          </button>
                        </>
                      ) : (
                        <small>
                          {member.role === "admin" ? "مدیر" : "عضو"}
                        </small>
                      ))}
                  </div>
                ))}
            </div>
          )}
          {["activity", "all"].includes(modal.type) && (
            <div>
              {data.channels
                .filter((channel) => modal.type === "all" || channel.unread)
                .map((channel) => (
                  <button
                    key={channel.id}
                    className="activity-card"
                    onClick={() => {
                      setModal(null);
                      openChannel(channel).catch(toast);
                    }}
                  >
                    <b>{channel.name}</b>
                    <span className="count">
                      {number.format(channel.unread)} خوانده‌نشده
                    </span>
                  </button>
                ))}
              {!unread && modal.type === "activity" && (
                <p>همهٔ پیام‌ها را خوانده‌اید.</p>
              )}
            </div>
          )}
        </Dialog>
      )}
      {notice && (
        <div id="toast" role="status">
          {notice}
        </div>
      )}
    </>
  );
}

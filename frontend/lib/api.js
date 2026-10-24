let csrfToken = "";
export async function api(url, options = {}) {
  const headers = { ...options.headers };
  const method = options.method || "GET";
  if (!["GET", "HEAD"].includes(method)) {
    if (!csrfToken) await api("/api/session/");
    // Django rotates CSRF cookies at login; always use the current cookie.
    const cookie = document.cookie
      .split("; ")
      .find((item) => item.startsWith("csrftoken="));
    headers["X-CSRFToken"] = cookie
      ? decodeURIComponent(cookie.split("=")[1])
      : csrfToken;
  }
  let body = options.body;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(url, {
      ...options,
      body,
      headers,
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new Error("ارتباط قطع شد. دوباره تلاش کنید.");
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("پاسخ سرور معتبر نیست. دوباره تلاش کنید.");
  }
  if (data.csrfToken) csrfToken = data.csrfToken;
  if (!response.ok) {
    if (response.status === 401)
      location.assign(
        `/accounts/login/?next=${encodeURIComponent(location.pathname + location.search)}`,
      );
    throw new Error(data.error || "انجام درخواست ممکن نشد.");
  }
  return data;
}

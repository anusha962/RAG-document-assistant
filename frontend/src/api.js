const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export const getToken = () => localStorage.getItem("token");
export const setSession = (token, username) => {
  if (token) {
    localStorage.setItem("token", token);
    localStorage.setItem("username", username || "");
  } else {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
  }
};

function errorText(data) {
  if (!data || typeof data !== "object") return "Something went wrong. Try again.";
  if (data.detail) return data.detail;
  const first = Object.values(data)[0];
  return Array.isArray(first) ? first[0] : String(first);
}

async function request(path, { method = "GET", json, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Token ${token}`;
  if (json) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(`${BASE}/api${path}`, {
      method,
      headers,
      body: form || (json ? JSON.stringify(json) : undefined),
    });
  } catch {
    throw new Error("Can't reach the server. It may be waking up — try again in a moment.");
  }
  if (res.status === 401 && token) {
    setSession(null);
    window.location.reload();
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorText(data));
  return data;
}

export const api = {
  login: (username, password) => request("/auth/login/", { method: "POST", json: { username, password } }),
  register: (username, password) => request("/auth/register/", { method: "POST", json: { username, password } }),
  listDocs: () => request("/documents/"),
  uploadDoc: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/documents/", { method: "POST", form });
  },
  deleteDoc: (id) => request(`/documents/${id}/`, { method: "DELETE" }),
  chat: (question, documentIds, history) =>
    request("/chat/", { method: "POST", json: { question, document_ids: documentIds, history } }),
};

/** Streams a chat answer over server-sent events. */
export async function chatStream(question, documentIds, history, on, signal) {
  let res;
  try {
    res = await fetch(`${BASE}/api/chat/stream/`, {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Authorization: `Token ${getToken()}` },
      body: JSON.stringify({ question, document_ids: documentIds, history }),
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error("Can't reach the server. It may be waking up — try again in a moment.");
  }
  if (res.status === 401) { setSession(null); window.location.reload(); }
  if (!res.ok) throw new Error(errorText(await res.json().catch(() => ({}))));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = /^event: (.+)$/m.exec(block)?.[1];
      const data = /^data: (.+)$/m.exec(block)?.[1];
      if (event && data) on[event]?.(JSON.parse(data));
    }
  }
}

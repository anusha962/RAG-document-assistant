import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { chatStream } from "./api";

const SUGGESTIONS = [
  "Summarize the key points in a few bullets",
  "What dates, numbers or deadlines are mentioned?",
  "What are the main risks or open questions?",
];

function Reply({ m, streaming }) {
  const [active, setActive] = useState(null);
  const [copied, setCopied] = useState(false);
  const text = m.content.replace(/\[(\d+)\]/g, "[$1](#src-$1)");
  const source = m.sources?.find((s) => s.id === active);

  const copy = () => {
    navigator.clipboard?.writeText(m.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <article className="reply">
      {(m.content || streaming) && (
        <div className="prose">
          <Markdown
            components={{
              a: ({ href, children }) =>
                href?.startsWith("#src-") ? (
                  <button className="cite" onClick={() => setActive(active === +href.slice(5) ? null : +href.slice(5))}>
                    {children}
                  </button>
                ) : (
                  <a href={href} target="_blank" rel="noreferrer">{children}</a>
                ),
            }}
          >
            {text}
          </Markdown>
          {streaming && <span className="caret" aria-hidden />}
        </div>
      )}
      {m.error && <p className="error" role="alert">{m.error}</p>}

      {m.sources?.length > 0 && (
        <div className="evidence">
          <span className="label">Sources</span>
          {m.sources.map((s) => (
            <button key={s.id} className={`chip ${active === s.id ? "on" : ""}`} onClick={() => setActive(active === s.id ? null : s.id)}>
              <b>{s.id}</b>
              <span>{s.document}{s.page ? ` · p.${s.page}` : ""}</span>
            </button>
          ))}
          {!streaming && m.content && <button className="link copy" onClick={copy}>{copied ? "Copied" : "Copy answer"}</button>}
        </div>
      )}

      {source && (
        <div className="passage">
          <div className="passage-head">
            <span>{source.document}{source.page ? `, page ${source.page}` : ""}</span>
            <span className="meter" title="How closely this passage matches your question">
              <i style={{ width: `${Math.min(100, Math.round(source.score * 100))}%` }} />
            </span>
            <span className="muted small">{Math.round(source.score * 100)}% match</span>
          </div>
          <blockquote><mark>{source.excerpt}</mark></blockquote>
        </div>
      )}
    </article>
  );
}

export default function Chat({ hasDocs, selected, docCount }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  const abort = useRef(null);

  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [messages]);

  async function send(text = question) {
    const q = text.trim();
    if (!q || busy) return;
    const history = messages.filter((m) => m.content && !m.error).map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "", sources: [] }]);
    setQuestion("");
    setBusy(true);
    const ctrl = new AbortController();
    abort.current = ctrl;
    const patch = (fn) => setMessages((m) => m.map((x, i) => (i === m.length - 1 ? fn(x) : x)));
    try {
      await chatStream(q, selected, history, {
        sources: (sources) => patch((x) => ({ ...x, sources })),
        token: (t) => patch((x) => ({ ...x, content: x.content + t })),
        error: (error) => patch((x) => ({ ...x, error })),
      }, ctrl.signal);
    } catch (e) {
      if (e.name !== "AbortError") patch((x) => ({ ...x, error: e.message }));
    } finally {
      setBusy(false);
    }
  }

  const scope = selected.length ? `${selected.length} selected` : `all ${docCount} document${docCount === 1 ? "" : "s"}`;

  return (
    <main className="chat">
      <div className="thread">
        {messages.length === 0 && (
          <div className="intro">
            <h1>{hasDocs ? "What would you like to know?" : "Start with a document"}</h1>
            <p className="muted">
              {hasDocs
                ? "Answers are written from your files, and every claim links to the passage behind it."
                : "Upload a PDF, Word or text file on the left. Then ask anything about it."}
            </p>
            {hasDocs && (
              <div className="suggest">
                {SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}
              </div>
            )}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <p key={i} className="question">{m.content}</p>
          ) : (
            <Reply key={i} m={m} streaming={busy && i === messages.length - 1} />
          )
        )}
        <div ref={end} />
      </div>

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            rows={1}
            value={question}
            placeholder={hasDocs ? "Ask a question about your documents" : "Upload a document to get started"}
            disabled={!hasDocs}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            aria-label="Your question"
          />
          {busy ? (
            <button className="send stop" onClick={() => abort.current?.abort()} aria-label="Stop answering">
              <svg width="14" height="14" viewBox="0 0 14 14"><rect width="14" height="14" rx="2" fill="currentColor" /></svg>
            </button>
          ) : (
            <button className="send" onClick={() => send()} disabled={!hasDocs || !question.trim()} aria-label="Ask">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
            </button>
          )}
        </div>
        {hasDocs && <p className="scope small muted">Searching {scope}. Enter to send, Shift+Enter for a new line.</p>}
      </div>
    </main>
  );
}

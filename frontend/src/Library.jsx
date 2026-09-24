import { useRef, useState } from "react";

const kind = (t) => (t.split(".").pop() || "txt").slice(0, 4).toUpperCase();

export default function Library({ user, docs, selected, setSelected, uploading, notice, onUpload, onDelete, onSignOut }) {
  const input = useRef(null);
  const [drag, setDrag] = useState(false);
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <aside className="library">
      <div className="brand">
        <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden><rect x="3" y="2" width="16" height="22" rx="3" fill="#fff" /><rect x="7" y="8" width="12" height="5" fill="var(--mark)" /><rect x="7" y="16" width="8" height="2" fill="#0e1a2b" opacity=".5" /></svg>
        <div><strong>Marginalia</strong><span>AI document assistant</span></div>
      </div>

      <div
        className={`drop ${drag ? "drag" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); onUpload([...e.dataTransfer.files]); }}
      >
        <input ref={input} type="file" hidden multiple accept=".pdf,.docx,.txt,.md" onChange={(e) => { onUpload([...e.target.files]); e.target.value = ""; }} />
        <button onClick={() => input.current.click()} disabled={uploading}>{uploading ? "Reading file…" : "Upload files"}</button>
        <p>Drop PDF, Word, TXT or Markdown here. 10 MB max each.</p>
      </div>

      {notice && <p className="error" role="alert">{notice}</p>}

      <div className="list-head">
        <span>Documents</span>
        {selected.length > 0 && <button className="link" onClick={() => setSelected([])}>Clear selection</button>}
      </div>
      {docs.length === 0 ? (
        <p className="side-muted">Nothing here yet. Your uploads will appear in this list.</p>
      ) : (
        <ul className="docs">
          {docs.map((d) => (
            <li key={d.id} className={selected.includes(d.id) ? "on" : ""}>
              <label>
                <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} />
                <span className="badge">{kind(d.title)}</span>
                <span className="doc-info">
                  <span className="doc-title">{d.title}</span>
                  <span className="side-muted">{d.chunk_count} passages</span>
                </span>
              </label>
              <button className="x" onClick={() => onDelete(d.id)} aria-label={`Delete ${d.title}`} title="Delete">×</button>
            </li>
          ))}
        </ul>
      )}

      <div className="who">
        <span>{user}</span>
        <button className="link" onClick={onSignOut}>Sign out</button>
      </div>
    </aside>
  );
}

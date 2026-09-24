import { useEffect, useState } from "react";
import { api, getToken, setSession } from "./api";
import Auth from "./Auth.jsx";
import Library from "./Library.jsx";
import Chat from "./Chat.jsx";

export default function App() {
  const [user, setUser] = useState(getToken() ? localStorage.getItem("username") : null);
  if (!user) return <Auth onAuth={setUser} />;
  return <Workspace user={user} onSignOut={() => { setSession(null); setUser(null); }} />;
}

function Workspace({ user, onSignOut }) {
  const [docs, setDocs] = useState([]);
  const [selected, setSelected] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api.listDocs().then(setDocs).catch((e) => setNotice(e.message));
  }, []);

  async function upload(files) {
    setUploading(true);
    setNotice("");
    for (const file of files) {
      try {
        const doc = await api.uploadDoc(file);
        setDocs((d) => [doc, ...d]);
      } catch (e) {
        setNotice(`${file.name}: ${e.message}`);
      }
    }
    setUploading(false);
  }

  async function remove(id) {
    try {
      await api.deleteDoc(id);
      setDocs((d) => d.filter((x) => x.id !== id));
      setSelected((s) => s.filter((x) => x !== id));
    } catch (e) {
      setNotice(e.message);
    }
  }

  return (
    <div className="shell">
      <Library
        user={user}
        docs={docs}
        selected={selected}
        setSelected={setSelected}
        uploading={uploading}
        notice={notice}
        onUpload={upload}
        onDelete={remove}
        onSignOut={onSignOut}
      />
      <Chat hasDocs={docs.length > 0} selected={selected} docCount={docs.length} />
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import {
  Search,
  Star,
  Github,
  GitFork,
  LogIn,
  LogOut,
  UserPlus,
  X,
  LoaderCircle,
  ExternalLink,
  AlertCircle,
  Check,
  BookmarkCheck,
  Sparkles,
} from "lucide-react";
import { authApi, searchApi, favoritesApi } from "./api";

const INITIAL_QUERY = {
  type: "repositories",
  query: "django rest",
  per_page: 10,
};

const EMPTY_FORM = {
  username: "",
  email: "",
  password: "",
};

/**
 * Normalizes both a GitHub Search API item and a Favorite from the backend.
 * - id: the Favorite record id, when there is one;
 * - repo_id: the GitHub repository id, used to add and remove favorites.
 */
function normalize(repo = {}) {
  const repoId = repo.repo_id ?? repo.repository_id ?? repo.id ?? null;

  return {
    ...repo,
    id: repo.id ?? null,
    repo_id: repoId,
    full_name: repo.full_name || repo.name || "Unknown repository",
    html_url: repo.html_url || "#",
    description: repo.description || "",
    stargazers_count: repo.stargazers_count ?? 0,
    forks_count: repo.forks_count ?? 0,
    language: repo.language || "",
  };
}

function getRepoId(repo) {
  const id = repo?.repo_id ?? repo?.repository_id ?? repo?.id;
  return id == null ? "" : String(id);
}

function getErrorMessage(error, fallback) {
  const data = error?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (typeof data?.message === "string") return data.message;
  if (typeof data === "object" && data) {
    const firstValue = Object.values(data).flat()[0];
    if (typeof firstValue === "string") return firstValue;
  }
  return fallback;
}

export default function App() {
  const [query, setQuery] = useState(INITIAL_QUERY);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [tab, setTab] = useState("search");

  const [user, setUser] = useState(() => {
    const username = localStorage.getItem("username");
    const accessToken = localStorage.getItem("access_token");
    return username && accessToken ? { username } : null;
  });

  const [modal, setModal] = useState(false);
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState(EMPTY_FORM);
  const [favorites, setFavorites] = useState([]);

  const [loading, setLoading] = useState(false);
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const favIds = useMemo(
    () => new Set(favorites.map(getRepoId).filter(Boolean)),
    [favorites]
  );

  const visible = tab === "favorites" ? favorites : results;

  useEffect(() => {
    if (user && localStorage.getItem("access_token")) {
      loadFavorites();
    } else {
      setFavorites([]);
    }
    // loadFavorites intentionally runs when the authenticated user changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function search(event) {
    event?.preventDefault();
    setLoading(true);
    setError("");
    setNotice("");

    try {
      const { data } = await searchApi.search(query);
      const list = data?.items ?? data?.results ?? data?.repositories ?? [];
      const items = Array.isArray(list) ? list.map(normalize) : [];

      setResults(items);
      setTotal(Number(data?.total_count ?? data?.count ?? items.length));
      setTab("search");
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          "Search failed. Make sure the backend is running."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadFavorites() {
    if (!localStorage.getItem("access_token")) {
      setFavorites([]);
      return;
    }

    setFavoritesLoading(true);
    try {
      const { data } = await favoritesApi.list();
      const list = Array.isArray(data)
        ? data
        : data?.results ?? data?.favorites ?? [];
      setFavorites(Array.isArray(list) ? list.map(normalize) : []);
    } catch (err) {
      if (err.response?.status === 401) {
        setFavorites([]);
        setError("Your session has expired. Please log in again.");
      } else {
        setError(getErrorMessage(err, "Could not load your favorites."));
      }
    } finally {
      setFavoritesLoading(false);
    }
  }

  function openAuth(nextMode = "login") {
    setMode(nextMode);
    setForm(EMPTY_FORM);
    setError("");
    setNotice("");
    setModal(true);
  }

  async function handleAuth(event) {
    event.preventDefault();
    setAuthLoading(true);
    setError("");
    setNotice("");

    try {
      if (mode === "register") {
        await authApi.register({
          username: form.username.trim(),
          email: form.email.trim(),
          password: form.password,
        });
      }

      const { data } = await authApi.login({
        username: form.username.trim(),
        password: form.password,
      });

      if (!data?.access) {
        throw new Error("The server did not return an access token.");
      }

      localStorage.setItem("access_token", data.access);
      if (data.refresh) localStorage.setItem("refresh_token", data.refresh);
      localStorage.setItem("username", form.username.trim());

      setUser({ username: form.username.trim() });
      setModal(false);
      setForm(EMPTY_FORM);
      setNotice(mode === "register" ? "Account created. You are logged in." : "Logged in.");
      setError("");
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          err.message || "Could not log in. Check your username and password."
        )
      );
    } finally {
      setAuthLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("username");
    setUser(null);
    setFavorites([]);
    setTab("search");
    setModal(false);
    setNotice("Logged out.");
    setError("");
  }

  async function toggleFavorite(repo) {
    if (!user || !localStorage.getItem("access_token")) {
      openAuth("login");
      setNotice("Log in to save repositories.");
      return;
    }

    const repoId = getRepoId(repo);
    if (!repoId) {
      setError("Could not determine this repository's GitHub ID.");
      return;
    }

    setBusy(repoId);
    setError("");
    setNotice("");

    try {
      if (favIds.has(repoId)) {
        // Backend route is favorites/<int:repo_id>/, so pass the GitHub repo ID.
        await favoritesApi.remove(repoId);
        setFavorites((current) => current.filter((item) => getRepoId(item) !== repoId));
        setNotice("Removed from favorites.");
      } else {
        const payload = {
          repo_id: Number(repoId),
          full_name: repo.full_name,
          html_url: repo.html_url,
          description: repo.description || "",
          stargazers_count: repo.stargazers_count ?? 0,
          forks_count: repo.forks_count ?? 0,
          language: repo.language || "",
        };

        await favoritesApi.add(payload);
        // Keep the UI in sync immediately; reload provides the canonical server record.
        setFavorites((current) => [
          normalize(payload),
          ...current.filter((item) => getRepoId(item) !== repoId),
        ]);
        setNotice("Saved to favorites.");
        if (tab === "favorites") await loadFavorites();
      }
    } catch (err) {
      const status = err.response?.status;
      if (status === 401) {
        setError("Your session has expired. Please log in again.");
      } else if (status === 404 && favIds.has(repoId)) {
        // If backend reports it absent, refresh the list to reconcile UI and server.
        await loadFavorites();
        setError("That favorite no longer exists on the server. The list has been refreshed.");
      } else {
        setError(getErrorMessage(err, "Could not update favorites."));
      }
    } finally {
      setBusy("");
    }
  }

  async function openFavorites() {
    if (!user) {
      openAuth("login");
      setNotice("Log in to see your saved repositories.");
      return;
    }

    setTab("favorites");
    setError("");
    setNotice("");
    await loadFavorites();
  }

  function updateQuery(field, value) {
    setQuery((current) => ({ ...current, [field]: value }));
  }

  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="RepoRadar home">
          <span className="brand-icon"><Github size={22} /></span>
          <span>Repo<span className="accent">Radar</span><small>DISCOVER OPEN SOURCE</small></span>
        </a>
        <div className="top-actions">
          {user ? (
            <>
              <span className="username"><i>{user.username.slice(0, 1).toUpperCase()}</i>{user.username}</span>
              <button className="btn ghost" onClick={logout}><LogOut size={15} /> Log out</button>
            </>
          ) : (
            <>
              <button className="btn ghost" onClick={() => openAuth("login")}><LogIn size={15} /> Log in</button>
              <button className="btn primary" onClick={() => openAuth("register")}><UserPlus size={15} /> Sign up</button>
            </>
          )}
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div>
            <div className="eyebrow"><Sparkles size={14} /> FIND YOUR NEXT FAVORITE REPOSITORY</div>
            <h1>Explore code.<br /><span>Build something.</span></h1>
            <p>Find interesting open-source projects, compare their stats and keep a list of the ones you like.</p>
            <div className="stats">
              <div><b>GitHub</b><small>OPEN SOURCE</small></div>
              <div><b>{total.toLocaleString()}</b><small>FOUND</small></div>
              <div><b>{favorites.length}</b><small>SAVED</small></div>
            </div>
          </div>
          <div className="art" aria-hidden="true">
            <div className="orbit" />
            <div className="code">
              <div className="window"><i /><i /><i /><span>repository.json</span></div>
              <pre><em>const</em> project = {"{"}<br />  <strong>name</strong>: <b>"awesome-app"</b>,<br />  <strong>stars</strong>: <mark>12840</mark>,<br />  <strong>openSource</strong>: true<br />{"};"}</pre>
              <footer><span>STATUS: DISCOVERING</span><span>● LIVE</span></footer>
            </div>
            <div className="float-star"><Star size={23} /></div>
            <div className="float-github"><Github size={25} /></div>
          </div>
        </section>

        <section className="workspace">
          <div className="section-head">
            <div><small>REPOSITORY EXPLORER</small><h2>Find your next project</h2></div>
            <div className="tabs">
              <button className={tab === "search" ? "active" : ""} onClick={() => setTab("search")}><Search size={15} /> Search</button>
              <button className={tab === "favorites" ? "active" : ""} onClick={openFavorites}><BookmarkCheck size={15} /> Favorites <b>{favorites.length}</b></button>
            </div>
          </div>

          <form className="searchbar" onSubmit={search}>
            <Search size={18} />
            <input
              aria-label="Search query"
              value={query.query}
              onChange={(event) => updateQuery("query", event.target.value)}
              placeholder="e.g. django rest"
              required
            />
            <button className="btn primary" type="submit" disabled={loading}>
              {loading ? <LoaderCircle className="spin" size={16} /> : <Search size={16} />}
              {loading ? "Searching..." : "Search"}
            </button>
          </form>

          {error && <div className="alert error" role="alert"><AlertCircle size={17} /><span>{error}</span><button type="button" aria-label="Dismiss message" onClick={() => setError("")}><X size={15} /></button></div>}
          {notice && <div className="alert success" role="status"><Check size={17} /><span>{notice}</span><button type="button" aria-label="Dismiss message" onClick={() => setNotice("")}><X size={15} /></button></div>}

          <div className="results-head">
            <div><h3>{tab === "favorites" ? "Saved repositories" : "Search results"}</h3><p>{tab === "favorites" ? `${favorites.length} saved` : `${total.toLocaleString()} results`}</p></div>
            <small>{tab === "favorites" ? "YOUR COLLECTION" : "GITHUB REPOSITORIES"}</small>
          </div>

          {((tab === "favorites" && favoritesLoading) || (tab === "search" && loading)) ? (
            <div className="empty"><LoaderCircle className="spin" size={26} /><b>Loading...</b><p>Fetching data, one moment.</p></div>
          ) : visible.length ? (
            <div className="grid">
              {visible.map((repo) => {
                const repoId = getRepoId(repo);
                const saved = favIds.has(repoId);
                const isBusy = busy === repoId;
                return (
                  <article className="card" key={repoId || repo.full_name}>
                    <div className="card-top">
                      <span className="repo-icon"><Github size={19} /></span>
                      <button
                        className={`star ${saved ? "saved" : ""}`}
                        type="button"
                        title={saved ? "Remove from favorites" : "Save repository"}
                        aria-label={saved ? `Remove ${repo.full_name} from favorites` : `Save ${repo.full_name}`}
                        disabled={Boolean(busy)}
                        onClick={() => toggleFavorite(repo)}
                      >
                        {isBusy ? <LoaderCircle className="spin" size={17} /> : <Star size={17} fill={saved ? "currentColor" : "none"} />}
                      </button>
                    </div>
                    <a className="repo-name" href={repo.html_url} target="_blank" rel="noreferrer">
                      {repo.full_name}<ExternalLink size={13} />
                    </a>
                    <p className="description">{repo.description || "No description provided."}</p>
                    <div className="meta">
                      <span><Star size={13} /> {(repo.stargazers_count ?? 0).toLocaleString()}</span>
                      <span><GitFork size={13} /> {(repo.forks_count ?? 0).toLocaleString()}</span>
                      {repo.language && <span><i />{repo.language}</span>}
                    </div>
                    <div className="card-foot"><span>GITHUB REPOSITORY</span><span>#{repoId || "—"}</span></div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="empty">
              {tab === "favorites" ? <BookmarkCheck size={27} /> : <Search size={27} />}
              <b>{tab === "favorites" ? "Nothing saved yet" : "No results"}</b>
              <p>{tab === "favorites" ? "Click the star on a repository card to add it here." : "Try a different search query."}</p>
            </div>
          )}
        </section>
      </main>

      <footer className="bottom">
        <span><Github size={15} /> RepoRadar</span>
        <span>Discover projects. Save ideas.</span>
        <span>Powered by GitHub</span>
      </footer>

      {modal && (
        <div className="backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setModal(false);
        }}>
          <section className="modal" role="dialog" aria-modal="true" aria-labelledby="auth-title">
            <button className="close" type="button" aria-label="Close" onClick={() => setModal(false)}><X size={17} /></button>
            <div className="modal-icon">{mode === "register" ? <UserPlus size={23} /> : <LogIn size={23} />}</div>
            <small>REPORADAR ACCOUNT</small>
            <h2 id="auth-title">{mode === "register" ? "Create an account" : "Welcome back!"}</h2>
            <p>{mode === "register" ? "Sign up to save your favorite repositories." : "Log in to open your collection."}</p>
            <form onSubmit={handleAuth}>
              <label>Username<input autoComplete="username" value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} required /></label>
              {mode === "register" && <label>Email<input type="email" autoComplete="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} required /></label>}
              <label>Password<input type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} minLength={mode === "register" ? 8 : undefined} required /></label>
              <button className="btn primary submit" type="submit" disabled={authLoading}>
                {authLoading && <LoaderCircle className="spin" size={16} />}
                {mode === "register" ? "Sign up" : "Log in"}
              </button>
            </form>
            <button className="switch" type="button" onClick={() => { setMode(mode === "register" ? "login" : "register"); setForm(EMPTY_FORM); setError(""); }}>
              {mode === "register" ? "Already have an account? Log in" : "No account yet? Sign up"}
            </button>
          </section>
        </div>
      )}
    </div>
  );
}

import React, { useEffect, useRef, useState } from "react";
import { Routes, Route } from "react-router-dom";

import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import Toast from "./components/Toast.jsx";
import Login from "./pages/Login.jsx";
import Home from "./pages/Home.jsx";
import CreateRecord from "./pages/CreateRecord.jsx";
import UpdateRecord from "./pages/UpdateRecord.jsx";
import DeleteRecord from "./pages/DeleteRecord.jsx";

import {
  me,
  logout,
  fetchRecalls,
  createRecall,
  updateRecall,
  deleteRecall,
  deleteHighestRecall,
} from "./api/recallsApi.js";

function RequireAuth({ auth, children }) {
  if (!auth.loggedIn) {
    return (
      <div className="card">
        <div className="view-head">
          <h2>Login Required</h2>
        </div>
        <div className="notice">Please login to access this page.</div>
      </div>
    );
  }
  return children;
}

export default function App() {
  const [auth, setAuth] = useState({ loggedIn: false, user: null, checked: false });
  const [recalls, setRecalls] = useState([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [selectedRecall, setSelectedRecall] = useState(null);
  const toastTimer = useRef(null);

  function showToast(message, ok = true) {
    clearTimeout(toastTimer.current);
    setToast({ message, ok });
    toastTimer.current = setTimeout(() => setToast(null), 3500);
  }

  useEffect(() => {
    (async () => {
      try {
        const user = await me();
        setAuth({ loggedIn: true, user, checked: true });
      } catch {
        setAuth({ loggedIn: false, user: null, checked: true });
      }
    })();
  }, []);

  async function reload() {
    if (!auth.loggedIn) {
      setRecalls([]);
      return;
    }
    try {
      setLoading(true);
      setRecalls(await fetchRecalls());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, [auth.loggedIn]);

  function onLogin(user) {
    setAuth({ loggedIn: true, user, checked: true });
  }

  async function onLogout() {
    await logout();
    setAuth({ loggedIn: false, user: null, checked: true });
  }

  async function onAdd(payload) {
    const created = await createRecall(payload);
    setRecalls((prev) => [...prev, created]);
    return created;
  }

  async function onUpdate(id, payload) {
    const updated = await updateRecall(id, payload);
    setRecalls((prev) => prev.map((r) => (r.id === id ? updated : r)));
    return updated;
  }

  async function onDelete(id) {
    await deleteRecall(id);
    setRecalls((prev) => prev.filter((r) => r.id !== id));
  }

  async function onDeleteHighest() {
    if (recalls.length === 0) {
      throw new Error("There are no recall notices to delete.");
    }
    const highest = recalls.reduce((a, b) => (a.id > b.id ? a : b));
    await deleteHighestRecall();
    setRecalls((prev) => prev.filter((r) => r.id !== highest.id));
    return highest;
  }

  if (!auth.checked) return null;

  return (
    <div>
      <Navbar auth={auth} recallCount={recalls.length} onLogout={onLogout} />

      <main className="page">
        <Routes>
          <Route
            path="/"
            element={
              <Home
                recalls={recalls}
                loading={loading}
                auth={auth}
                onSearch={fetchRecalls}
                onReload={reload}
                onSelectRecall={setSelectedRecall}
                onDelete={onDelete}
                onDeleteHighest={onDeleteHighest}
                showToast={showToast}
              />
            }
          />
          <Route path="/login" element={<Login onLogin={onLogin} />} />
          <Route
            path="/create"
            element={
              <RequireAuth auth={auth}>
                <CreateRecord onAdd={onAdd} showToast={showToast} />
              </RequireAuth>
            }
          />
          <Route
            path="/update"
            element={
              <RequireAuth auth={auth}>
                <UpdateRecord recall={selectedRecall} onUpdate={onUpdate} showToast={showToast} />
              </RequireAuth>
            }
          />
          <Route
            path="/delete"
            element={
              <RequireAuth auth={auth}>
                <DeleteRecord recall={selectedRecall} onDelete={onDelete} showToast={showToast} />
              </RequireAuth>
            }
          />
        </Routes>
      </main>

      <Footer />
      <Toast toast={toast} />
    </div>
  );
}

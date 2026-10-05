import React, { useEffect, useRef, useState } from "react";
import { Routes, Route } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";

import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import Toast from "./components/Toast.jsx";
import Login from "./pages/Login.jsx";
import Home from "./pages/Home.jsx";
import CreateRecord from "./pages/CreateRecord.jsx";
import UpdateRecord from "./pages/UpdateRecord.jsx";
import DeleteRecord from "./pages/DeleteRecord.jsx";

import { me, logout } from "./api/recallsApi.js";
import { fetchRecalls } from "./store/recallsSlice.js";

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
  const dispatch = useDispatch();
  const recallCount = useSelector((state) => state.recalls.items.length);
  const [auth, setAuth] = useState({ loggedIn: false, user: null, checked: false });
  const [toast, setToast] = useState(null);
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

  useEffect(() => {
    if (auth.loggedIn) {
      dispatch(fetchRecalls());
    }
  }, [auth.loggedIn, dispatch]);

  function onLogin(user) {
    setAuth({ loggedIn: true, user, checked: true });
  }

  async function onLogout() {
    await logout();
    setAuth({ loggedIn: false, user: null, checked: true });
  }

  if (!auth.checked) return null;

  return (
    <div>
      <Navbar auth={auth} recallCount={recallCount} onLogout={onLogout} />

      <main className="page">
        <Routes>
          <Route path="/" element={<Home auth={auth} />} />
          <Route path="/login" element={<Login onLogin={onLogin} />} />
          <Route
            path="/create"
            element={
              <RequireAuth auth={auth}>
                <CreateRecord showToast={showToast} />
              </RequireAuth>
            }
          />
          <Route
            path="/update"
            element={
              <RequireAuth auth={auth}>
                <UpdateRecord showToast={showToast} />
              </RequireAuth>
            }
          />
          <Route
            path="/delete"
            element={
              <RequireAuth auth={auth}>
                <DeleteRecord showToast={showToast} />
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

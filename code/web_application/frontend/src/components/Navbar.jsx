import React from "react";
import { NavLink } from "react-router-dom";

export default function Navbar({ auth, recallCount, onLogout }) {
  return (
    <header className="site-header">
      <div className="header-account">
        {auth.loggedIn ? (
          <>
            <span>Signed in as {auth.user?.name}</span>
            <button className="link-btn" onClick={onLogout}>Logout</button>
          </>
        ) : (
          <NavLink to="/login" className="link-btn">Login</NavLink>
        )}
      </div>

      <div className="brand">
        <div className="brand-text">
          <span className="brand-title">Grocery Recall Notices</span>
          <span className="brand-sub">DATA-260 HW4 &middot; port 8191</span>
        </div>
      </div>

      <nav className="tabs" aria-label="Main">
        <NavLink to="/" end className={({ isActive }) => `tab${isActive ? " is-active" : ""}`}>
          Home <span className="pill">{recallCount}</span>
        </NavLink>
        <NavLink to="/create" className={({ isActive }) => `tab${isActive ? " is-active" : ""}`}>
          Add Notice
        </NavLink>
      </nav>
    </header>
  );
}

import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { chipClass } from "../utils.js";

export default function Home({ recalls, loading, auth, onSearch, onReload, onSelectRecall, onDelete, onDeleteHighest, showToast }) {
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [error, setError] = useState("");

  if (!auth.loggedIn) {
    return (
      <>
        <div className="view-head">
          <h2>Grocery Supply and Recall Notices</h2>
        </div>
        <div className="notice">Login required</div>
      </>
    );
  }

  const list = searchResults !== null ? searchResults : recalls;
  const isLoading = searchResults !== null ? searchLoading : loading;

  async function handleSearch() {
    const term = searchInput.trim();
    if (!term) {
      handleShowAll();
      return;
    }
    setError("");
    setSearchLoading(true);
    try {
      setSearchTerm(term);
      setSearchResults(await onSearch(term));
    } catch (err) {
      setError(err.message);
    } finally {
      setSearchLoading(false);
    }
  }

  function handleShowAll() {
    setSearchInput("");
    setSearchTerm("");
    setSearchResults(null);
    onReload();
  }

  async function handleDeleteHighest() {
    const highest = recalls.reduce((a, b) => (a.id > b.id ? a : b), recalls[0]);
    if (!highest || !confirm(`Delete the notice with the highest ID?\n\nID ${highest.id} - ${highest.product_name}`)) {
      return;
    }
    try {
      const deleted = await onDeleteHighest();
      showToast(`Deleted record ID ${deleted.id}, the highest ID.`);
    } catch (err) {
      showToast("Could not delete: " + err.message, false);
    }
  }

  function goToUpdate(recall) {
    onSelectRecall(recall);
    navigate("/update");
  }

  function goToDelete(recall) {
    onSelectRecall(recall);
    navigate("/delete");
  }

  const highestPreview = recalls.length === 0
    ? "nothing left to delete"
    : (() => {
        const highest = recalls.reduce((a, b) => (a.id > b.id ? a : b));
        return `ID ${highest.id} - ${highest.product_name}`;
      })();

  return (
    <>
      <div className="view-head">
        <h2>All recall notices</h2>
        <p className="view-sub">Every notice reported so far. Search by product name or supplier.</p>
      </div>

      <div className="search-bar">
        <div className="search-field">
          <input
            type="text"
            placeholder="Search product name or supplier…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <button type="button" className="btn btn-primary" onClick={handleSearch}>Search</button>
        <button type="button" className="btn btn-ghost" onClick={handleShowAll}>Show All</button>
      </div>

      {searchTerm && searchResults !== null && (
        <p className="search-note">
          Showing {searchResults.length} result{searchResults.length === 1 ? "" : "s"} for "{searchTerm}".
        </p>
      )}

      {isLoading ? (
        <>
          <div className="skeleton-row" />
          <div className="skeleton-row" />
          <div className="skeleton-row" />
          <p className="state-caption"><span className="spinner" aria-hidden="true" /> Loading recall notices…</p>
        </>
      ) : error ? (
        <div className="state state-error" role="alert">
          <h3>Could not load the notices</h3>
          <p>{error}</p>
          <button type="button" className="btn btn-primary" onClick={handleShowAll}>Try again</button>
        </div>
      ) : list.length === 0 ? (
        <div className="state state-empty">
          <h3>{searchTerm ? "No matching notices" : "No recall notices yet"}</h3>
          <p>
            {searchTerm
              ? `Nothing matches "${searchTerm}". Try a different product name or supplier, or press Show All.`
              : "Nothing has been reported. Use Add Notice to report the first one."}
          </p>
          <Link to="/create" className="btn btn-primary">Report a recall</Link>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="recall-table">
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">Product Name</th>
                <th scope="col">Supplier / Brand</th>
                <th scope="col">Reason Type</th>
                <th scope="col"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.id}>
                  <td data-label="ID" className="id-cell">{r.id}</td>
                  <td data-label="Product" className="product-cell">{r.product_name}</td>
                  <td data-label="Supplier">{r.supplier}</td>
                  <td data-label="Reason">
                    {r.recall_type ? (
                      <span className={`chip ${chipClass(r.recall_type)}`}>{r.recall_type}</span>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td data-label="" className="actions-cell">
                    <div className="row-actions">
                      <button type="button" className="icon-btn" onClick={() => goToUpdate(r)}>Update</button>
                      <button type="button" className="icon-btn danger" onClick={() => goToDelete(r)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card card-danger" style={{ marginTop: 20 }}>
        <h3 className="card-title">Delete highest ID</h3>
        <p className="card-sub">Removes whichever notice currently has the largest ID.</p>
        <div className="danger-preview">About to delete: <strong>{highestPreview}</strong></div>
        <button type="button" className="btn btn-danger btn-block" onClick={handleDeleteHighest}>
          Delete Highest ID
        </button>
      </div>
    </>
  );
}

import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";

import { chipClass } from "../utils.js";
import { fetchRecalls } from "../store/recallsSlice.js";

export default function Home({ auth }) {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const recalls = useSelector((state) => state.recalls.items);
  const loading = useSelector((state) => state.recalls.status === "loading");
  const storeError = useSelector((state) => state.recalls.error);

  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

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

  const term = searchTerm.trim().toLowerCase();
  const list = term
    ? recalls.filter(
        (r) =>
          r.product_name.toLowerCase().includes(term) ||
          (r.recall_code || "").toLowerCase().includes(term) ||
          String(r.supplier_id).includes(term)
      )
    : recalls;

  function handleSearch() {
    setSearchTerm(searchInput.trim());
  }

  function handleShowAll() {
    setSearchInput("");
    setSearchTerm("");
    dispatch(fetchRecalls());
  }

  function goToUpdate(recall) {
    navigate(`/update?id=${recall.id}`);
  }

  function goToDelete(recall) {
    navigate(`/delete?id=${recall.id}`);
  }

  return (
    <>
      <div className="view-head">
        <h2>All recall notices</h2>
        <p className="view-sub">
          List is driven by Redux. Search by product name, recall code, or supplier id.
        </p>
      </div>

      <div className="search-bar">
        <div className="search-field">
          <input
            type="text"
            placeholder="Search product, recall code, or supplier id…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <button type="button" className="btn btn-primary" onClick={handleSearch}>Search</button>
        <button type="button" className="btn btn-ghost" onClick={handleShowAll}>Show All</button>
      </div>

      {term && (
        <p className="search-note">
          Showing {list.length} result{list.length === 1 ? "" : "s"} for "{searchTerm}".
        </p>
      )}

      {loading ? (
        <>
          <div className="skeleton-row" />
          <div className="skeleton-row" />
          <div className="skeleton-row" />
          <p className="state-caption"><span className="spinner" aria-hidden="true" /> Loading recall notices…</p>
        </>
      ) : storeError && recalls.length === 0 ? (
        <div className="state state-error" role="alert">
          <h3>Could not load the notices</h3>
          <p>{storeError}</p>
          <button type="button" className="btn btn-primary" onClick={handleShowAll}>Try again</button>
        </div>
      ) : list.length === 0 ? (
        <div className="state state-empty">
          <h3>{term ? "No matching notices" : "No recall notices yet"}</h3>
          <p>
            {term
              ? `Nothing matches "${searchTerm}". Try a different term, or press Show All.`
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
                <th scope="col">Recall code</th>
                <th scope="col">Units</th>
                <th scope="col">Supplier ID</th>
                <th scope="col">Reason Type</th>
                <th scope="col"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.id}>
                  <td data-label="ID" className="id-cell">{r.id}</td>
                  <td data-label="Product" className="product-cell">{r.product_name}</td>
                  <td data-label="Code">{r.recall_code}</td>
                  <td data-label="Units">{r.affected_units}</td>
                  <td data-label="Supplier">{r.supplier_id}</td>
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
    </>
  );
}

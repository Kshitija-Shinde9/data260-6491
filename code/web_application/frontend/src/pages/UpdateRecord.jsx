import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";

import { updateRecall } from "../store/recallsSlice.js";

export default function UpdateRecord({ showToast }) {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const items = useSelector((state) => state.recalls.items);

  const initialId = searchParams.get("id") || "";
  const [idInput, setIdInput] = useState(initialId);
  const selected = items.find((r) => String(r.id) === String(idInput));

  const [productName, setProductName] = useState(selected ? selected.product_name : "");
  const [affectedUnits, setAffectedUnits] = useState(selected ? selected.affected_units : 0);
  const [supplierId, setSupplierId] = useState(selected ? selected.supplier_id : "");
  const [loadedId, setLoadedId] = useState(selected ? String(selected.id) : "");
  const [submitting, setSubmitting] = useState(false);

  function loadRecord() {
    const found = items.find((r) => String(r.id) === String(idInput));
    if (!found) {
      showToast("No recall with that ID in the Redux store. Open Home first or check the ID.", false);
      return;
    }
    setProductName(found.product_name);
    setAffectedUnits(found.affected_units);
    setSupplierId(found.supplier_id);
    setLoadedId(String(found.id));
    showToast(`Loaded record ID ${found.id}.`);
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (!loadedId) {
      showToast("Enter a Record ID and click Load Record first.", false);
      return;
    }
    if (!productName.trim()) {
      showToast("Product name is required.", false);
      return;
    }

    setSubmitting(true);
    try {
      const result = await dispatch(
        updateRecall({
          id: Number(loadedId),
          payload: {
            product_name: productName.trim(),
            affected_units: Number(affectedUnits) || 0,
            supplier_id: Number(supplierId),
          },
        })
      );
      if (updateRecall.fulfilled.match(result)) {
        showToast(`Record ID ${result.payload.id} updated.`);
        navigate("/");
      } else {
        showToast("Could not update the record: " + result.payload, false);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="view-head">
        <h2>Manage notices</h2>
        <p className="view-sub">Select a record by ID, then dispatch the Redux updateRecall thunk.</p>
      </div>

      <div className="card">
        <h3 className="card-title">Update a record</h3>
        <p className="card-sub">Choose the ID from Home, or type it and click Load.</p>

        <label htmlFor="updateId">Record ID</label>
        <input
          id="updateId"
          type="number"
          min="1"
          value={idInput}
          onChange={(e) => setIdInput(e.target.value)}
        />
        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginTop: 8, marginBottom: 12 }}
          onClick={loadRecord}
        >
          Load Record
        </button>

        {loadedId && (
          <p className="field-hint">
            Currently editing: <strong>ID {loadedId}</strong>
          </p>
        )}

        <form onSubmit={handleSubmit}>
          <label htmlFor="updateProductName">Product Name</label>
          <input
            id="updateProductName"
            type="text"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            autoFocus
          />

          <label htmlFor="updateUnits">Affected units</label>
          <input
            id="updateUnits"
            type="number"
            min="0"
            value={affectedUnits}
            onChange={(e) => setAffectedUnits(e.target.value)}
          />

          <label htmlFor="updateSupplierId">Supplier ID</label>
          <input
            id="updateSupplierId"
            type="number"
            min="1"
            value={supplierId}
            onChange={(e) => setSupplierId(e.target.value)}
          />

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? "Updating..." : "Update Record"}
          </button>
        </form>
      </div>
    </>
  );
}

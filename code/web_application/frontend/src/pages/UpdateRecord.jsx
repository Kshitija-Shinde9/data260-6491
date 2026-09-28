import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function UpdateRecord({ recall, onUpdate, showToast }) {
  const navigate = useNavigate();
  const [productName, setProductName] = useState(recall ? recall.product_name : "");
  const [supplier, setSupplier] = useState(recall ? recall.supplier : "");
  const [submitting, setSubmitting] = useState(false);

  if (!recall) {
    return (
      <div className="card">
        <div className="view-head">
          <h2>No Record Selected</h2>
        </div>
        <div className="notice">Go back to Home and click Update on a record.</div>
      </div>
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (!productName.trim() || !supplier.trim()) {
      showToast("Please enter both a new product name and a new supplier / brand.", false);
      return;
    }

    setSubmitting(true);
    try {
      const updated = await onUpdate(recall.id, {
        product_name: productName.trim(),
        supplier: supplier.trim(),
      });
      showToast(`Record ID ${updated.id} updated.`);
      navigate("/");
    } catch (err) {
      showToast("Could not update the record: " + err.message, false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="view-head">
        <h2>Manage notices</h2>
        <p className="view-sub">Update an existing record.</p>
      </div>

      <div className="card">
        <h3 className="card-title">Update a record</h3>
        <p className="card-sub">Changes the primary and secondary fields of one record.</p>

        <label htmlFor="updateId">Record ID</label>
        <input id="updateId" type="number" value={recall.id} disabled />
        <p className="field-hint">
          Currently editing: <strong>{recall.product_name}</strong>
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="updateProductName">New Product Name</label>
          <input
            id="updateProductName"
            type="text"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            autoFocus
          />

          <label htmlFor="updateSupplierName">New Supplier / Brand</label>
          <input
            id="updateSupplierName"
            type="text"
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
          />

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? "Updating..." : "Update Record"}
          </button>
        </form>
      </div>
    </>
  );
}

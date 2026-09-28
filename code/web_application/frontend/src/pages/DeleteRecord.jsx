import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function DeleteRecord({ recall, onDelete, showToast }) {
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);

  if (!recall) {
    return (
      <div className="card">
        <div className="view-head">
          <h2>No Record Selected</h2>
        </div>
        <div className="notice">Go back to Home and click Delete on a record.</div>
      </div>
    );
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await onDelete(recall.id);
      showToast(`Deleted record ID ${recall.id}.`);
      navigate("/");
    } catch (err) {
      showToast("Could not delete: " + err.message, false);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <div className="view-head">
        <h2>Manage notices</h2>
        <p className="view-sub">Remove this record.</p>
      </div>

      <div className="card card-danger">
        <h3 className="card-title">Delete recall #{recall.id}</h3>
        <p className="card-sub">This cannot be undone.</p>

        <div className="danger-preview">
          About to delete: <strong>ID {recall.id} - {recall.product_name}</strong> ({recall.supplier})
        </div>

        <button type="button" className="btn btn-danger btn-block" onClick={handleDelete} disabled={deleting}>
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </>
  );
}

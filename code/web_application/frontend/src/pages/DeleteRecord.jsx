import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";

import { deleteRecall } from "../store/recallsSlice.js";

export default function DeleteRecord({ showToast }) {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const items = useSelector((state) => state.recalls.items);
  const [deleting, setDeleting] = useState(false);

  const recallId = searchParams.get("id");
  const recall = items.find((r) => String(r.id) === String(recallId));

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
      const result = await dispatch(deleteRecall(recall.id));
      if (deleteRecall.fulfilled.match(result)) {
        showToast(`Deleted record ID ${recall.id}.`);
        navigate("/");
      } else {
        showToast("Could not delete: " + result.payload, false);
      }
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
        <p className="card-sub">This cannot be undone. Confirming dispatches the Redux deleteRecall thunk.</p>

        <div className="danger-preview">
          About to delete:{" "}
          <strong>
            ID {recall.id} - {recall.product_name}
          </strong>{" "}
          ({recall.recall_code}, supplier {recall.supplier_id})
        </div>

        <button
          type="button"
          className="btn btn-danger btn-block"
          onClick={handleDelete}
          disabled={deleting}
        >
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </>
  );
}

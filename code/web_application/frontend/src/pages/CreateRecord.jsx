import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDispatch } from "react-redux";

import { createRecall } from "../store/recallsSlice.js";

const RECALL_TYPES = [
  "Packaging / Seal Failure",
  "Contamination",
  "Undeclared Allergen",
  "Spoiled or Quality Issue",
];

export default function CreateRecord({ showToast }) {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [productName, setProductName] = useState("");
  const [recallCode, setRecallCode] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [affectedUnits, setAffectedUnits] = useState(0);
  const [email, setEmail] = useState("");
  const [description, setDescription] = useState("");
  const [recallType, setRecallType] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function validate() {
    if (!/^REC-[0-9]{4}$/i.test(recallCode.trim())) {
      return "Recall code must look like REC-0004 (REC- and four digits).";
    }
    if (!supplierId || Number(supplierId) < 1) {
      return "Supplier ID is required and must match an existing supplier.";
    }
    if (description.trim().length <= 25) {
      return "Please write a bit more in the recall reason, it needs to be more than 25 characters.";
    }
    if (!agreeTerms) {
      return "You need to check the box agreeing to the terms and conditions before submitting.";
    }
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();

    const problem = validate();
    if (problem) {
      showToast(problem, false);
      return;
    }

    setSubmitting(true);
    try {
      const result = await dispatch(
        createRecall({
          product_name: productName.trim(),
          recall_code: recallCode.trim().toUpperCase(),
          supplier_id: Number(supplierId),
          affected_units: Number(affectedUnits) || 0,
          email: email.trim(),
          description: description.trim(),
          recall_type: recallType,
        })
      );
      if (createRecall.fulfilled.match(result)) {
        showToast(`Added "${result.payload.product_name}" as record ID ${result.payload.id}.`);
        navigate("/");
      } else {
        showToast("Could not add the recall notice: " + result.payload, false);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="view-head">
        <h2>Report a new recall</h2>
        <p className="view-sub">
          Dispatches the Redux createRecall thunk. Use a real supplier_id from GET /api/suppliers.
        </p>
      </div>

      <div className="card">
        <form onSubmit={handleSubmit}>
          <label htmlFor="productName">Product Name <span className="req">*</span></label>
          <input
            id="productName"
            type="text"
            placeholder="e.g. Trader Joe's Organic Frozen Blueberries, 16oz"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            required
            autoFocus
          />
          <p className="field-hint">Primary text field.</p>

          <label htmlFor="recallCode">Recall code <span className="req">*</span></label>
          <input
            id="recallCode"
            type="text"
            placeholder="REC-0004"
            value={recallCode}
            onChange={(e) => setRecallCode(e.target.value)}
            required
          />
          <p className="field-hint">Unique field. Format REC- then four digits.</p>

          <label htmlFor="supplierId">Supplier ID <span className="req">*</span></label>
          <input
            id="supplierId"
            type="number"
            min="1"
            placeholder="1"
            value={supplierId}
            onChange={(e) => setSupplierId(e.target.value)}
            required
          />
          <p className="field-hint">Foreign key to suppliers (seeded ids are usually 1, 2, 3).</p>

          <label htmlFor="affectedUnits">Affected units</label>
          <input
            id="affectedUnits"
            type="number"
            min="0"
            value={affectedUnits}
            onChange={(e) => setAffectedUnits(e.target.value)}
          />
          <p className="field-hint">Numeric field. Defaults to 0.</p>

          <label htmlFor="submitterEmail">Your Email <span className="req">*</span></label>
          <input
            id="submitterEmail"
            type="email"
            placeholder="your email so we can follow up"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <label htmlFor="recallDescription">Recall Reason / Description <span className="req">*</span></label>
          <textarea
            id="recallDescription"
            placeholder="what happened, when you noticed it, any batch/lot info"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
          />
          <p className="field-hint">{description.trim().length} characters &middot; needs more than 25</p>

          <label htmlFor="recallType">Recall Reason Type <span className="req">*</span></label>
          <select id="recallType" value={recallType} onChange={(e) => setRecallType(e.target.value)} required>
            <option value="" disabled>Choose a reason</option>
            {RECALL_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          <div className="checkbox-row">
            <input
              id="agreeTerms"
              type="checkbox"
              checked={agreeTerms}
              onChange={(e) => setAgreeTerms(e.target.checked)}
            />
            <label htmlFor="agreeTerms">I agree to the terms and conditions.</label>
          </div>

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? "Submitting..." : "Report This Recall"}
          </button>
        </form>
      </div>
    </>
  );
}

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

const RECALL_TYPES = [
  "Packaging / Seal Failure",
  "Contamination",
  "Undeclared Allergen",
  "Spoiled or Quality Issue",
];

export default function CreateRecord({ onAdd, showToast }) {
  const [productName, setProductName] = useState("");
  const [supplier, setSupplier] = useState("");
  const [email, setEmail] = useState("");
  const [description, setDescription] = useState("");
  const [recallType, setRecallType] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  function validate() {
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
      const created = await onAdd({
        product_name: productName.trim(),
        supplier: supplier.trim(),
        email: email.trim(),
        description: description.trim(),
        recall_type: recallType,
      });
      showToast(`Added "${created.product_name}" as record ID ${created.id}.`);
      navigate("/");
    } catch (err) {
      showToast("Could not add the recall notice: " + err.message, false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="view-head">
        <h2>Report a new recall</h2>
        <p className="view-sub">Product name and supplier are the two fields the record is stored under.</p>
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
          <p className="field-hint">This is the primary field the record is listed under.</p>

          <label htmlFor="supplierName">Supplier / Brand <span className="req">*</span></label>
          <input
            id="supplierName"
            type="text"
            placeholder="who made or supplied it"
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
            required
          />
          <p className="field-hint">This is the secondary field. Search matches on this too.</p>

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

import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import FreezerForm from '../components/forms/FreezerForm';
import { createFreezerFn } from '../api';

// ── AddFreezerPage ────────────────────────────────────────────────────────────

function AddFreezerPage() {
  const navigate = useNavigate();

  const [submitting, setSubmitting] = useState(false);
  const [success,    setSuccess]    = useState(null);   // created freezer response
  const [error,      setError]      = useState(null);

  async function handleSubmit(payload) {
    setSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await createFreezerFn(payload);
      setSuccess(result);
    } catch (e) {
      // Backend may return a detail string or an object
      const detail = e.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        // FastAPI validation error array
        setError(detail.map(d => d.msg).join(' · '));
      } else {
        setError('Failed to create freezer. Check that the backend is running.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleAddAnother() {
    setSuccess(null);
    setError(null);
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="admin-page">
      <div className="page-topbar">
        <Link to="/admin" className="topbar-back">← Admin</Link>
        <h2 className="page-title">Add Freezer</h2>
      </div>

      <div className="add-freezer-layout">
        <div className="add-freezer-card">

          {/* Success state */}
          {success && (
            <div className="freezer-success-banner">
              <div className="freezer-success-header">
                <span className="freezer-success-icon">✓</span>
                Freezer created successfully
              </div>
              <div className="freezer-success-details">
                <div className="freezer-detail-row">
                  <span className="freezer-detail-label">Asset ID</span>
                  <span className="freezer-detail-value font-mono">{success.asset_id}</span>
                </div>
                <div className="freezer-detail-row">
                  <span className="freezer-detail-label">Temperature</span>
                  <span className="freezer-detail-value">{success.temperature}°C</span>
                </div>
                <div className="freezer-detail-row">
                  <span className="freezer-detail-label">Total drawers</span>
                  <span className="freezer-detail-value font-mono">{success.total_drawers?.toLocaleString()}</span>
                </div>
                <div className="freezer-detail-row">
                  <span className="freezer-detail-label">Structure</span>
                  <span className="freezer-detail-value">
                    {success.num_of_layers}L × {success.num_of_rack_per_layer}R × {success.num_of_drawer_per_rack}D
                  </span>
                </div>
                <div className="freezer-detail-row">
                  <span className="freezer-detail-label">Study capacity</span>
                  <span className="freezer-detail-value">{success.study_sample_capacity} per drawer</span>
                </div>
                <div className="freezer-detail-row">
                  <span className="freezer-detail-label">STD/QC capacity</span>
                  <span className="freezer-detail-value">{success.stdqc_capacity} per drawer</span>
                </div>
              </div>
              <div className="freezer-success-actions">
                <button className="btn-action btn-action--primary" onClick={handleAddAnother}>
                  + Add Another Freezer
                </button>
                <Link to="/admin" className="btn-action btn-action--ghost" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                  ← Back to Admin
                </Link>
              </div>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="freezer-error-banner">
              <strong>Error:</strong> {error}
            </div>
          )}

          {/* Form — hidden after success */}
          {!success && (
            <>
              <div className="add-freezer-intro">
                Fill in the freezer parameters below. All fields marked as required
                must be completed before submission. The system will automatically
                generate the full drawer structure from the dimensions you provide.
              </div>
              <FreezerForm
                onSubmit={handleSubmit}
                submitting={submitting}
                disabled={false}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── AdminPage ─────────────────────────────────────────────────────────────────
// Simple landing page for admin functions.
// Add more links here as new admin features are built.

export function AdminPage() {
  return (
    <div className="admin-page">
      <div className="page-topbar">
        <Link to="/" className="topbar-back">← Home</Link>
        <h2 className="page-title">Admin</h2>
      </div>

      <div className="admin-landing">
        <div className="admin-landing-title">Administration</div>
        <div className="admin-menu">
          <Link to="/admin/add-freezer" className="admin-menu-item">
            <span className="admin-menu-icon">❄</span>
            <span className="admin-menu-content">
              <span className="admin-menu-label">Add Freezer</span>
              <span className="admin-menu-desc">Register a new freezer and generate its drawer structure</span>
            </span>
            <span className="admin-menu-arrow">→</span>
          </Link>

          {/* Placeholder slots for future admin functions */}
          <div className="admin-menu-item admin-menu-item--disabled">
            <span className="admin-menu-icon">⊟</span>
            <span className="admin-menu-content">
              <span className="admin-menu-label">Reserve Drawers</span>
              <span className="admin-menu-desc">Coming soon</span>
            </span>
          </div>

          <div className="admin-menu-item admin-menu-item--disabled">
            <span className="admin-menu-icon">◈</span>
            <span className="admin-menu-content">
              <span className="admin-menu-label">View All Freezers</span>
              <span className="admin-menu-desc">Coming soon</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AddFreezerPage;

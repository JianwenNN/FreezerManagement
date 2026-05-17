import React from 'react';

/**
 * AllocationPanel — displays the auto-allocation suggestion summary.
 *
 * Props:
 *  allocations  — array from allocate-proximity API
 *  onCommit     — async callback to confirm the allocation
 *  onCancel     — callback to clear the overlay
 *  committing   — boolean loading state
 *  error        — error string or null
 */
function AllocationPanel({ allocations, onCommit, onCancel, committing, error }) {
  const totalAllocated = allocations.reduce((s, a) => s + a.container_count, 0);
  const isPartial = allocations.some(a => a.partial);

  // Compute expiry from first reservation
  const expiresAt = allocations[0]?.expires_at
    ? new Date(allocations[0].expires_at).toLocaleTimeString()
    : null;

  return (
    <div className="allocation-panel">
      <div className="panel-header">
        <span className="panel-title">Allocation Suggestion</span>
        <button className="btn-ghost-sm" onClick={onCancel}>✕ Cancel</button>
      </div>

      {isPartial && (
        <div className="panel-warning">
          ⚠ Partial allocation — freezer could not fit all containers.
        </div>
      )}

      <div className="panel-summary">
        <span className="summary-stat">
          <span className="stat-label">Drawers used</span>
          <span className="stat-value">{allocations.length}</span>
        </span>
        <span className="summary-stat">
          <span className="stat-label">Containers placed</span>
          <span className="stat-value">{totalAllocated}</span>
        </span>
        {expiresAt && (
          <span className="summary-stat">
            <span className="stat-label">Reservation expires</span>
            <span className="stat-value">{expiresAt}</span>
          </span>
        )}
      </div>

      <div className="allocation-rows">
        {allocations.map((a, i) => (
          <div key={i} className="allocation-row">
            <span className="alloc-coord font-mono">{a.drawer_coordinate}</span>
            <span className="alloc-count">+{a.container_count}</span>
          </div>
        ))}
      </div>

      {error && <div className="panel-error">{error}</div>}

      <button
        className="btn-commit"
        onClick={onCommit}
        disabled={committing}
      >
        {committing ? 'Committing…' : 'Commit Allocation'}
      </button>
    </div>
  );
}

export default AllocationPanel;

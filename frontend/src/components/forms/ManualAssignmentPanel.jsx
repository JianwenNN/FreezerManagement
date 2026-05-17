import React from 'react';

/**
 * ManualAssignmentPanel
 *
 * Props:
 *  drawerGrid      — full grid (to read manualSelected drawers)
 *  totalRequired   — total containers that need to be assigned
 *  sampleType      — 'study_sample_container' | 'stdqc_container'
 *  onConfirm       — async callback to submit manual assignment
 *  onCancel        — callback to exit manual mode
 *  confirming      — boolean loading state
 *  error           — error string or null
 */
function ManualAssignmentPanel({
  drawerGrid, totalRequired, sampleType,
  onConfirm, onCancel, confirming, error,
}) {
  // Flatten grid to get selected drawers
  const selected = drawerGrid.flatMap(layer =>
    layer.racks.flatMap(rack =>
      rack.drawers.filter(d => d.manualSelected)
    )
  );

  const totalAssigned = selected.reduce((s, d) => s + (d.manualCount || 0), 0);
  const isValid       = totalAssigned === totalRequired && selected.length > 0;
  const remaining     = totalRequired - totalAssigned;

  return (
    <div className="allocation-panel">
      <div className="panel-header">
        <span className="panel-title">Manual Override</span>
        <button className="btn-ghost-sm" onClick={onCancel}>✕ Cancel</button>
      </div>

      <div className="manual-instruction">
        Click drawer cells in the freezer grid to select them,
        then enter container counts in each selected drawer.
      </div>

      <div className="panel-summary">
        <span className="summary-stat">
          <span className="stat-label">Drawers selected</span>
          <span className="stat-value">{selected.length}</span>
        </span>
        <span className="summary-stat">
          <span className="stat-label">Total assigned</span>
          <span className={`stat-value ${isValid ? 'stat-ok' : 'stat-warn'}`}>
            {totalAssigned} / {totalRequired}
          </span>
        </span>
      </div>

      {selected.length > 0 && (
        <div className="allocation-rows">
          {selected.map(d => (
            <div key={d.coord} className="allocation-row">
              <span className="alloc-coord font-mono">{d.coord}</span>
              <span className={`alloc-count ${(d.manualCount || 0) > 0 ? 'alloc-count-set' : 'alloc-count-empty'}`}>
                {(d.manualCount || 0) > 0 ? `+${d.manualCount}` : 'no count'}
              </span>
            </div>
          ))}
        </div>
      )}

      {remaining !== 0 && selected.length > 0 && (
        <div className="panel-warning">
          {remaining > 0
            ? `⚠ ${remaining} container${remaining !== 1 ? 's' : ''} still unassigned`
            : `⚠ Over-assigned by ${Math.abs(remaining)}`}
        </div>
      )}

      {error && <div className="panel-error">{error}</div>}

      <button
        className="btn-commit"
        onClick={onConfirm}
        disabled={!isValid || confirming}
      >
        {confirming ? 'Confirming…' : 'Confirm Manual Assignment'}
      </button>
    </div>
  );
}

export default ManualAssignmentPanel;

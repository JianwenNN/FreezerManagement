import React from 'react';

/**
 * RetrievalSummaryPanel
 *
 * Shows lookup results and drives the two-step retrieval flow.
 *
 * Props:
 *  retrievalType  — 'study_sample' | 'stdqc'
 *  lookupResult   — raw backend preview response, or null if not yet looked up
 *  lookupError    — error string from lookup call, or null
 *  retrieveResult — raw backend confirm response, or null if not yet retrieved
 *  retrieveError  — error string from retrieve call, or null
 *  onLookup       — async callback to trigger lookup
 *  onRetrieve     — async callback to trigger retrieval confirmation
 *  onClear        — callback to reset all state
 *  looking        — boolean — lookup in progress
 *  retrieving     — boolean — retrieval in progress
 *  canLookup      — boolean — form data is valid enough to lookup
 */
function RetrievalSummaryPanel({
  retrievalType,
  lookupResult, lookupError,
  retrieveResult, retrieveError,
  onLookup, onRetrieve, onClear,
  looking, retrieving,
  canLookup,
}) {
  const hasLookup    = !!lookupResult;
  const hasRetrieved = !!retrieveResult;

  return (
    <div className="retrieval-panel">

      {/* ── Action buttons ─────────────────────────────────────────────────── */}
      <div className="retrieval-actions">
        <button
          className="btn-action btn-action--primary"
          onClick={onLookup}
          disabled={!canLookup || looking || retrieving || hasRetrieved}
        >
          {looking ? '⌕ Searching…' : '⌕ Lookup'}
        </button>

        <button
          className="btn-action btn-action--danger"
          onClick={onRetrieve}
          disabled={!hasLookup || retrieving || hasRetrieved}
        >
          {retrieving ? 'Retrieving…' : '⊖ Retrieve'}
        </button>

        {(hasLookup || lookupError || hasRetrieved) && (
          <button className="btn-action btn-action--ghost" onClick={onClear}>
            ↺ Clear
          </button>
        )}
      </div>

      {/* ── Errors ─────────────────────────────────────────────────────────── */}
      {lookupError   && <div className="panel-error mt-2">{lookupError}</div>}
      {retrieveError && <div className="panel-error mt-2">{retrieveError}</div>}

      {/* ── Retrieval success ──────────────────────────────────────────────── */}
      {hasRetrieved && (
        <div className="retrieval-success">
          <span className="success-icon">✓</span>
          {retrievalType === 'study_sample'
            ? `${retrieveResult.total_removed} container${retrieveResult.total_removed !== 1 ? 's' : ''} removed successfully.`
            : `Batch "${retrieveResult.barcode_prefix}" removed — ${retrieveResult.total_removed} container${retrieveResult.total_removed !== 1 ? 's' : ''}.`
          }
          {retrieveResult.not_found?.length > 0 && (
            <div className="retrieval-not-found">
              {retrieveResult.not_found.length} barcode{retrieveResult.not_found.length !== 1 ? 's' : ''} not found (already removed?):
              {' '}{retrieveResult.not_found.join(', ')}
            </div>
          )}
        </div>
      )}

      {/* ── Lookup results ─────────────────────────────────────────────────── */}
      {hasLookup && !hasRetrieved && (
        retrievalType === 'study_sample'
          ? <StudySampleLookupSummary result={lookupResult} />
          : <STDQCLookupSummary result={lookupResult} />
      )}

    </div>
  );
}

// ── Study sample lookup summary ───────────────────────────────────────────────

function StudySampleLookupSummary({ result }) {
  const { found, not_found, total_found } = result;

  // Group found containers by drawer coordinate
  const byDrawer = found.reduce((acc, c) => {
    const coord = c.location.drawer_coordinate;
    if (!acc[coord]) acc[coord] = [];
    acc[coord].push(c);
    return acc;
  }, {});

  return (
    <div className="lookup-summary">
      <div className="summary-header">
        <span className="summary-title">Lookup Result</span>
        <span className="summary-count-badge">
          {total_found} found
          {not_found.length > 0 && ` · ${not_found.length} not found`}
        </span>
      </div>

      {/* Not found warning */}
      {not_found.length > 0 && (
        <div className="panel-warning">
          ⚠ Not found: {not_found.join(', ')}
        </div>
      )}

      {/* Per-drawer breakdown */}
      <div className="summary-drawer-list">
        {Object.entries(byDrawer).map(([coord, containers]) => (
          <div key={coord} className="summary-drawer-row">
            <div className="summary-drawer-header">
              <span className="font-mono summary-coord">{coord}</span>
              <span className="summary-drawer-count">{containers.length}</span>
            </div>
            <div className="summary-barcodes">
              {containers.map(c => (
                <span key={c.id} className="summary-barcode font-mono">
                  {c.container_barcode}
                  {c.study_name && <span className="summary-study"> {c.study_name}</span>}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {total_found > 0 && (
        <div className="retrieve-warning">
          ⚠ Clicking Retrieve will permanently remove the {total_found} found container{total_found !== 1 ? 's' : ''}.
        </div>
      )}
    </div>
  );
}

// ── STDQC lookup summary ──────────────────────────────────────────────────────

function STDQCLookupSummary({ result }) {
  const { barcode_prefix, compound_name, matrix, anticoagulant, prep_date, total_count, containers } = result;

  // Group by drawer
  const byDrawer = containers.reduce((acc, c) => {
    const coord = c.location.drawer_coordinate;
    acc[coord] = (acc[coord] || 0) + 1;
    return acc;
  }, {});

  const drawerCount   = Object.keys(byDrawer).length;
  const freezerSet    = new Set(containers.map(c => c.location.freezer_asset_id));
  const freezerList   = [...freezerSet].join(', ');

  return (
    <div className="lookup-summary">
      <div className="summary-header">
        <span className="summary-title">STD/QC Batch</span>
        <span className="summary-count-badge">{total_count} containers</span>
      </div>

      <div className="summary-meta-grid">
        <span className="summary-meta-key">Prep ID</span>    <span className="summary-meta-val font-mono">{barcode_prefix}</span>
        <span className="summary-meta-key">Compound</span>   <span className="summary-meta-val">{compound_name}</span>
        <span className="summary-meta-key">Matrix</span>     <span className="summary-meta-val">{matrix}</span>
        <span className="summary-meta-key">Anticoag</span>   <span className="summary-meta-val">{anticoagulant}</span>
        <span className="summary-meta-key">Prep Date</span>  <span className="summary-meta-val">{new Date(prep_date).toLocaleDateString(undefined, { dateStyle: 'medium' })}</span>
        <span className="summary-meta-key">Freezer(s)</span> <span className="summary-meta-val font-mono">{freezerList}</span>
        <span className="summary-meta-key">Drawers</span>    <span className="summary-meta-val">{drawerCount}</span>
      </div>

      <div className="summary-drawer-list mt-2">
        {Object.entries(byDrawer).map(([coord, count]) => (
          <div key={coord} className="summary-drawer-row">
            <div className="summary-drawer-header">
              <span className="font-mono summary-coord">{coord}</span>
              <span className="summary-drawer-count">{count}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="retrieve-warning">
        ⚠ Clicking Retrieve will permanently remove the entire batch ({total_count} containers).
      </div>
    </div>
  );
}

export default RetrievalSummaryPanel;

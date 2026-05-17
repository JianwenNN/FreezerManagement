import React, { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useFreezer, buildDrawerGrid } from '../hooks/useFreezer';
import FreezerGrid from '../components/freezer/FreezerGrid';
import { listFreezersFn, lookupStudySampleFn, lookupSTDQCFn } from '../api';

// ─────────────────────────────────────────────────────────────────────────────

function LookupPage() {
  const {
    drawerGrid, applySearchOverlay, clearOverlay,
  } = useFreezer();

  // Page state
  const [searchType,   setSearchType]   = useState('study_sample');
  const [query,        setQuery]        = useState('');
  const [searching,    setSearching]    = useState(false);
  const [searchError,  setSearchError]  = useState(null);
  const [result,       setResult]       = useState(null);   // raw API response
  const [freezerMeta,  setFreezerMeta]  = useState(null);   // { asset_id, num_of_layers, ... }
  const [grid,         setGrid]         = useState([]);     // built from freezerMeta

  // ── Helpers ────────────────────────────────────────────────────────────────

  /**
   * Given a result from the backend, extract the set of drawer coordinates
   * that contain matching containers, grouped with a count per coordinate.
   */
  function extractMatchCoords(res, type) {
    if (type === 'study_sample') {
      // Single container — one location
      return [{
        drawer_coordinate: res.location.drawer_coordinate,
        matchCount:        1,
      }];
    } else {
      // STDQC batch — may span multiple drawers
      const byCoord = {};
      for (const c of res.containers) {
        const coord = c.location.drawer_coordinate;
        byCoord[coord] = (byCoord[coord] || 0) + 1;
      }
      return Object.entries(byCoord).map(([drawer_coordinate, matchCount]) => ({
        drawer_coordinate, matchCount,
      }));
    }
  }

  /**
   * Given search results, find the freezer(s) involved,
   * fetch their metadata, build the grid, and apply the search overlay.
   */
  const loadFreezerAndOverlay = useCallback(async (res, type) => {
    const matchCoords = extractMatchCoords(res, type);

    // Determine which freezer asset_id(s) are involved
    let assetId;
    if (type === 'study_sample') {
      assetId = res.location.freezer_asset_id;
    } else {
      // For STDQC, all containers in the batch should be in the same freezer
      // (allocation is per-freezer). Use first container's freezer.
      assetId = res.containers[0]?.location.freezer_asset_id;
    }

    if (!assetId) return;

    // Fetch all freezers and find the matching one
    const freezers = await listFreezersFn();
    const freezer  = freezers.find(f => f.asset_id === assetId);
    if (!freezer) return;

    setFreezerMeta(freezer);

    // Build grid from dimension metadata
    const builtGrid = buildDrawerGrid(freezer);

    // Apply search overlay — mark matching drawers
    const enrichedGrid = builtGrid.map(layer => ({
      ...layer,
      racks: layer.racks.map(rack => ({
        ...rack,
        drawers: rack.drawers.map(drawer => {
          const hit = matchCoords.find(m => m.drawer_coordinate === drawer.coord);
          return hit
            ? { ...drawer, searchMatch: true, matchCount: hit.matchCount }
            : drawer;
        }),
      })),
    }));

    setGrid(enrichedGrid);
  }, []);

  // ── Search ─────────────────────────────────────────────────────────────────

  async function handleSearch(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    setSearching(true);
    setSearchError(null);
    setResult(null);
    setGrid([]);
    setFreezerMeta(null);

    try {
      const res = searchType === 'study_sample'
        ? await lookupStudySampleFn(q)
        : await lookupSTDQCFn(q);

      setResult(res);
      await loadFreezerAndOverlay(res, searchType);
    } catch (e) {
      if (e.response?.status === 404) {
        setSearchError(
          searchType === 'study_sample'
            ? `No container found with barcode "${q}".`
            : `No STD/QC batch found with prep ID "${q}".`
        );
      } else {
        setSearchError(e.response?.data?.detail || 'Search failed. Is the backend running?');
      }
    } finally {
      setSearching(false);
    }
  }

  function handleClear() {
    setQuery('');
    setResult(null);
    setGrid([]);
    setFreezerMeta(null);
    setSearchError(null);
  }

  function handleTypeChange(type) {
    setSearchType(type);
    handleClear();
  }

  // ── Derived ────────────────────────────────────────────────────────────────

  const hasResult = !!result;
  const placeholder = searchType === 'study_sample'
    ? 'Enter container barcode…'
    : 'Enter prep ID (e.g. Warfarin-Plasma-EDTA-20260516-B001)';

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="lookup-page">

      {/* Top bar */}
      <div className="page-topbar">
        <Link to="/" className="topbar-back">← Back</Link>
        <h2 className="page-title">Lookup Container</h2>
      </div>

      <div className="lookup-layout">

        {/* ── Search section ─────────────────────────────────────────────── */}
        <div className="lookup-search-section">

          {/* Type selector */}
          <div className="radio-group mb-3">
            <label className={`radio-option ${searchType === 'study_sample' ? 'radio-option--active' : ''}`}>
              <input type="radio" value="study_sample" checked={searchType === 'study_sample'} onChange={() => handleTypeChange('study_sample')} />
              Study Sample
            </label>
            <label className={`radio-option ${searchType === 'stdqc' ? 'radio-option--active' : ''}`}>
              <input type="radio" value="stdqc" checked={searchType === 'stdqc'} onChange={() => handleTypeChange('stdqc')} />
              STD/QC
            </label>
          </div>

          {/* Search input */}
          <form className="lookup-search-form" onSubmit={handleSearch}>
            <input
              type="text"
              className="form-control form-control-custom font-mono lookup-input"
              placeholder={placeholder}
              value={query}
              onChange={e => setQuery(e.target.value)}
              autoFocus
            />
            <button
              type="submit"
              className="btn-search"
              disabled={searching || !query.trim()}
            >
              {searching ? '…' : '⌕'}
            </button>
            {(hasResult || searchError) && (
              <button type="button" className="btn-clear" onClick={handleClear}>
                ✕
              </button>
            )}
          </form>

          {searchError && (
            <div className="field-error mt-2">{searchError}</div>
          )}
        </div>

        {/* ── Result summary card ─────────────────────────────────────────── */}
        {hasResult && (
          <div className="lookup-result-card">
            {searchType === 'study_sample' ? (
              <StudySampleResult result={result} />
            ) : (
              <STDQCResult result={result} />
            )}
          </div>
        )}

        {/* ── Freezer visualization ───────────────────────────────────────── */}
        {grid.length > 0 && freezerMeta && (
          <div className="lookup-viz-section">
            <div className="viz-header">
              <span className="viz-freezer-label">
                {freezerMeta.asset_id}
                <span className="viz-freezer-meta">
                  {freezerMeta.num_of_layers}L ×
                  {freezerMeta.num_of_rack_per_layer}R ×
                  {freezerMeta.num_of_drawer_per_rack}D ·
                  {freezerMeta.temperature}°C
                </span>
              </span>
              <span className="viz-mode-badge viz-mode-badge--lookup">
                Read-only · Search Result
              </span>
            </div>
            <FreezerGrid
              grid={grid}
              mode="view"
              onManualSelect={null}
              onSetCount={null}
            />
          </div>
        )}

        {/* Empty state */}
        {!hasResult && !searchError && grid.length === 0 && (
          <div className="lookup-empty-state">
            <div className="empty-icon">◎</div>
            <div className="empty-title">Search for a container</div>
            <div className="empty-desc">
              {searchType === 'study_sample'
                ? 'Enter a container barcode to locate it in the freezer system.'
                : 'Enter a prep ID to locate all containers in that batch.'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Result cards ──────────────────────────────────────────────────────────────

function ResultRow({ label, value, mono = false }) {
  return (
    <div className="result-row">
      <span className="result-label">{label}</span>
      <span className={`result-value${mono ? ' font-mono' : ''}`}>{value}</span>
    </div>
  );
}

function StudySampleResult({ result }) {
  const loc = result.location;
  return (
    <>
      <div className="result-card-header">
        <span className="result-card-title">Study Sample</span>
        <span className="result-match-badge">1 container</span>
      </div>
      <div className="result-rows">
        <ResultRow label="Barcode"    value={result.container_barcode} mono />
        <ResultRow label="Study"      value={result.study_name} />
        <ResultRow label="Freezer"    value={loc.freezer_asset_id} mono />
        <ResultRow label="Coordinate" value={loc.drawer_coordinate} mono />
        {result.position_in_drawer && (
          <ResultRow label="Position" value={result.position_in_drawer} mono />
        )}
        <ResultRow
          label="Added"
          value={new Date(result.date_added).toLocaleDateString(undefined, { dateStyle: 'medium' })}
        />
      </div>
    </>
  );
}

function STDQCResult({ result }) {
  // Group containers by freezer and coordinate for the summary
  const byFreezer = {};
  for (const c of result.containers) {
    const fa = c.location.freezer_asset_id;
    if (!byFreezer[fa]) byFreezer[fa] = new Set();
    byFreezer[fa].add(c.location.drawer_coordinate);
  }

  const freezerCount = Object.keys(byFreezer).length;
  const drawerCount  = new Set(result.containers.map(c => c.location.drawer_coordinate)).size;

  return (
    <>
      <div className="result-card-header">
        <span className="result-card-title">STD/QC Batch</span>
        <span className="result-match-badge">{result.total_count} containers</span>
      </div>
      <div className="result-rows">
        <ResultRow label="Prep ID"      value={result.barcode_prefix} mono />
        <ResultRow label="Compound"     value={result.compound_name} />
        <ResultRow label="Matrix"       value={result.matrix} />
        <ResultRow label="Anticoag"     value={result.anticoagulant} />
        <ResultRow
          label="Prep Date"
          value={new Date(result.prep_date).toLocaleDateString(undefined, { dateStyle: 'medium' })}
        />
        <ResultRow label="Freezers"     value={Object.keys(byFreezer).join(', ')} mono />
        <ResultRow label="Drawers used" value={`${drawerCount} drawer${drawerCount !== 1 ? 's' : ''} across ${freezerCount} freezer${freezerCount !== 1 ? 's' : ''}`} />
      </div>

      {/* Per-drawer breakdown */}
      {drawerCount > 1 && (
        <div className="result-drawer-list">
          <div className="result-drawer-list-header">Container distribution</div>
          {Object.entries(
            result.containers.reduce((acc, c) => {
              const coord = c.location.drawer_coordinate;
              acc[coord] = (acc[coord] || 0) + 1;
              return acc;
            }, {})
          ).map(([coord, count]) => (
            <div key={coord} className="result-drawer-row">
              <span className="font-mono result-drawer-coord">{coord}</span>
              <span className="result-drawer-count">{count}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default LookupPage;

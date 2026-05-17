import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useFreezer, buildDrawerGrid } from '../hooks/useFreezer';
import FreezerGrid from '../components/freezer/FreezerGrid';
import RetrievalForm from '../components/forms/RetrievalForm';
import RetrievalSummaryPanel from '../components/forms/RetrievalSummaryPanel';
import { listFreezersFn,
         previewStudySampleRetrievalFn,
         confirmStudySampleRetrievalFn,
         previewSTDQCRetrievalFn,
         confirmSTDQCRetrievalFn } from '../api';

// ─────────────────────────────────────────────────────────────────────────────

function RetrievalPage() {
  const {
    freezers, selectedFreezer, drawerGrid,
    loading: freezerLoading, error: freezerError,
    fetchFreezers, selectFreezer,
    applySearchOverlay, clearOverlay,
  } = useFreezer();

  // Retrieval type
  const [retrievalType, setRetrievalType] = useState('study_sample');

  // Form data from RetrievalForm
  const [formData, setFormData] = useState(null);

  // Lookup state
  const [lookupResult,  setLookupResult]  = useState(null);
  const [lookupError,   setLookupError]   = useState(null);
  const [looking,       setLooking]       = useState(false);

  // Retrieve state
  const [retrieveResult,  setRetrieveResult]  = useState(null);
  const [retrieveError,   setRetrieveError]   = useState(null);
  const [retrieving,      setRetrieving]      = useState(false);

  useEffect(() => { fetchFreezers(); }, [fetchFreezers]);

  // ── Handlers ───────────────────────────────────────────────────────────────

  function handleFreezerChange(e) {
    const f = freezers.find(fr => fr.asset_id === e.target.value);
    if (f) {
      selectFreezer(f);
      resetLookup();
    }
  }

  function handleTypeChange(type) {
    setRetrievalType(type);
    setFormData(null);
    resetLookup();
  }

  function resetLookup() {
    setLookupResult(null);
    setLookupError(null);
    setRetrieveResult(null);
    setRetrieveError(null);
    clearOverlay();
  }

  function handleFormChange(data) {
    setFormData(data);
    // Clear prior lookup when form changes
    if (lookupResult) resetLookup();
  }

  // ── Validation ─────────────────────────────────────────────────────────────

  function canLookup() {
    if (retrievalType === 'study_sample') {
      return formData?.barcodes?.length > 0;
    }
    return !!formData?.barcode_prefix;
  }

  // ── Extract search coords from a preview result ────────────────────────────

  function extractSearchCoords(result, type) {
    if (type === 'study_sample') {
      const byCoord = {};
      for (const c of result.found) {
        const coord = c.location.drawer_coordinate;
        byCoord[coord] = (byCoord[coord] || 0) + 1;
      }
      return Object.entries(byCoord).map(([drawer_coordinate, matchCount]) => ({
        drawer_coordinate, matchCount,
      }));
    } else {
      // STDQC
      const byCoord = {};
      for (const c of result.containers) {
        const coord = c.location.drawer_coordinate;
        byCoord[coord] = (byCoord[coord] || 0) + 1;
      }
      return Object.entries(byCoord).map(([drawer_coordinate, matchCount]) => ({
        drawer_coordinate, matchCount,
      }));
    }
  }

  // ── If the result involves a different freezer than selected,
  //    build a grid for that freezer and overlay it.
  //    (STDQC batches are always in one freezer; study samples could span
  //     multiple but MVP only highlights within the selected freezer.)

  const applyOverlayFromResult = useCallback(async (result, type) => {
    const coords = extractSearchCoords(result, type);

    // Determine if result references a different freezer than currently shown
    let resultFreezerAssetId;
    if (type === 'study_sample' && result.found.length > 0) {
      resultFreezerAssetId = result.found[0].location.freezer_asset_id;
    } else if (type === 'stdqc' && result.containers?.length > 0) {
      resultFreezerAssetId = result.containers[0].location.freezer_asset_id;
    }

    // If we need to switch to a different freezer, find and select it
    if (resultFreezerAssetId && selectedFreezer?.asset_id !== resultFreezerAssetId) {
      const allFreezers = freezers.length > 0 ? freezers : await listFreezersFn();
      const targetFreezer = allFreezers.find(f => f.asset_id === resultFreezerAssetId);
      if (targetFreezer) selectFreezer(targetFreezer);
    }

    applySearchOverlay(coords);
  }, [selectedFreezer, freezers, selectFreezer, applySearchOverlay]);

  // ── Lookup ─────────────────────────────────────────────────────────────────

  async function handleLookup() {
    setLooking(true);
    setLookupError(null);
    setLookupResult(null);
    setRetrieveResult(null);
    clearOverlay();

    try {
      let result;
      if (retrievalType === 'study_sample') {
        result = await previewStudySampleRetrievalFn({
          container_barcodes: formData.barcodes,
        });
        if (result.total_found === 0) {
          setLookupError('No containers found for the provided barcodes.');
          return;
        }
      } else {
        result = await previewSTDQCRetrievalFn(formData.barcode_prefix);
      }

      setLookupResult(result);
      await applyOverlayFromResult(result, retrievalType);
    } catch (e) {
      if (e.response?.status === 404) {
        setLookupError(
          retrievalType === 'study_sample'
            ? 'None of the provided barcodes were found in the system.'
            : `No STD/QC batch found with prep ID "${formData.barcode_prefix}".`
        );
      } else {
        setLookupError(e.response?.data?.detail || 'Lookup failed. Is the backend running?');
      }
    } finally {
      setLooking(false);
    }
  }

  // ── Retrieve ───────────────────────────────────────────────────────────────

  async function handleRetrieve() {
    setRetrieving(true);
    setRetrieveError(null);

    try {
      let result;
      if (retrievalType === 'study_sample') {
        // Only retrieve barcodes that were actually found during lookup
        const foundBarcodes = lookupResult.found.map(c => c.container_barcode);
        result = await confirmStudySampleRetrievalFn({
          container_barcodes: foundBarcodes,
        });
      } else {
        result = await confirmSTDQCRetrievalFn({
          barcode_prefix: formData.barcode_prefix,
        });
      }

      setRetrieveResult(result);

      // Refresh visualization — rebuild grid and clear overlays
      // (containers are now gone; occupancy will update when backend
      //  exposes a real drawer-state endpoint)
      clearOverlay();
      if (selectedFreezer) selectFreezer(selectedFreezer);

    } catch (e) {
      setRetrieveError(e.response?.data?.detail || 'Retrieval failed.');
    } finally {
      setRetrieving(false);
    }
  }

  // ── Clear ──────────────────────────────────────────────────────────────────

  function handleClear() {
    setFormData(null);
    resetLookup();
  }

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="retrieval-page">

      {/* Top bar */}
      <div className="page-topbar">
        <Link to="/" className="topbar-back">← Back</Link>
        <h2 className="page-title">Container Retrieval</h2>
      </div>

      <div className="retrieval-layout">

        {/* ── Left column: controls ────────────────────────────────────── */}
        <div className="retrieval-controls">

          {/* 1. Freezer selection */}
          <div className="control-section">
            <h3 className="section-title">1. Select Freezer</h3>
            {freezerError && <div className="field-error mb-2">{freezerError}</div>}
            <select
              className="form-select form-control-custom"
              onChange={handleFreezerChange}
              defaultValue=""
            >
              <option value="" disabled>
                {freezerLoading ? 'Loading freezers…' : 'Choose a freezer…'}
              </option>
              {freezers.map(f => (
                <option key={f.asset_id} value={f.asset_id}>
                  {f.asset_id} — {f.temperature}°C — {f.total_drawers} drawers
                </option>
              ))}
            </select>
          </div>

          {/* 2. Retrieval type */}
          <div className="control-section">
            <h3 className="section-title">2. Container Type</h3>
            <div className="radio-group">
              <label className={`radio-option ${retrievalType === 'study_sample' ? 'radio-option--active' : ''}`}>
                <input
                  type="radio"
                  value="study_sample"
                  checked={retrievalType === 'study_sample'}
                  onChange={() => handleTypeChange('study_sample')}
                />
                Study Samples
              </label>
              <label className={`radio-option ${retrievalType === 'stdqc' ? 'radio-option--active' : ''}`}>
                <input
                  type="radio"
                  value="stdqc"
                  checked={retrievalType === 'stdqc'}
                  onChange={() => handleTypeChange('stdqc')}
                />
                STD/QC
              </label>
            </div>
          </div>

          {/* 3. Form */}
          <div className="control-section">
            <h3 className="section-title">3. Container Details</h3>
            <RetrievalForm
              retrievalType={retrievalType}
              onChange={handleFormChange}
              disabled={looking || retrieving}
            />
          </div>

          {/* 4. Lookup + Retrieve */}
          <div className="control-section">
            <h3 className="section-title">4. Lookup &amp; Retrieve</h3>
            <RetrievalSummaryPanel
              retrievalType={retrievalType}
              lookupResult={lookupResult}
              lookupError={lookupError}
              retrieveResult={retrieveResult}
              retrieveError={retrieveError}
              onLookup={handleLookup}
              onRetrieve={handleRetrieve}
              onClear={handleClear}
              looking={looking}
              retrieving={retrieving}
              canLookup={canLookup()}
            />
          </div>

        </div>

        {/* ── Right column: freezer visualization ──────────────────────── */}
        <div className="intro-visualization">
          <div className="viz-header">
            {selectedFreezer ? (
              <span className="viz-freezer-label">
                {selectedFreezer.asset_id}
                <span className="viz-freezer-meta">
                  {selectedFreezer.num_of_layers}L ×
                  {selectedFreezer.num_of_rack_per_layer}R ×
                  {selectedFreezer.num_of_drawer_per_rack}D ·
                  {selectedFreezer.temperature}°C
                </span>
              </span>
            ) : (
              <span className="viz-placeholder-label">No freezer selected</span>
            )}
            {lookupResult && !retrieveResult && (
              <span className="viz-mode-badge viz-mode-badge--retrieval">
                Retrieval targets highlighted
              </span>
            )}
          </div>

          <FreezerGrid
            grid={drawerGrid}
            mode="view"
            onManualSelect={null}
            onSetCount={null}
          />
        </div>
      </div>
    </div>
  );
}

export default RetrievalPage;

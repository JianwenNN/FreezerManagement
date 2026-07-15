import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useFreezer } from '../hooks/useFreezer';
import FreezerGrid from '../components/freezer/FreezerGrid';
import StudySampleForm from '../components/forms/StudySampleForm';
import STDQCForm from '../components/forms/STDQCForm';
import AllocationPanel from '../components/forms/AllocationPanel';
import ManualAssignmentPanel from '../components/forms/ManualAssignmentPanel';
import {
  allocateContainersFn,
  confirmStudySampleAllocationFn,
  confirmSTDQCAllocationFn,
  manualAssignStudySampleFn,
  manualAssignSTDQCFn,
} from '../api';

// ── Introduction mode ─────────────────────────────────────────────────────────
const MODES = { VIEW: 'view', AUTO: 'auto', MANUAL: 'manual' };

function ContainerIntroductionPage() {
  const {
    freezers, selectedFreezer, drawerGrid,
    loading, error: freezerError,
    fetchFreezers, selectFreezer,
    applyAllocationOverlay, clearOverlay,
    toggleManualSelect, setManualCount,
  } = useFreezer();

  const [sampleType,    setSampleType]    = useState('study_sample_container');
  const [formData,      setFormData]      = useState(null);   // from StudySampleForm or STDQCForm
  const [mode,          setMode]          = useState(MODES.VIEW);

  // Auto-assign state
  const [allocations,   setAllocations]   = useState([]);
  const [allocating,    setAllocating]    = useState(false);
  const [allocError,    setAllocError]    = useState(null);
  const [committing,    setCommitting]    = useState(false);
  const [commitError,   setCommitError]   = useState(null);
  const [commitSuccess, setCommitSuccess] = useState(null);

  // Manual state
  const [manualError,   setManualError]   = useState(null);
  const [confirming,    setConfirming]    = useState(false);

  useEffect(() => { fetchFreezers(); }, [fetchFreezers]);

  // ── Helpers ────────────────────────────────────────────────────────────────

  function getTotalContainers() {
    if (!formData) return 0;
    if (sampleType === 'study_sample_container') return formData.containers?.length || 0;
    return formData.container_count || 0;
  }

  function resetAll() {
    setMode(MODES.VIEW);
    setAllocations([]);
    setAllocError(null);
    setCommitError(null);
    setCommitSuccess(null);
    setManualError(null);
    clearOverlay();
  }

  function handleFreezerChange(e) {
    const f = freezers.find(fr => fr.asset_id === e.target.value);
    if (f) { selectFreezer(f); resetAll(); }
  }

  function handleSampleTypeChange(e) {
    setSampleType(e.target.value);
    setFormData(null);
    resetAll();
  }

  // ── Auto Assign ────────────────────────────────────────────────────────────

  async function handleLookupSpace() {
    if (!selectedFreezer || !formData) return;
    const total = getTotalContainers();
    if (total === 0) return;

    setAllocating(true);
    setAllocError(null);
    setCommitSuccess(null);

    try {
      const result = await allocateContainersFn({
        number_of_containers: total,
        sample_type:          sampleType,
        freezer_asset_id:     selectedFreezer.asset_id,
      });
      setAllocations(result);
      applyAllocationOverlay(result);
      setMode(MODES.AUTO);
    } catch (e) {
      setAllocError(e.response?.data?.detail || 'Allocation failed. Check backend.');
    } finally {
      setAllocating(false);
    }
  }

  async function handleCommitAllocation() {
    setCommitting(true);
    setCommitError(null);

    try {
      const tokens   = allocations.map(a => a.reservation_token);
      const total    = getTotalContainers();
      const isPartial = allocations.some(a => a.partial);

      if (sampleType === 'study_sample_container') {
        // Build drawers array — distribute barcodes across allocated drawers
        const barcodes = [...formData.containers];
        const drawers  = allocations.map(a => {
          const slice = barcodes.splice(0, a.container_count);
          return {
            drawer_id:  a.drawer_id,
            containers: slice.map(bc => ({
              container_barcode:  bc,
              study_name:         formData.study_name,
              position_in_drawer: null,
            })),
          };
        });

        await confirmStudySampleAllocationFn({
          freezer_asset_id:     selectedFreezer.asset_id,
          originally_requested: total,
          reservation_tokens:   tokens,
          drawers,
          partial_allowed:      isPartial,
        });
      } else {
        // STDQC
        const drawers = allocations.map(a => ({
          drawer_id: a.drawer_id,
          batch: {
            barcode_prefix:     formData.barcode_prefix,
            container_count:    a.container_count,
            compound_name:      formData.compound_name,
            matrix:             formData.matrix,
            anticoagulant:      formData.anticoagulant,
            prep_date:          formData.prep_date,
            description:        null,
            position_in_drawer: null,
          },
        }));

        await confirmSTDQCAllocationFn({
          freezer_asset_id:     selectedFreezer.asset_id,
          originally_requested: total,
          reservation_tokens:   tokens,
          drawers,
          partial_allowed:      isPartial,
        });
      }

      setCommitSuccess(`Successfully introduced ${total} container${total !== 1 ? 's' : ''}.`);
      resetAll();
      // Re-render grid (occupancy will update when backend exposes drawer state endpoint)
      selectFreezer(selectedFreezer);
    } catch (e) {
      setCommitError(e.response?.data?.detail || 'Commit failed.');
    } finally {
      setCommitting(false);
    }
  }

  // ── Manual Assign ──────────────────────────────────────────────────────────

  function handleManualOverride() {
    clearOverlay();
    setAllocations([]);
    setMode(MODES.MANUAL);
    setManualError(null);
  }

  async function handleConfirmManual() {
    setConfirming(true);
    setManualError(null);

    // Collect selected drawers from grid
    const selected = drawerGrid.flatMap(layer =>
      layer.racks.flatMap(rack =>
        rack.drawers.filter(d => d.manualSelected && (d.manualCount || 0) > 0)
      )
    );

    // Guard: every selected cell must have its real drawer_id resolved
    // (populated by selectFreezer() via listFreezerDrawersFn()). Without
    // this, we'd fall back to sending drawerNum — the bug this guard
    // exists to prevent (drawerNum repeats across racks and is NOT the
    // database drawer_id, so it can silently target the wrong drawer).
    const missingId = selected.find(d => d.id == null);
    if (missingId) {
      setManualError(
        `Drawer IDs haven't finished loading for ${missingId.coord}. ` +
        `Please wait a moment or re-select the freezer, then try again.`
      );
      setConfirming(false);
      return;
    }

    try {
      if (sampleType === 'study_sample_container') {
        const barcodes = [...formData.containers];
        for (const d of selected) {
          const slice = barcodes.splice(0, d.manualCount);
          await manualAssignStudySampleFn({
            drawer_id:  d.id,
            containers: slice.map(bc => ({
              container_barcode:  bc,
              study_name:         formData.study_name,
              position_in_drawer: null,
            })),
          });
        }
      } else {
        for (const d of selected) {
          await manualAssignSTDQCFn({
            drawer_id: d.id,
            batch: {
              barcode_prefix:     formData.barcode_prefix,
              container_count:    d.manualCount,
              compound_name:      formData.compound_name,
              matrix:             formData.matrix,
              anticoagulant:      formData.anticoagulant,
              prep_date:          formData.prep_date,
              description:        null,
              position_in_drawer: null,
            },
          });
        }
      }

      const total = getTotalContainers();
      setCommitSuccess(`Manual assignment complete — ${total} container${total !== 1 ? 's' : ''} placed.`);
      resetAll();
      selectFreezer(selectedFreezer);
    } catch (e) {
      setManualError(e.response?.data?.detail || 'Manual assignment failed.');
    } finally {
      setConfirming(false);
    }
  }

  // ── Derived state ──────────────────────────────────────────────────────────
  const total        = getTotalContainers();
  const canAllocate  = !!selectedFreezer && total > 0;
  const showPanel    = mode === MODES.AUTO && allocations.length > 0;
  const showManual   = mode === MODES.MANUAL;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="intro-page">

      {/* ── Top nav ── */}
      <div className="page-topbar">
        <Link to="/" className="topbar-back">← Back</Link>
        <h2 className="page-title">Container Introduction</h2>
      </div>

      <div className="intro-layout">

        {/* ── Left column: controls ── */}
        <div className="intro-controls">

          {/* Freezer selection */}
          <div className="control-section">
            <h3 className="section-title">1. Select Freezer</h3>
            {freezerError && <div className="field-error mb-2">{freezerError}</div>}
            <select
              className="form-select form-control-custom"
              onChange={handleFreezerChange}
              defaultValue=""
            >
              <option value="" disabled>
                {loading ? 'Loading freezers…' : 'Choose a freezer…'}
              </option>
              {freezers.map(f => (
                <option key={f.asset_id} value={f.asset_id}>
                  {f.asset_id} — {f.temperature}°C — {f.total_drawers} drawers
                </option>
              ))}
            </select>
          </div>

          {/* Sample type toggle */}
          <div className="control-section">
            <h3 className="section-title">2. Container Type</h3>
            <div className="radio-group">
              <label className={`radio-option ${sampleType === 'study_sample_container' ? 'radio-option--active' : ''}`}>
                <input
                  type="radio"
                  value="study_sample_container"
                  checked={sampleType === 'study_sample_container'}
                  onChange={handleSampleTypeChange}
                />
                Study Samples
              </label>
              <label className={`radio-option ${sampleType === 'stdqc_container' ? 'radio-option--active' : ''}`}>
                <input
                  type="radio"
                  value="stdqc_container"
                  checked={sampleType === 'stdqc_container'}
                  onChange={handleSampleTypeChange}
                />
                STD/QC
              </label>
            </div>
          </div>

          {/* Dynamic form */}
          <div className="control-section">
            <h3 className="section-title">3. Container Details</h3>
            {sampleType === 'study_sample_container'
              ? <StudySampleForm onChange={setFormData} />
              : <STDQCForm onChange={setFormData} />
            }
          </div>

          {/* Container count indicator */}
          {total > 0 && (
            <div className="total-indicator">
              <span className="total-label">Containers ready to introduce</span>
              <span className="total-count">{total}</span>
            </div>
          )}

          {/* Action buttons */}
          <div className="control-section">
            <h3 className="section-title">4. Assign to Freezer</h3>
            <div className="action-buttons">
              <button
                className="btn-action btn-action--primary"
                onClick={handleLookupSpace}
                disabled={!canAllocate || allocating || mode === MODES.MANUAL}
              >
                {allocating ? 'Searching…' : '⊞ Lookup Space (Auto Assign)'}
              </button>
              <button
                className="btn-action btn-action--secondary"
                onClick={handleManualOverride}
                disabled={!canAllocate || mode === MODES.AUTO}
              >
                ⊟ Manual Override
              </button>
            </div>
            {allocError && <div className="field-error mt-2">{allocError}</div>}
          </div>

          {/* Success message */}
          {commitSuccess && (
            <div className="success-banner">{commitSuccess}</div>
          )}

          {/* Panels */}
          {showPanel && (
            <AllocationPanel
              allocations={allocations}
              onCommit={handleCommitAllocation}
              onCancel={resetAll}
              committing={committing}
              error={commitError}
            />
          )}

          {showManual && (
            <ManualAssignmentPanel
              drawerGrid={drawerGrid}
              totalRequired={total}
              sampleType={sampleType}
              onConfirm={handleConfirmManual}
              onCancel={resetAll}
              confirming={confirming}
              error={manualError}
            />
          )}
        </div>

        {/* ── Right column: freezer visualization ── */}
        <div className="intro-visualization">
          <div className="viz-header">
            {selectedFreezer ? (
              <span className="viz-freezer-label">
                {selectedFreezer.asset_id}
                <span className="viz-freezer-meta">
                  {selectedFreezer.num_of_layers}L ×
                  {selectedFreezer.num_of_rack_per_layer}R ×
                  {selectedFreezer.num_of_drawer_per_rack}D
                  · {selectedFreezer.temperature}°C
                </span>
              </span>
            ) : (
              <span className="viz-placeholder-label">No freezer selected</span>
            )}
            {mode === MODES.MANUAL && (
              <span className="viz-mode-badge">Manual Selection Mode</span>
            )}
          </div>
          <FreezerGrid
            grid={drawerGrid}
            mode={mode}
            onManualSelect={toggleManualSelect}
            onSetCount={setManualCount}
          />
        </div>
      </div>
    </div>
  );
}

export default ContainerIntroductionPage;

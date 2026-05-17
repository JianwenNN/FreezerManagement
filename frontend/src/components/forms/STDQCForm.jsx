import React, { useState } from 'react';

// Expected format: compound_name-matrix-anticoagulant-prepdate-sourceid
// Example: Warfarin-Plasma-EDTA-20260516-B001
const PREP_ID_REGEX = /^[^-]+-[^-]+-[^-]+-\d{8}-[^-]+$/;

function parseRepId(prepId) {
  const parts = prepId.split('-');
  if (parts.length < 5) return null;
  // Last part is source_id, second-to-last is prepdate, third-to-last is anticoagulant
  // But compound_name and matrix could contain no hyphens per the format
  const [compound_name, matrix, anticoagulant, prepdate, ...sourceparts] = parts;
  const source_id = sourceparts.join('-');
  return { compound_name, matrix, anticoagulant, prep_date: prepdate, source_id };
}

/**
 * STDQCForm
 *
 * Props:
 *  onChange(data) — called with { barcode_prefix, container_count, parsed }
 *                   where parsed: { compound_name, matrix, anticoagulant, prep_date, source_id }
 */
function STDQCForm({ onChange }) {
  const [prepId,        setPrepId]        = useState('');
  const [containerCount,setContainerCount]= useState('');
  const [prepIdError,   setPrepIdError]   = useState('');

  function validate(val) {
    if (!val) { setPrepIdError(''); return; }
    if (!PREP_ID_REGEX.test(val)) {
      setPrepIdError('Format: CompoundName-Matrix-Anticoagulant-YYYYMMDD-SourceID');
    } else {
      setPrepIdError('');
    }
  }

  function handlePrepIdChange(e) {
    const val = e.target.value;
    setPrepId(val);
    validate(val);
    emit(val, containerCount);
  }

  function handleCountChange(e) {
    const val = e.target.value;
    setContainerCount(val);
    emit(prepId, val);
  }

  function emit(pid, count) {
    if (!PREP_ID_REGEX.test(pid) || !count) {
      onChange(null);
      return;
    }
    const parsed = parseRepId(pid);
    if (!parsed) { onChange(null); return; }

    // Build prep_date as ISO string (YYYYMMDD -> YYYY-MM-DDT00:00:00Z)
    const pd = parsed.prep_date;
    const isoDate = `${pd.slice(0,4)}-${pd.slice(4,6)}-${pd.slice(6,8)}T00:00:00Z`;

    onChange({
      barcode_prefix: pid,
      container_count: parseInt(count, 10) || 0,
      compound_name:   parsed.compound_name,
      matrix:          parsed.matrix,
      anticoagulant:   parsed.anticoagulant,
      prep_date:       isoDate,
      source_id:       parsed.source_id,
    });
  }

  const isValid = PREP_ID_REGEX.test(prepId) && parseInt(containerCount, 10) > 0;

  return (
    <div className="intro-form">
      {/* Prep ID */}
      <div className="mb-3">
        <label className="form-label form-label-custom">
          Preparation ID
          <span className="hint-text"> — CompoundName-Matrix-Anticoagulant-YYYYMMDD-SourceID</span>
        </label>
        <input
          type="text"
          className={`form-control form-control-custom font-mono${prepIdError ? ' is-invalid' : isValid ? ' is-valid' : ''}`}
          placeholder="Warfarin-Plasma-EDTA-20260516-B001"
          value={prepId}
          onChange={handlePrepIdChange}
        />
        {prepIdError && <div className="field-error mt-1">{prepIdError}</div>}
      </div>

      {/* Parsed preview */}
      {isValid && (
        <div className="prep-id-preview mb-3">
          {(() => {
            const p = parseRepId(prepId);
            return (
              <div className="prep-preview-grid">
                <span className="prep-key">Compound</span><span className="prep-val">{p.compound_name}</span>
                <span className="prep-key">Matrix</span>  <span className="prep-val">{p.matrix}</span>
                <span className="prep-key">Anticoag</span><span className="prep-val">{p.anticoagulant}</span>
                <span className="prep-key">Prep Date</span><span className="prep-val">{p.prep_date}</span>
                <span className="prep-key">Source ID</span><span className="prep-val">{p.source_id}</span>
              </div>
            );
          })()}
        </div>
      )}

      {/* Container count */}
      <div className="mb-3">
        <label className="form-label form-label-custom">Total Container Count</label>
        <input
          type="number"
          min={1}
          className="form-control form-control-custom"
          placeholder="e.g. 12"
          value={containerCount}
          onChange={handleCountChange}
        />
      </div>
    </div>
  );
}

export default STDQCForm;

import React, { useState, useRef } from 'react';

/**
 * RetrievalForm
 *
 * Handles both retrieval input modes:
 *  - 'study_sample': study name (informational) + barcode list (scanned one by one)
 *  - 'stdqc':        single prep ID input
 *
 * Props:
 *  retrievalType  — 'study_sample' | 'stdqc'
 *  onChange(data) — called whenever form data changes
 *                   study_sample: { study_name, barcodes: string[] }
 *                   stdqc:        { barcode_prefix: string }
 *  disabled       — disable all inputs (e.g. during lookup/retrieve)
 */
function RetrievalForm({ retrievalType, onChange, disabled }) {
  return retrievalType === 'study_sample'
    ? <StudySampleRetrievalInput onChange={onChange} disabled={disabled} />
    : <STDQCRetrievalInput onChange={onChange} disabled={disabled} />;
}

// ── Study sample input ────────────────────────────────────────────────────────

function StudySampleRetrievalInput({ onChange, disabled }) {
  const [studyName,    setStudyName]    = useState('');
  const [barcodeInput, setBarcodeInput] = useState('');
  const [barcodes,     setBarcodes]     = useState([]);
  const [dupError,     setDupError]     = useState('');
  const inputRef = useRef(null);

  function notify(name, list) {
    onChange({ study_name: name, barcodes: list });
  }

  function handleStudyNameChange(e) {
    setStudyName(e.target.value);
    notify(e.target.value, barcodes);
  }

  function handleKeyDown(e) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const val = barcodeInput.trim();
    if (!val) return;
    if (barcodes.includes(val)) {
      setDupError(`"${val}" already in list`);
      return;
    }
    const next = [...barcodes, val];
    setBarcodes(next);
    setBarcodeInput('');
    setDupError('');
    notify(studyName, next);
    inputRef.current?.focus();
  }

  function removeBarcode(bc) {
    const next = barcodes.filter(b => b !== bc);
    setBarcodes(next);
    notify(studyName, next);
  }

  function clearAll() {
    setBarcodes([]);
    setStudyName('');
    setBarcodeInput('');
    setDupError('');
    onChange({ study_name: '', barcodes: [] });
  }

  return (
    <div className="retrieval-form">
      {/* Study Name — informational only in MVP */}
      <div className="mb-3">
        <label className="form-label form-label-custom">
          Study Name
          <span className="hint-text"> — for reference only</span>
        </label>
        <input
          type="text"
          className="form-control form-control-custom"
          placeholder="e.g. PHOENIX-01"
          value={studyName}
          onChange={handleStudyNameChange}
          disabled={disabled}
        />
      </div>

      {/* Barcode input */}
      <div className="mb-2">
        <label className="form-label form-label-custom">
          Scan / Enter Container Barcodes
          <span className="hint-text"> — press Enter to add</span>
        </label>
        <input
          ref={inputRef}
          type="text"
          className="form-control form-control-custom font-mono"
          placeholder="BC-00001"
          value={barcodeInput}
          onChange={e => { setBarcodeInput(e.target.value); setDupError(''); }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        {dupError && <div className="field-error mt-1">{dupError}</div>}
      </div>

      {/* Barcode list */}
      {barcodes.length > 0 && (
        <div className="barcode-list">
          <div className="barcode-list-header">
            {barcodes.length} barcode{barcodes.length !== 1 ? 's' : ''} queued
            {studyName && <span className="barcode-study-tag">{studyName}</span>}
            <button className="barcode-clear-btn" onClick={clearAll} disabled={disabled}>
              Clear all
            </button>
          </div>
          <div className="barcode-chips">
            {barcodes.map(bc => (
              <span key={bc} className="barcode-chip">
                {bc}
                <button
                  className="barcode-chip-remove"
                  onClick={() => removeBarcode(bc)}
                  disabled={disabled}
                  title="Remove"
                >×</button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── STDQC input ───────────────────────────────────────────────────────────────

function STDQCRetrievalInput({ onChange, disabled }) {
  const [prepId, setPrepId] = useState('');

  function handleChange(e) {
    const val = e.target.value;
    setPrepId(val);
    onChange({ barcode_prefix: val.trim() });
  }

  return (
    <div className="retrieval-form">
      <div className="mb-3">
        <label className="form-label form-label-custom">
          Preparation ID
          <span className="hint-text"> — identifies the entire STD/QC batch</span>
        </label>
        <input
          type="text"
          className="form-control form-control-custom font-mono"
          placeholder="Warfarin-Plasma-EDTA-20260516-B001"
          value={prepId}
          onChange={handleChange}
          disabled={disabled}
        />
      </div>
    </div>
  );
}

export default RetrievalForm;

import React, { useState, useRef } from 'react';

/**
 * StudySampleForm
 * Handles study name + barcode list entry for batch introduction.
 *
 * Props:
 *  onChange(data) — called whenever study_name or containers changes
 *                   data: { study_name, containers: string[] }
 */
function StudySampleForm({ onChange }) {
  const [studyName,  setStudyName]  = useState('');
  const [barcodeInput, setBarcodeInput] = useState('');
  const [barcodes,   setBarcodes]   = useState([]);
  const [error,      setError]      = useState('');
  const inputRef = useRef(null);

  function notify(name, list) {
    onChange({ study_name: name, containers: list });
  }

  function handleStudyNameChange(e) {
    setStudyName(e.target.value);
    notify(e.target.value, barcodes);
  }

  function handleBarcodeKeyDown(e) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const val = barcodeInput.trim();
    if (!val) return;

    if (barcodes.includes(val)) {
      setError(`Barcode "${val}" already added.`);
      return;
    }

    const next = [...barcodes, val];
    setBarcodes(next);
    setBarcodeInput('');
    setError('');
    notify(studyName, next);
    inputRef.current?.focus();
  }

  function removeBarcode(bc) {
    const next = barcodes.filter(b => b !== bc);
    setBarcodes(next);
    notify(studyName, next);
  }

  return (
    <div className="intro-form">
      {/* Study Name */}
      <div className="mb-3">
        <label className="form-label form-label-custom">Study Name</label>
        <input
          type="text"
          className="form-control form-control-custom"
          placeholder="e.g. PHOENIX-01"
          value={studyName}
          onChange={handleStudyNameChange}
        />
      </div>

      {/* Barcode scanner input */}
      <div className="mb-2">
        <label className="form-label form-label-custom">
          Scan / Enter Container Barcode
          <span className="hint-text"> — press Enter to add</span>
        </label>
        <input
          ref={inputRef}
          type="text"
          className="form-control form-control-custom font-mono"
          placeholder="BC-00001"
          value={barcodeInput}
          onChange={e => { setBarcodeInput(e.target.value); setError(''); }}
          onKeyDown={handleBarcodeKeyDown}
        />
        {error && <div className="field-error mt-1">{error}</div>}
      </div>

      {/* Barcode list */}
      {barcodes.length > 0 && (
        <div className="barcode-list">
          <div className="barcode-list-header">
            {barcodes.length} container{barcodes.length !== 1 ? 's' : ''} queued
            {studyName && <span className="barcode-study-tag">{studyName}</span>}
          </div>
          <div className="barcode-chips">
            {barcodes.map(bc => (
              <span key={bc} className="barcode-chip">
                {bc}
                <button
                  className="barcode-chip-remove"
                  onClick={() => removeBarcode(bc)}
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

export default StudySampleForm;

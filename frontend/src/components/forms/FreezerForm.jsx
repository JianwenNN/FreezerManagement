import React, { useState } from 'react';

// ── Field definitions ─────────────────────────────────────────────────────────

const FIELDS = [
  {
    key:         'asset_id',
    label:       'Asset ID',
    type:        'text',
    placeholder: 'e.g. FRZ-LAB-01',
    hint:        'Unique identifier for this freezer',
    validate:    v => v.trim() ? null : 'Asset ID is required',
  },
  {
    key:         'temperature',
    label:       'Temperature (°C)',
    type:        'number',
    placeholder: 'e.g. -80',
    hint:        'Operating temperature — can be negative',
    validate:    v => v !== '' && !isNaN(Number(v)) ? null : 'Enter a valid temperature',
  },
  {
    key:         'num_of_layers',
    label:       'Number of Layers',
    type:        'number',
    placeholder: 'e.g. 5',
    hint:        'Vertical layers inside the freezer',
    validate:    v => Number.isInteger(Number(v)) && Number(v) >= 1 ? null : 'Must be a positive integer',
  },
  {
    key:         'num_of_rack_per_layer',
    label:       'Racks per Layer',
    type:        'number',
    placeholder: 'e.g. 4',
    hint:        'Number of racks in each layer',
    validate:    v => Number.isInteger(Number(v)) && Number(v) >= 1 ? null : 'Must be a positive integer',
  },
  {
    key:         'num_of_drawer_per_rack',
    label:       'Drawers per Rack',
    type:        'number',
    placeholder: 'e.g. 6',
    hint:        'Number of drawers in each rack',
    validate:    v => Number.isInteger(Number(v)) && Number(v) >= 1 ? null : 'Must be a positive integer',
  },
  {
    key:         'study_sample_capacity',
    label:       'Study Sample Capacity',
    type:        'number',
    placeholder: 'e.g. 5',
    hint:        'Max study sample containers per drawer',
    validate:    v => Number.isInteger(Number(v)) && Number(v) >= 1 ? null : 'Must be ≥ 1',
  },
  {
    key:         'stdqc_capacity',
    label:       'STD/QC Capacity',
    type:        'number',
    placeholder: 'e.g. 8',
    hint:        'Max STD/QC containers per drawer',
    validate:    v => Number.isInteger(Number(v)) && Number(v) >= 1 ? null : 'Must be ≥ 1',
  },
  {
    key:         'description',
    label:       'Description',
    type:        'text',
    placeholder: 'Optional notes about this freezer',
    hint:        'Optional',
    validate:    () => null,   // optional field
    optional:    true,
  },
  {
    key:         'location',
    label:       'Physical Location',
    type:        'text',
    placeholder: 'e.g. Lab Room 2B, Bay 3',
    hint:        'Optional',
    validate:    () => null,   // optional field
    optional:    true,
  },
];

// ── FreezerForm ───────────────────────────────────────────────────────────────

/**
 * FreezerForm
 *
 * Props:
 *  onSubmit(payload)  — called with the validated payload object on submit
 *  submitting         — boolean — shows loading state on submit button
 *  disabled           — boolean — disables all fields (e.g. after success)
 */
function FreezerForm({ onSubmit, submitting, disabled }) {
  const initialValues = Object.fromEntries(FIELDS.map(f => [f.key, '']));
  const [values,  setValues]  = useState(initialValues);
  const [touched, setTouched] = useState({});   // track which fields the user has interacted with
  const [showAll, setShowAll] = useState(false); // force-show all errors on submit attempt

  // ── Helpers ────────────────────────────────────────────────────────────────

  function getError(field) {
    if (!touched[field.key] && !showAll) return null;
    return field.validate(values[field.key]);
  }

  function isFormValid() {
    return FIELDS.every(f => f.validate(values[f.key]) === null);
  }

  function handleChange(key, val) {
    setValues(prev => ({ ...prev, [key]: val }));
  }

  function handleBlur(key) {
    setTouched(prev => ({ ...prev, [key]: true }));
  }

  function handleSubmit(e) {
    e.preventDefault();

    // Mark all fields touched to show errors
    setShowAll(true);
    if (!isFormValid()) return;

    // Build typed payload
    const payload = {
      asset_id:               values.asset_id.trim(),
      temperature:            Number(values.temperature),
      num_of_layers:          parseInt(values.num_of_layers, 10),
      num_of_rack_per_layer:  parseInt(values.num_of_rack_per_layer, 10),
      num_of_drawer_per_rack: parseInt(values.num_of_drawer_per_rack, 10),
      study_sample_capacity:  parseInt(values.study_sample_capacity, 10),
      stdqc_capacity:         parseInt(values.stdqc_capacity, 10),
    };
    if (values.description.trim()) payload.description = values.description.trim();
    if (values.location.trim())    payload.location    = values.location.trim();

    onSubmit(payload);
  }

  // ── Computed drawer total ─────────────────────────────────────────────────
  const layers  = parseInt(values.num_of_layers, 10)          || 0;
  const racks   = parseInt(values.num_of_rack_per_layer, 10)  || 0;
  const drawers = parseInt(values.num_of_drawer_per_rack, 10) || 0;
  const totalDrawers = layers * racks * drawers;

  // ── Render ─────────────────────────────────────────────────────────────────
  const requiredFields = FIELDS.filter(f => !f.optional);
  const optionalFields = FIELDS.filter(f => f.optional);

  return (
    <form onSubmit={handleSubmit} noValidate>

      {/* Required fields */}
      <div className="form-section">
        <div className="form-section-label">Identification</div>
        <FormField
          field={FIELDS[0]}
          value={values.asset_id}
          error={getError(FIELDS[0])}
          onChange={handleChange}
          onBlur={handleBlur}
          disabled={disabled || submitting}
        />
        <FormField
          field={FIELDS[1]}
          value={values.temperature}
          error={getError(FIELDS[1])}
          onChange={handleChange}
          onBlur={handleBlur}
          disabled={disabled || submitting}
        />
      </div>

      <div className="form-section">
        <div className="form-section-label">Physical Structure</div>
        {[FIELDS[2], FIELDS[3], FIELDS[4]].map(f => (
          <FormField
            key={f.key}
            field={f}
            value={values[f.key]}
            error={getError(f)}
            onChange={handleChange}
            onBlur={handleBlur}
            disabled={disabled || submitting}
          />
        ))}
        {totalDrawers > 0 && (
          <div className="drawer-total-preview">
            This freezer will have <strong>{totalDrawers.toLocaleString()}</strong> drawers total
            ({layers}L × {racks}R × {drawers}D)
          </div>
        )}
      </div>

      <div className="form-section">
        <div className="form-section-label">Drawer Capacity</div>
        <div className="capacity-hint">
          A drawer holds either study samples OR STD/QC — never both.
          The first container placed locks the drawer to that type.
        </div>
        {[FIELDS[5], FIELDS[6]].map(f => (
          <FormField
            key={f.key}
            field={f}
            value={values[f.key]}
            error={getError(f)}
            onChange={handleChange}
            onBlur={handleBlur}
            disabled={disabled || submitting}
          />
        ))}
      </div>

      <div className="form-section">
        <div className="form-section-label">Optional</div>
        {optionalFields.map(f => (
          <FormField
            key={f.key}
            field={f}
            value={values[f.key]}
            error={getError(f)}
            onChange={handleChange}
            onBlur={handleBlur}
            disabled={disabled || submitting}
          />
        ))}
      </div>

      <button
        type="submit"
        className="btn-submit-freezer"
        disabled={submitting || disabled}
      >
        {submitting ? (
          <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />Creating…</>
        ) : (
          '+ Create Freezer'
        )}
      </button>
    </form>
  );
}

// ── FormField ─────────────────────────────────────────────────────────────────

function FormField({ field, value, error, onChange, onBlur, disabled }) {
  const hasError = !!error;

  return (
    <div className="freezer-field mb-3">
      <label className="form-label form-label-custom" htmlFor={field.key}>
        {field.label}
        {field.optional && <span className="optional-tag">optional</span>}
      </label>
      <input
        id={field.key}
        type={field.type}
        step={field.type === 'number' ? '1' : undefined}
        className={`form-control form-control-custom${hasError ? ' is-invalid' : ''}`}
        placeholder={field.placeholder}
        value={value}
        onChange={e => onChange(field.key, e.target.value)}
        onBlur={() => onBlur(field.key)}
        disabled={disabled}
        autoComplete="off"
      />
      {field.hint && !hasError && (
        <div className="form-text field-hint">{field.hint}</div>
      )}
      {hasError && (
        <div className="invalid-feedback d-block">{error}</div>
      )}
    </div>
  );
}

export default FreezerForm;

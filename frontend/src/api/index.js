import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// ── Freezers ────────────────────────────────────────────────────────────────

export const listFreezersFn = () =>
  api.get('/freezers/').then(r => r.data);

export const createFreezerFn = (payload) =>
  // POST /freezers/
  // payload: { asset_id, temperature, num_of_layers, num_of_rack_per_layer,
  //            num_of_drawer_per_rack, study_sample_capacity, stdqc_capacity,
  //            description?, location? }
  api.post('/freezers/', payload).then(r => r.data);

// ── Drawer occupancy ─────────────────────────────────────────────────────────
// Backend doesn't expose a single "drawer state" endpoint yet, so we derive
// occupancy from the drawer_coordinates view via the admin endpoint and
// supplement with available_space queries per drawer during allocation.
// For now we return the freezer list (which has enough info to render the grid)
// and fetch available space per drawer lazily when needed.

export const getFreezerDrawersFn = (freezerAssetId) =>
  // Returns all drawers belonging to the freezer via the admin reserved-drawers
  // endpoint filtered client-side, plus a synthetic occupancy call.
  // Replace with a dedicated /freezers/{id}/drawers endpoint when available.
  api.get('/admin/reserved-drawers').then(r =>
    r.data.filter(d => d.freezer_asset_id === freezerAssetId)
  );

// ── Allocation (suggest) ────────────────────────────────────────────────────

export const allocateContainersFn = (payload) =>
  // payload: { number_of_containers, sample_type, freezer_asset_id }
  api.post('/containers/allocate-proximity/', payload).then(r => r.data);

// ── Confirm allocation ───────────────────────────────────────────────────────

export const confirmStudySampleAllocationFn = (payload) =>
  api.post('/containers/confirm/study-sample/', payload).then(r => r.data);

export const confirmSTDQCAllocationFn = (payload) =>
  api.post('/containers/confirm/stdqc/', payload).then(r => r.data);

// ── Manual assignment ────────────────────────────────────────────────────────

export const manualAssignStudySampleFn = (payload) =>
  // payload: { drawer_id, containers: [{container_barcode, study_name}] }
  api.post('/containers/manual/study-sample/', payload).then(r => r.data);

export const manualAssignSTDQCFn = (payload) =>
  // payload: { drawer_id, batch: { barcode_prefix, container_count, ... } }
  api.post('/containers/manual/stdqc/', payload).then(r => r.data);

// ── Lookup / search ──────────────────────────────────────────────────────────

export const lookupStudySampleFn = (containerBarcode) =>
  // GET /samples/study-sample/{container_barcode}
  // Returns: { id, container_barcode, study_name, position_in_drawer, date_added, location }
  api.get(`/samples/study-sample/${encodeURIComponent(containerBarcode)}`).then(r => r.data);

export const lookupSTDQCFn = (barcodePrefix) =>
  // GET /samples/stdqc/?barcode_prefix={prefix}
  // Returns: { barcode_prefix, compound_name, matrix, anticoagulant, prep_date, description, total_count, containers }
  api.get('/samples/stdqc/', { params: { barcode_prefix: barcodePrefix } }).then(r => r.data);

// ── Retrieval ────────────────────────────────────────────────────────────────

export const previewStudySampleRetrievalFn = (payload) =>
  // POST /samples/study-sample/retrieval-preview
  // payload: { container_barcodes: string[] }
  // Returns: { found: [...], not_found: string[], total_found: int }
  api.post('/samples/study-sample/retrieval-preview', payload).then(r => r.data);

export const confirmStudySampleRetrievalFn = (payload) =>
  // POST /samples/study-sample/retrieval-confirm
  // payload: { container_barcodes: string[] }
  // Returns: { total_removed, not_found, removed: [...] }
  api.post('/samples/study-sample/retrieval-confirm', payload).then(r => r.data);

export const previewSTDQCRetrievalFn = (barcodePrefix) =>
  // GET /samples/stdqc/retrieval-preview?barcode_prefix={prefix}
  // Returns: { barcode_prefix, compound_name, ..., total_count, containers: [...] }
  api.get('/samples/stdqc/retrieval-preview', { params: { barcode_prefix: barcodePrefix } }).then(r => r.data);

export const confirmSTDQCRetrievalFn = (payload) =>
  // POST /samples/stdqc/retrieval-confirm
  // payload: { barcode_prefix: string }
  // Returns: { barcode_prefix, total_removed }
  api.post('/samples/stdqc/retrieval-confirm', payload).then(r => r.data);

export default api;

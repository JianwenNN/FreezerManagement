import { useState, useCallback } from 'react';
import { listFreezersFn, listFreezerDrawersFn } from '../api';

/**
 * Builds a synthetic drawer grid from a freezer's dimension metadata,
 * with real drawer_id values merged in from listFreezerDrawersFn().
 *
 * Occupancy itself is still unknown client-side (shown as "unknown" /
 * white) — that remains a future enhancement. This function only fixes
 * id resolution: every cell now carries the real `id` used for manual
 * assignment, instead of relying on the synthetic drawerNum.
 */
export function buildDrawerGrid(freezer, drawerIdLookup = {}, reservedDrawerIds = new Set()) {
  const layers = [];
  for (let l = 1; l <= freezer.num_of_layers; l++) {
    const racks = [];
    for (let r = 1; r <= freezer.num_of_rack_per_layer; r++) {
      const drawers = [];
      for (let d = 1; d <= freezer.num_of_drawer_per_rack; d++) {
        const coord = `${freezer.asset_id}-${l}-${r}-${d}`;
        // Real database drawer_id, resolved from the backend via
        // listFreezerDrawersFn(). Falls back to undefined if the lookup
        // hasn't loaded yet — manual selection should be disabled/ignored
        // until this is populated, since submitting without it means
        // there is no real drawer_id to send.
        const id = drawerIdLookup[`${l}-${r}-${d}`];
        drawers.push({
          id,
          coord,
          layerNum:  l,
          rackNum:   r,
          drawerNum: d,
          // Occupancy state: 'empty' | 'partial' | 'full' | 'reserved' | 'unknown'
          // Will be enriched when backend provides real data
          status:    'unknown',
          usedCount: null,
          capacity:  null,
          reserved:  false,
        });
      }
      racks.push({ rackNum: r, drawers });
    }
    layers.push({ layerNum: l, racks });
  }
  return layers;
}

export function useFreezer() {
  const [freezers,         setFreezers]         = useState([]);
  const [selectedFreezer,  setSelectedFreezer]  = useState(null);
  const [drawerGrid,       setDrawerGrid]        = useState([]);
  const [loading,          setLoading]           = useState(false);
  const [error,            setError]             = useState(null);

  const fetchFreezers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFreezersFn();
      setFreezers(data);
    } catch (e) {
      setError('Failed to load freezers. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  const selectFreezer = useCallback(async (freezer) => {
    setSelectedFreezer(freezer);
    setError(null);

    // Build a quick lookup of "layer-rack-drawer" -> real drawer_id so the
    // grid (and anything submitted from it) uses actual database ids
    // instead of the synthetic drawerNum (which repeats across racks).
    let drawerIdLookup = {};
    try {
      const drawers = await listFreezerDrawersFn(freezer.asset_id);
      drawerIdLookup = drawers.reduce((acc, d) => {
        acc[`${d.layer_number}-${d.rack_number}-${d.drawer_number}`] = d.drawer_id;
        return acc;
      }, {});
    } catch (e) {
      setError('Failed to load drawer IDs for this freezer. Manual assignment will be unavailable until this succeeds.');
    }

    const grid = buildDrawerGrid(freezer, drawerIdLookup);
    setDrawerGrid(grid);
  }, []);

  /**
   * Overlay allocation suggestions onto the drawer grid.
   * allocationResults: array from the allocate-proximity API.
   */
  const applyAllocationOverlay = useCallback((allocationResults) => {
    setDrawerGrid(prev =>
      prev.map(layer => ({
        ...layer,
        racks: layer.racks.map(rack => ({
          ...rack,
          drawers: rack.drawers.map(drawer => {
            const hit = allocationResults.find(a => a.drawer_coordinate === drawer.coord);
            return hit
              ? { ...drawer, allocationCount: hit.container_count, reservationToken: hit.reservation_token, expiresAt: hit.expires_at, highlighted: true }
              : { ...drawer, highlighted: false, allocationCount: undefined };
          }),
        })),
      }))
    );
  }, []);


  /**
   * Overlay search results onto the drawer grid.
   * Unlike applyAllocationOverlay, this PRESERVES the drawer's occupancy
   * status colour — searchMatch is a separate visual layer (glowing ring).
   *
   * searchCoords: array of { drawer_coordinate, matchCount }
   */
  const applySearchOverlay = useCallback((searchCoords) => {
    setDrawerGrid(prev =>
      prev.map(layer => ({
        ...layer,
        racks: layer.racks.map(rack => ({
          ...rack,
          drawers: rack.drawers.map(drawer => {
            const hit = searchCoords.find(s => s.drawer_coordinate === drawer.coord);
            return {
              ...drawer,
              searchMatch: !!hit,
              matchCount:  hit ? hit.matchCount : undefined,
            };
          }),
        })),
      }))
    );
  }, []);

  const clearOverlay = useCallback(() => {
    setDrawerGrid(prev =>
      prev.map(layer => ({
        ...layer,
        racks: layer.racks.map(rack => ({
          ...rack,
          drawers: rack.drawers.map(d => ({
            ...d, highlighted: false, allocationCount: undefined, manualSelected: false, manualCount: 0, searchMatch: false, matchCount: undefined,
          })),
        })),
      }))
    );
  }, []);

  /**
   * Toggle manual selection on a drawer.
   */
  const toggleManualSelect = useCallback((coord) => {
    setDrawerGrid(prev =>
      prev.map(layer => ({
        ...layer,
        racks: layer.racks.map(rack => ({
          ...rack,
          drawers: rack.drawers.map(d =>
            d.coord === coord
              ? { ...d, manualSelected: !d.manualSelected, manualCount: d.manualSelected ? 0 : (d.manualCount || 0) }
              : d
          ),
        })),
      }))
    );
  }, []);

  const setManualCount = useCallback((coord, count) => {
    setDrawerGrid(prev =>
      prev.map(layer => ({
        ...layer,
        racks: layer.racks.map(rack => ({
          ...rack,
          drawers: rack.drawers.map(d =>
            d.coord === coord ? { ...d, manualCount: count } : d
          ),
        })),
      }))
    );
  }, []);

  return {
    freezers, selectedFreezer, drawerGrid,
    loading, error,
    fetchFreezers, selectFreezer,
    applyAllocationOverlay, applySearchOverlay, clearOverlay,
    toggleManualSelect, setManualCount,
  };
}

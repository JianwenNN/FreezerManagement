import React from 'react';
import DrawerCell from './DrawerCell';

// ── RackView ─────────────────────────────────────────────────────────────────

export function RackView({ rack, mode, onManualSelect, onSetCount }) {
  return (
    <div className="rack-view">
      <div className="rack-label">R{rack.rackNum}</div>
      <div className="rack-drawers">
        {rack.drawers.map(drawer => (
          <DrawerCell
            key={drawer.coord}
            drawer={drawer}
            mode={mode}
            onManualSelect={onManualSelect}
            onSetCount={onSetCount}
          />
        ))}
      </div>
    </div>
  );
}

// ── LayerView ─────────────────────────────────────────────────────────────────

export function LayerView({ layer, mode, onManualSelect, onSetCount }) {
  return (
    <div className="layer-view">
      <div className="layer-label">Layer {layer.layerNum}</div>
      <div className="layer-racks">
        {layer.racks.map(rack => (
          <RackView
            key={rack.rackNum}
            rack={rack}
            mode={mode}
            onManualSelect={onManualSelect}
            onSetCount={onSetCount}
          />
        ))}
      </div>
    </div>
  );
}

// ── FreezerGrid ───────────────────────────────────────────────────────────────

/**
 * FreezerGrid — renders the full spatial freezer visualization.
 *
 * Props:
 *  grid           — array of layer objects from useFreezer
 *  mode           — 'view' | 'auto' | 'manual'
 *  onManualSelect — callback(coord)
 *  onSetCount     — callback(coord, count)
 */
function FreezerGrid({ grid, mode = 'view', onManualSelect, onSetCount }) {
  if (!grid || grid.length === 0) {
    return (
      <div className="freezer-grid-empty">
        <span>Select a freezer to view its layout</span>
      </div>
    );
  }

  return (
    <div className="freezer-grid">
      {/* Legend */}
      <div className="grid-legend">
        <span className="legend-item legend-empty">Empty</span>
        <span className="legend-item legend-partial">Partial</span>
        <span className="legend-item legend-full">Full</span>
        <span className="legend-item legend-reserved">Reserved</span>
        {mode === 'auto'   && <span className="legend-item legend-allocated">Allocated</span>}
        {mode === 'manual' && <span className="legend-item legend-manual">Selected</span>}
        {mode === 'view' && <span className="legend-item legend-search">Match</span>}
      </div>

      {/* Layers — top to bottom */}
      <div className="freezer-layers">
        {grid.map(layer => (
          <LayerView
            key={layer.layerNum}
            layer={layer}
            mode={mode}
            onManualSelect={onManualSelect}
            onSetCount={onSetCount}
          />
        ))}
      </div>
    </div>
  );
}

export default FreezerGrid;

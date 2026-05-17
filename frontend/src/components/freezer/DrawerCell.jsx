import React from 'react';

/**
 * DrawerCell — one clickable drawer unit in the freezer grid.
 *
 * Props:
 *  drawer          — drawer data object from the grid
 *  mode            — 'view' | 'auto' | 'manual'
 *  onManualSelect  — callback(coord) for manual mode
 *  onSetCount      — callback(coord, count) for manual count input
 *
 * drawer fields that affect rendering:
 *  status          — 'empty' | 'partial' | 'full' | 'reserved' | 'unknown'
 *  highlighted     — true when auto-allocation targets this drawer
 *  allocationCount — count badge for auto-allocation
 *  manualSelected  — true when user has clicked this drawer in manual mode
 *  manualCount     — number entered in manual count input
 *  searchMatch     — true when this drawer contains a lookup result
 *  matchCount      — number of matching containers in this drawer
 */
function DrawerCell({ drawer, mode, onManualSelect, onSetCount }) {
  const {
    coord, status, usedCount, capacity, reserved,
    highlighted, allocationCount,
    manualSelected, manualCount,
    searchMatch, matchCount,
  } = drawer;

  const shortCoord = coord.split('-').slice(1).join('-');

  // ── Base colour class (occupancy) ─────────────────────────────────────────
  // searchMatch does NOT override the base colour — it adds a ring on top.
  // This lets a partially-full drawer remain yellow while also being highlighted.
  let cellClass = 'drawer-cell';

  if (reserved)                  cellClass += ' drawer-reserved';
  else if (highlighted)          cellClass += ' drawer-allocated';
  else if (manualSelected)       cellClass += ' drawer-manual';
  else if (status === 'empty')   cellClass += ' drawer-empty';
  else if (status === 'partial') cellClass += ' drawer-partial';
  else if (status === 'full')    cellClass += ' drawer-full';
  else                           cellClass += ' drawer-unknown';

  // searchMatch adds a separate ring class — layered on top of any base colour
  if (searchMatch) cellClass += ' drawer-search-match';

  const isClickable = mode === 'manual' && !reserved;

  function handleClick() {
    if (isClickable) onManualSelect(coord);
  }

  return (
    <div
      className={cellClass + (isClickable ? ' drawer-clickable' : '')}
      onClick={handleClick}
      title={coord}
    >
      <span className="drawer-coord">{shortCoord}</span>

      {/* Auto-allocation badge */}
      {highlighted && allocationCount != null && (
        <span className="drawer-badge drawer-badge-auto">+{allocationCount}</span>
      )}

      {/* Search match badge — shown on top of occupancy colour */}
      {searchMatch && matchCount != null && (
        <span className="drawer-badge drawer-badge-search">{matchCount}</span>
      )}

      {/* Occupancy indicator */}
      {usedCount != null && capacity != null && (
        <span className="drawer-usage">{usedCount}/{capacity}</span>
      )}

      {/* Manual count input */}
      {manualSelected && mode === 'manual' && (
        <input
          type="number"
          min={0}
          className="drawer-count-input"
          value={manualCount || ''}
          onClick={e => e.stopPropagation()}
          onChange={e => onSetCount(coord, parseInt(e.target.value, 10) || 0)}
          placeholder="n"
        />
      )}
    </div>
  );
}

export default React.memo(DrawerCell);

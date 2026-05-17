# Freezer Management System — Frontend

React + Bootstrap frontend for the Freezer Management System.

## Project Structure

```
src/
├── api/
│   └── index.js                  ← All Axios API calls
├── hooks/
│   └── useFreezer.js             ← Freezer state, grid builder, overlay logic
├── components/
│   ├── freezer/
│   │   ├── DrawerCell.jsx        ← Single drawer unit (colour, badges, input)
│   │   └── FreezerGrid.jsx       ← Full grid (FreezerGrid → LayerView → RackView → DrawerCell)
│   └── forms/
│       ├── StudySampleForm.jsx   ← Study name + barcode scanner input
│       ├── STDQCForm.jsx         ← Prep ID (validated) + container count
│       ├── AllocationPanel.jsx   ← Auto-allocation summary + commit
│       └── ManualAssignmentPanel.jsx ← Manual selection summary + confirm
├── pages/
│   ├── HomePage.jsx              ← Landing page with 3 action buttons
│   └── ContainerIntroductionPage.jsx ← Full introduction workflow
├── App.js                        ← React Router setup
├── styles.css                    ← Global CSS (IBM Plex, navy/teal theme)
└── index.js                      ← Entry point
```

## Setup

```bash
npm install
REACT_APP_API_URL=http://localhost:8000/api/v1 npm start
```

The `REACT_APP_API_URL` env var defaults to `http://localhost:8000/api/v1`.

## Known TODOs

1. **Drawer occupancy** — the backend has no `GET /freezers/{id}/drawers` endpoint yet.
   The grid renders all drawers as `unknown` (dark blue). Once such an endpoint exists,
   update `useFreezer.selectFreezer` to fetch real occupancy and colour drawers correctly.

2. **Manual assignment drawer_id** — `ManualAssignmentPanel` and the manual confirm flow
   in `ContainerIntroductionPage` currently use `d.drawerNum` (the 1-based drawer number
   within the rack) as `drawer_id`. This is WRONG — the backend expects the integer
   primary key from the `drawer` table. Fix once the drawer-state endpoint returns real
   `drawer_id` values per coordinate.

3. **Retrieval and Lookup pages** — stubbed as placeholders, pending backend route readiness.

4. **Admin page** — placeholder, to be implemented with RBAC.
```

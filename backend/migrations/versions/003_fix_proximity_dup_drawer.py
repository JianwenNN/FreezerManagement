"""Fix duplicate-drawer bug in allocate_containers_in_proximity

Revision ID: 003_fix_proximity_dup_drawer
Revises: 002_add_drawer_reservation
Create Date: 2026-06-25 00:00:00.000000

Why this migration exists
--------------------------
allocate_containers_in_proximity() can run multiple loop iterations
within a SINGLE function call when one drawer isn't enough to hold
the full request. Drawer selection inside that loop relies on
available_space_in_drawer(), which reads live DB state (actual
container rows + active drawer_reservation rows).

The bug: reservations for a suggestion are only written by the caller
(containers.py) AFTER this function returns its full result set. So
within the function's own loop, a drawer it just "virtually" filled in
iteration N still looks completely empty to available_space_in_drawer()
in iteration N+1 — because nothing has actually been persisted yet.
Result: the same drawer can be returned twice in one suggestion
(e.g. requesting 12 STD/QC containers into an 8-capacity drawer
allocates 8 from drawer X, then 4 AGAIN from the same drawer X
instead of moving to a second drawer).

Fix: track drawer_ids already consumed within the current function
call in a local array (used_drawer_ids) and exclude them from every
subsequent drawer/rack selection query, instead of relying solely on
available_space_in_drawer()'s live-DB view.

This migration simply re-creates the function (CREATE OR REPLACE) with
the corrected body — no schema/table changes, no data migration needed.
"""

import os
from alembic import op


# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision      = '003_fix_proximity_dup_drawer'
down_revision = '002_add_drawer_reservation'
branch_labels = None
depends_on    = None


# ---------------------------------------------------------------------------
# Helper (same pattern as 001_initial_schema.py)
# ---------------------------------------------------------------------------
def _load_sql(relative_path: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base, "..", "..", "app", "sql", *relative_path.split("/"))
    with open(full_path) as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # CREATE OR REPLACE — swaps the function body in place, no DROP needed.
    op.execute(_load_sql("functions/allocate_containers_in_proximity.sql"))


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:
    # Revert to the pre-fix version of the function (re-introduces the bug —
    # only intended for rolling back this specific change, not recommended
    # to run in practice).
    op.execute("""
        CREATE OR REPLACE FUNCTION allocate_containers_in_proximity(
            p_container_count  INTEGER,
            p_sample_type      VARCHAR,
            p_freezer_asset_id VARCHAR
        )
        RETURNS TABLE (
            drawer_id         INTEGER,
            drawer_coordinate TEXT,
            container_count   INTEGER,
            remaining_count   INTEGER
        ) AS $$
        DECLARE
            remaining          INTEGER := p_container_count;
            current_rack_id    INTEGER := NULL;
            current_layer_id   INTEGER := NULL;
            current_freezer_id INTEGER;
            v_drawer_id        INTEGER;
            v_coord            TEXT;
            v_capacity         INTEGER;
            container_fit      INTEGER;
            allocated          INTEGER;
        BEGIN
            SELECT id INTO current_freezer_id
            FROM   freezer
            WHERE  asset_id = p_freezer_asset_id;

            IF current_freezer_id IS NULL THEN
                RAISE EXCEPTION 'Freezer with asset_id % not found', p_freezer_asset_id;
            END IF;

            IF p_sample_type = 'study_sample_container' THEN
                SELECT study_sample_capacity INTO v_capacity
                FROM   freezer WHERE id = current_freezer_id;
            ELSIF p_sample_type = 'stdqc_container' THEN
                SELECT stdqc_capacity INTO v_capacity
                FROM   freezer WHERE id = current_freezer_id;
            ELSE
                RAISE EXCEPTION 'Unknown sample type: %', p_sample_type;
            END IF;

            IF v_capacity IS NULL OR v_capacity <= 0 THEN
                RAISE EXCEPTION
                    'Freezer % has no capacity defined for sample type %',
                    p_freezer_asset_id, p_sample_type;
            END IF;

            WHILE remaining > 0 LOOP
                IF current_rack_id IS NULL THEN
                    SELECT r.id, r.layer_id
                    INTO   current_rack_id, current_layer_id
                    FROM   drawer d
                    JOIN   rack  r ON d.rack_id  = r.id
                    JOIN   layer l ON r.layer_id = l.id
                    WHERE  l.freezer_id = current_freezer_id
                      AND  d.reserved   = FALSE
                      AND  available_space_in_drawer(d.id, p_sample_type) > 0
                    GROUP  BY r.id, r.layer_id
                    ORDER  BY SUM(available_space_in_drawer(d.id, p_sample_type)) DESC
                    LIMIT  1;

                    IF current_rack_id IS NULL THEN
                        EXIT;
                    END IF;
                END IF;

                SELECT d.id,
                       available_space_in_drawer(d.id, p_sample_type)
                INTO   v_drawer_id, container_fit
                FROM   drawer d
                WHERE  d.rack_id  = current_rack_id
                  AND  d.reserved = FALSE
                  AND  available_space_in_drawer(d.id, p_sample_type) > 0
                ORDER  BY available_space_in_drawer(d.id, p_sample_type) DESC
                LIMIT  1;

                IF v_drawer_id IS NULL THEN
                    SELECT r.id
                    INTO   current_rack_id
                    FROM   drawer d
                    JOIN   rack r ON d.rack_id = r.id
                    WHERE  r.layer_id = current_layer_id
                      AND  r.id      != current_rack_id
                      AND  d.reserved = FALSE
                      AND  available_space_in_drawer(d.id, p_sample_type) > 0
                    GROUP  BY r.id
                    ORDER  BY SUM(available_space_in_drawer(d.id, p_sample_type)) DESC
                    LIMIT  1;

                    IF current_rack_id IS NULL THEN
                        SELECT l.id INTO current_layer_id
                        FROM   layer l
                        WHERE  l.freezer_id = current_freezer_id
                          AND  l.id        != current_layer_id
                          AND  EXISTS (
                                   SELECT 1 FROM drawer d
                                   JOIN   rack r ON d.rack_id = r.id
                                   WHERE  r.layer_id = l.id
                                     AND  d.reserved  = FALSE
                                     AND  available_space_in_drawer(d.id, p_sample_type) > 0
                               )
                        ORDER  BY l.layer_number
                        LIMIT  1;

                        IF current_layer_id IS NULL THEN
                            EXIT;
                        END IF;

                        current_rack_id := NULL;
                    END IF;

                    CONTINUE;
                END IF;

                allocated := LEAST(container_fit, remaining);
                remaining := remaining - allocated;

                SELECT dc.drawer_coordinate INTO v_coord
                FROM   drawer_coordinates dc
                WHERE  dc.drawer_id = v_drawer_id;

                drawer_id         := v_drawer_id;
                drawer_coordinate := v_coord;
                container_count   := allocated;
                remaining_count   := remaining;

                RETURN NEXT;

                IF remaining <= 0 THEN
                    EXIT;
                END IF;
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)

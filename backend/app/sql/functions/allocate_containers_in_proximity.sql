CREATE OR REPLACE FUNCTION allocate_containers_in_proximity(
    p_container_count  INTEGER,
    p_sample_type      VARCHAR,   -- 'study_sample_container' or 'stdqc_container'
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
    used_drawer_ids    INTEGER[] := ARRAY[]::INTEGER[];  -- drawers already
                                                          -- consumed *within
                                                          -- this call*. The
                                                          -- DB itself doesn't
                                                          -- reflect these yet
                                                          -- (reservations are
                                                          -- written by the
                                                          -- caller AFTER this
                                                          -- function returns),
                                                          -- so we can't rely
                                                          -- on available_space_
                                                          -- in_drawer() alone
                                                          -- to avoid re-picking
                                                          -- the same drawer.
BEGIN
    -- Resolve freezer integer id from asset_id
    SELECT id INTO current_freezer_id
    FROM   freezer
    WHERE  asset_id = p_freezer_asset_id;

    IF current_freezer_id IS NULL THEN
        RAISE EXCEPTION 'Freezer with asset_id % not found', p_freezer_asset_id;
    END IF;

    -- Verify this freezer has a non-zero capacity for the requested sample type.
    -- Capacity is stored directly on the freezer row (no separate capacity table).
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

    -- -----------------------------------------------------------------------
    -- Main allocation loop: runs until all containers are placed or the
    -- freezer is exhausted.
    -- -----------------------------------------------------------------------
    WHILE remaining > 0 LOOP

        -- -------------------------------------------------------------------
        -- Step 1: pick the rack with the most total available space.
        --
        -- available_space_in_drawer() handles all exclusion logic:
        --   - reserved drawers       → returns 0
        --   - wrong-type drawers     → returns 0
        --   - partially filled       → returns remainder
        --   - empty drawers          → returns full capacity
        --
        -- We additionally exclude any drawer_id already in used_drawer_ids,
        -- since available_space_in_drawer() can't see allocations this same
        -- function call has already decided on but not yet persisted.
        --
        -- Only re-runs when current_rack_id is NULL (cleared by escalation).
        -- -------------------------------------------------------------------
        IF current_rack_id IS NULL THEN
            SELECT r.id, r.layer_id
            INTO   current_rack_id, current_layer_id
            FROM   drawer d
            JOIN   rack  r ON d.rack_id  = r.id
            JOIN   layer l ON r.layer_id = l.id
            WHERE  l.freezer_id = current_freezer_id
              AND  d.reserved   = FALSE
              AND  NOT (d.id = ANY(used_drawer_ids))
              AND  available_space_in_drawer(d.id, p_sample_type) > 0
            GROUP  BY r.id, r.layer_id
            ORDER  BY SUM(available_space_in_drawer(d.id, p_sample_type)) DESC
            LIMIT  1;

            IF current_rack_id IS NULL THEN
                RAISE NOTICE 'No available space remaining in freezer %', p_freezer_asset_id;
                EXIT;
            END IF;
        END IF;

        -- -------------------------------------------------------------------
        -- Step 2: within the chosen rack, pick the drawer with the most room.
        -- -------------------------------------------------------------------
        SELECT d.id,
               available_space_in_drawer(d.id, p_sample_type)
        INTO   v_drawer_id, container_fit
        FROM   drawer d
        WHERE  d.rack_id  = current_rack_id
          AND  d.reserved = FALSE
          AND  NOT (d.id = ANY(used_drawer_ids))
          AND  available_space_in_drawer(d.id, p_sample_type) > 0
        ORDER  BY available_space_in_drawer(d.id, p_sample_type) DESC
        LIMIT  1;

        -- -------------------------------------------------------------------
        -- Step 3 (escalation): no usable drawer in this rack.
        --   Try the next best rack in the same layer,
        --   then the next layer in the same freezer (clearing current_rack_id
        --   so Step 1 picks the best rack in that layer on the next iteration),
        --   then give up.
        -- -------------------------------------------------------------------
        IF v_drawer_id IS NULL THEN

            -- Try another rack in the same layer, picking the one with the
            -- most total available space (not just the next by rack_number).
            SELECT r.id
            INTO   current_rack_id
            FROM   drawer d
            JOIN   rack r ON d.rack_id = r.id
            WHERE  r.layer_id = current_layer_id
              AND  r.id      != current_rack_id
              AND  d.reserved = FALSE
              AND  NOT (d.id = ANY(used_drawer_ids))
              AND  available_space_in_drawer(d.id, p_sample_type) > 0
            GROUP  BY r.id
            ORDER  BY SUM(available_space_in_drawer(d.id, p_sample_type)) DESC
            LIMIT  1;

            IF current_rack_id IS NULL THEN
                -- No more racks in this layer — try the next layer.
                -- Clear current_rack_id so Step 1 picks the best rack
                -- in the new layer on the next loop iteration.
                SELECT l.id INTO current_layer_id
                FROM   layer l
                WHERE  l.freezer_id = current_freezer_id
                  AND  l.id        != current_layer_id
                  AND  EXISTS (
                           SELECT 1 FROM drawer d
                           JOIN   rack r ON d.rack_id = r.id
                           WHERE  r.layer_id = l.id
                             AND  d.reserved  = FALSE
                             AND  NOT (d.id = ANY(used_drawer_ids))
                             AND  available_space_in_drawer(d.id, p_sample_type) > 0
                       )
                ORDER  BY l.layer_number
                LIMIT  1;

                IF current_layer_id IS NULL THEN
                    RAISE NOTICE 'No more available space in freezer %', p_freezer_asset_id;
                    EXIT;
                END IF;

                -- Clear rack so Step 1 selects the best rack in the new layer
                current_rack_id := NULL;
            END IF;

            CONTINUE;  -- re-enter loop with updated rack or cleared rack
        END IF;

        -- -------------------------------------------------------------------
        -- Step 4: allocate — fill this drawer as much as possible, emit a
        --         result row, and subtract from remaining. Record the
        --         drawer as used so it can never be selected again within
        --         this same function call.
        -- -------------------------------------------------------------------
        allocated := LEAST(container_fit, remaining);
        remaining := remaining - allocated;
        used_drawer_ids := array_append(used_drawer_ids, v_drawer_id);

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

    IF remaining > 0 THEN
        RAISE NOTICE 'Could not allocate all containers. Still unplaced: %', remaining;
    END IF;
END;
$$ LANGUAGE plpgsql;

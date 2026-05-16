CREATE OR REPLACE FUNCTION available_space_in_drawer(
    p_drawer_id   INTEGER,
    p_sample_type VARCHAR   -- 'study_sample_container' or 'stdqc_container'
)
RETURNS INTEGER AS $$
DECLARE
    v_study_capacity   INTEGER;
    v_stdqc_capacity   INTEGER;
    v_max_capacity     INTEGER;
    v_current_count    INTEGER;
    v_other_count      INTEGER;
    v_reserved_count   INTEGER;
BEGIN
    -- Read both capacity columns in a single JOIN traversal.
    -- drawer → rack → layer → freezer
    SELECT f.study_sample_capacity,
           f.stdqc_capacity
    INTO   v_study_capacity,
           v_stdqc_capacity
    FROM   drawer d
    JOIN   rack  r ON d.rack_id  = r.id
    JOIN   layer l ON r.layer_id = l.id
    JOIN   freezer f ON l.freezer_id = f.id
    WHERE  d.id = p_drawer_id;

    IF v_study_capacity IS NULL THEN
        RETURN 0;   -- drawer not found
    END IF;

    -- Select the relevant capacity for the requested sample type
    IF p_sample_type = 'study_sample_container' THEN
        v_max_capacity := v_study_capacity;
    ELSIF p_sample_type = 'stdqc_container' THEN
        v_max_capacity := v_stdqc_capacity;
    ELSE
        RETURN 0;
    END IF;

    -- A drawer is locked to whichever type was placed first.
    -- If the OTHER type already occupies this drawer, return 0.
    IF p_sample_type = 'study_sample_container' THEN
        SELECT COUNT(*) INTO v_other_count
        FROM   stdqc_container
        WHERE  drawer_id = p_drawer_id;
    ELSE
        SELECT COUNT(*) INTO v_other_count
        FROM   study_sample_container
        WHERE  drawer_id = p_drawer_id;
    END IF;

    IF v_other_count > 0 THEN
        RETURN 0;
    END IF;

    -- Count containers already placed of the requested type
    IF p_sample_type = 'study_sample_container' THEN
        SELECT COUNT(*) INTO v_current_count
        FROM   study_sample_container
        WHERE  drawer_id = p_drawer_id;
    ELSE
        SELECT COUNT(*) INTO v_current_count
        FROM   stdqc_container
        WHERE  drawer_id = p_drawer_id;
    END IF;

    -- Sum active (non-expired) reservations for this drawer and sample type.
    -- These represent space promised to other users who haven't confirmed yet.
    -- Expired reservations are excluded — they no longer hold any space.
    SELECT COALESCE(SUM(reserved_count), 0)
    INTO   v_reserved_count
    FROM   drawer_reservation
    WHERE  drawer_id   = p_drawer_id
      AND  sample_type = p_sample_type
      AND  expires_at  > NOW();

    -- effective_available = capacity - actual containers - active reservations
    RETURN GREATEST(0, v_max_capacity - v_current_count - v_reserved_count);
END;
$$ LANGUAGE plpgsql;

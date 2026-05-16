CREATE OR REPLACE FUNCTION check_stdqc_container_capacity()
RETURNS TRIGGER AS $$
DECLARE
    v_max_capacity  INTEGER;
    v_current_count INTEGER;
    v_other_count   INTEGER;
BEGIN
    -- Reject if this drawer already contains study sample containers
    SELECT COUNT(*) INTO v_other_count
    FROM   study_sample_container
    WHERE  drawer_id = NEW.drawer_id;

    IF v_other_count > 0 THEN
        RAISE EXCEPTION
            'Drawer % already contains study sample containers and cannot accept STDQC containers.',
            NEW.drawer_id;
    END IF;

    -- Read STDQC capacity directly from the freezer row
    SELECT f.stdqc_capacity
    INTO   v_max_capacity
    FROM   drawer d
    JOIN   rack  r ON d.rack_id  = r.id
    JOIN   layer l ON r.layer_id = l.id
    JOIN   freezer f ON l.freezer_id = f.id
    WHERE  d.id = NEW.drawer_id;

    -- Count existing STDQC containers in this drawer
    SELECT COUNT(*) INTO v_current_count
    FROM   stdqc_container
    WHERE  drawer_id = NEW.drawer_id;

    IF v_current_count >= v_max_capacity THEN
        RAISE EXCEPTION
            'Drawer % is full: % of % STDQC containers already placed.',
            NEW.drawer_id, v_current_count, v_max_capacity;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION check_study_sample_container_capacity()
RETURNS TRIGGER AS $$
DECLARE
    v_max_capacity  INTEGER;
    v_current_count INTEGER;
    v_other_count   INTEGER;
BEGIN
    -- Reject if this drawer already contains STDQC containers
    SELECT COUNT(*) INTO v_other_count
    FROM   stdqc_container
    WHERE  drawer_id = NEW.drawer_id;

    IF v_other_count > 0 THEN
        RAISE EXCEPTION
            'Drawer % already contains STDQC containers and cannot accept study sample containers.',
            NEW.drawer_id;
    END IF;

    -- Read study sample capacity directly from the freezer row
    SELECT f.study_sample_capacity
    INTO   v_max_capacity
    FROM   drawer d
    JOIN   rack  r ON d.rack_id  = r.id
    JOIN   layer l ON r.layer_id = l.id
    JOIN   freezer f ON l.freezer_id = f.id
    WHERE  d.id = NEW.drawer_id;

    -- Count existing study sample containers in this drawer
    SELECT COUNT(*) INTO v_current_count
    FROM   study_sample_container
    WHERE  drawer_id = NEW.drawer_id;

    IF v_current_count >= v_max_capacity THEN
        RAISE EXCEPTION
            'Drawer % is full: % of % study sample containers already placed.',
            NEW.drawer_id, v_current_count, v_max_capacity;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

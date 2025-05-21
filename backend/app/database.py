from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from sqlalchemy import text

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/freezer_management"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to use in FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create drawer coordinates view
def create_drawer_coordinates_view():
    view_sql = """
    CREATE OR REPLACE VIEW drawer_coordinates AS
    SELECT 
        d.id AS drawer_id,
        f.asset_id AS freezer_asset_id,
        l.layer_number,
        r.rack_number,
        d.drawer_number,
        CONCAT(f.asset_id, '-', l.layer_number, '-', r.rack_number, '-', d.drawer_number) AS drawer_coordinate,
        d.reserved,
        d.reserved_reason
    FROM 
        drawer d
    JOIN rack r ON d.rack_id = r.id
    JOIN layer l ON r.layer_id = l.id
    JOIN freezer f ON l.freezer_id = f.id;
    """
    with engine.begin() as conn:
        conn.execute(text(view_sql))

# Function to create capacity check function and triggers
def create_capacity_check_functions():
    # Inside create_capacity_check_functions()
    # Inside create_capacity_check_functions()
    capacity_check_sql = """
    CREATE OR REPLACE FUNCTION check_study_sample_container_capacity() RETURNS TRIGGER AS $$
    DECLARE
        drawer_type INTEGER;
        container_type INTEGER;
        current_count INTEGER;
        max_capacity INTEGER;
    BEGIN
        SELECT NEW.container_type_id, d.drawer_type_id
        INTO container_type, drawer_type
        FROM drawer d
        WHERE d.id = NEW.drawer_id;
        
        SELECT COUNT(*) INTO current_count
        FROM study_sample_container
        WHERE drawer_id = NEW.drawer_id
        AND container_type_id = container_type;
        
        SELECT max_capacity INTO max_capacity
        FROM drawer_capacity
        WHERE drawer_type_id = drawer_type AND container_type_id = container_type;
        
        IF current_count >= max_capacity THEN
            RAISE EXCEPTION 'Drawer capacity exceeded (% study sample containers of type %, maximum is %)', 
                            current_count, container_type, max_capacity;
        END IF;
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION check_stdqc_container_capacity() RETURNS TRIGGER AS $$
    DECLARE
        drawer_type INTEGER;
        container_type INTEGER;
        current_count INTEGER;
        max_capacity INTEGER;
    BEGIN
        SELECT NEW.container_type_id, d.drawer_type_id
        INTO container_type, drawer_type
        FROM drawer d
        WHERE d.id = NEW.drawer_id;
        
        SELECT COUNT(*) INTO current_count
        FROM stdqc_container
        WHERE drawer_id = NEW.drawer_id
        AND container_type_id = container_type;
        
        SELECT max_capacity INTO max_capacity
        FROM drawer_capacity
        WHERE drawer_type_id = drawer_type AND container_type_id = container_type;
        
        IF current_count >= max_capacity THEN
            RAISE EXCEPTION 'Drawer capacity exceeded (% STDQC containers of type %, maximum is %)', 
                            current_count, container_type, max_capacity;
        END IF;
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- Update your triggers to new tables
    DROP TRIGGER IF EXISTS enforce_study_samples_capacity ON study_sample_container;
    DROP TRIGGER IF EXISTS enforce_stdqc_samples_capacity ON stdqc_container;

    CREATE TRIGGER enforce_study_samples_capacity
    BEFORE INSERT ON study_sample_container
    FOR EACH ROW EXECUTE FUNCTION check_study_sample_container_capacity();

    CREATE TRIGGER enforce_stdqc_samples_capacity
    BEFORE INSERT ON stdqc_container
    FOR EACH ROW EXECUTE FUNCTION check_stdqc_container_capacity();
    """

    with engine.begin() as conn:
        conn.execute(text(capacity_check_sql))

def create_available_space_function():
    helper_function_sql = """
    CREATE OR REPLACE FUNCTION available_space_in_drawer(
        p_drawer_id INTEGER, 
        p_container_type_id INTEGER,
        p_sample_type VARCHAR
    )
    RETURNS INTEGER AS $$
    DECLARE
        max_capacity INTEGER;
        current_count INTEGER;
        drawer_type INTEGER;
        is_reserved BOOLEAN;
    BEGIN
        -- Check if drawer is reserved
        SELECT reserved INTO is_reserved
        FROM drawer
        WHERE id = p_drawer_id;
        
        IF is_reserved THEN
            RETURN 0;
        END IF;
        
        -- Get drawer type and max capacity
        SELECT d.drawer_type_id, dc.max_capacity
        INTO drawer_type, max_capacity
        FROM drawer d
        JOIN drawer_capacity dc 
        ON d.drawer_type_id = dc.drawer_type_id
        AND dc.container_type_id = p_container_type_id
        WHERE d.id = p_drawer_id;

        -- Count containers based on sample type
        IF p_sample_type = 'study_sample_container' THEN
            SELECT COUNT(*) INTO current_count
            FROM study_sample_container
            WHERE drawer_id = p_drawer_id
            AND container_type_id = p_container_type_id;
        ELSIF p_sample_type = 'stdqc_container' THEN
            SELECT COUNT(*) INTO current_count
            FROM stdqc_container
            WHERE drawer_id = p_drawer_id
            AND container_type_id = p_container_type_id;
        END IF;

        -- Return available space
        RETURN max_capacity - current_count;
    END;
    $$ LANGUAGE plpgsql;
    """
    with engine.begin() as conn:
        conn.execute(text(helper_function_sql))

def create_allocation_function():
    allocation_function_sql = """
    CREATE OR REPLACE FUNCTION allocate_containers_in_proximity(
        p_container_type_id INTEGER,
        p_container_count INTEGER,
        p_sample_type VARCHAR,
        p_freezer_asset_id VARCHAR
    ) RETURNS TABLE (
        drawer_id INTEGER,
        drawer_coordinate TEXT,
        container_count INTEGER,
        remaining_count INTEGER
    ) AS $$
    DECLARE
        total_to_allocate INTEGER := p_container_count;
        remaining INTEGER := p_container_count;
        max_capacity INTEGER;
        single_drawer_id INTEGER;
        current_rack_id INTEGER := NULL;
        current_layer_id INTEGER := NULL;
        container_fit INTEGER;
        drawer_id INTEGER;
        drawer_coordinate TEXT;
    BEGIN
        -- First get the maximum capacity for this container type
        SELECT max_capacity INTO max_capacity
        FROM drawer_capacity dc
        JOIN drawer_type dt ON dc.drawer_type_id = dt.id
        WHERE dc.container_type_id = p_container_type_id
        ORDER BY max_capacity DESC
        LIMIT 1;
        
        -- Check if the requested number is within maximum drawer capacity
        IF p_container_count <= max_capacity THEN
            -- Try to find the best fitting drawer (smallest capacity that fits all) in the specified freezer
            WITH drawer_space AS (
                SELECT 
                    d.id AS drawer_id,
                    dc.max_capacity,
                    CASE 
                        WHEN p_sample_type = 'study_sample_container' THEN 
                            (SELECT COUNT(*) FROM study_sample_container 
                            WHERE drawer_id = d.id AND container_type_id = p_container_type_id)
                        WHEN p_sample_type = 'stdqc_container' THEN 
                            (SELECT COUNT(*) FROM stdqc_container 
                            WHERE drawer_id = d.id AND container_type_id = p_container_type_id)
                        ELSE 0
                    END AS current_count
                FROM drawer d
                JOIN rack r ON d.rack_id = r.id
                JOIN layer l ON r.layer_id = l.id
                JOIN freezer f ON l.freezer_id = f.id
                JOIN drawer_capacity dc ON d.drawer_type_id = dc.drawer_type_id 
                                      AND dc.container_type_id = p_container_type_id
                WHERE d.reserved = FALSE
                AND f.asset_id = p_freezer_asset_id
            )
            SELECT drawer_id INTO single_drawer_id
            FROM drawer_space
            WHERE (max_capacity - current_count) >= p_container_count
            ORDER BY (max_capacity - current_count - p_container_count) ASC  -- Choose most efficient fit
            LIMIT 1;
            
            -- If found a suitable drawer
            IF single_drawer_id IS NOT NULL THEN
                -- Get drawer coordinates
                SELECT drawer_coordinate INTO drawer_coordinate
                FROM drawer_coordinates
                WHERE drawer_id = single_drawer_id;
                
                -- Return a single allocation record
                drawer_id := single_drawer_id;
                container_count := remaining;
                remaining := 0;
                RETURN NEXT;
                RETURN;
            END IF;
        END IF;
        
        -- If we got here, we need to split the containers across multiple drawers
        -- but still stay within the specified freezer
        
        -- NOTE: We no longer define the helper function here, we just use it
        
        -- Allocate across multiple drawers in the specified freezer
        -- First, try to find a layer with maximum available space
        WITH layer_availability AS (
            SELECT l.id AS layer_id, 
                SUM(available_space_in_drawer(d.id, p_container_type_id, p_sample_type)) AS total_space
            FROM drawer d
            JOIN rack r ON d.rack_id = r.id
            JOIN layer l ON r.layer_id = l.id
            JOIN freezer f ON l.freezer_id = f.id
            WHERE f.asset_id = p_freezer_asset_id
            AND available_space_in_drawer(d.id, p_container_type_id, p_sample_type) > 0
            GROUP BY l.id
            ORDER BY total_space DESC
            LIMIT 1
        )
        SELECT layer_id INTO current_layer_id
        FROM layer_availability;

        -- If no layer found, exit (not enough space in the freezer)
        IF current_layer_id IS NULL THEN
            RAISE NOTICE 'No available space in the specified freezer';
            RETURN;
        END IF;

        -- Now allocate within the chosen layer first, then try other layers in the same freezer
        WHILE remaining > 0 LOOP
            IF current_rack_id IS NULL THEN
                -- Find a rack with maximum available space in the current layer
                WITH rack_availability AS (
                    SELECT r.id AS rack_id,
                        SUM(available_space_in_drawer(d.id, p_container_type_id, p_sample_type)) AS total_space
                    FROM drawer d
                    JOIN rack r ON d.rack_id = r.id
                    WHERE r.layer_id = current_layer_id
                    AND available_space_in_drawer(d.id, p_container_type_id, p_sample_type) > 0
                    GROUP BY r.id
                    ORDER BY total_space DESC
                    LIMIT 1
                )
                SELECT rack_id INTO current_rack_id
                FROM rack_availability;

                -- If no rack found in this layer, try another layer in the same freezer
                IF current_rack_id IS NULL THEN
                    -- Find another layer in the same freezer
                    WITH freezer_layers AS (
                        SELECT l.id FROM layer l
                        JOIN freezer f ON l.freezer_id = f.id
                        WHERE f.asset_id = p_freezer_asset_id
                        AND l.id != current_layer_id
                        ORDER BY l.layer_number
                        LIMIT 1
                    )
                    SELECT id INTO current_layer_id FROM freezer_layers;

                    -- If no other layer available, exit
                    IF current_layer_id IS NULL THEN
                        RAISE NOTICE 'Unable to allocate all containers in the specified freezer';
                        EXIT;
                    END IF;
                    CONTINUE;
                END IF;
            END IF;

            -- Find drawer with most available space in current rack
            WITH drawer_info AS (
                SELECT d.id AS drawer_id,
                    available_space_in_drawer(d.id, p_container_type_id, p_sample_type) AS available_space
                FROM drawer d
                WHERE d.rack_id = current_rack_id
                AND available_space_in_drawer(d.id, p_container_type_id, p_sample_type) > 0
                ORDER BY available_space DESC
                LIMIT 1
            )
            SELECT drawer_id, available_space INTO drawer_id, container_fit
            FROM drawer_info;

            -- If no drawer found in this rack, move to another rack in same layer
            IF drawer_id IS NULL THEN
                current_rack_id := NULL;
                -- Find another rack in the same layer
                WITH layer_racks AS (
                    SELECT id FROM rack 
                    WHERE layer_id = current_layer_id 
                    AND id != current_rack_id
                    ORDER BY rack_number
                    LIMIT 1
                )
                SELECT id INTO current_rack_id FROM layer_racks;

                -- If no other rack in this layer, this will trigger finding another layer in the next iteration
                IF current_rack_id IS NULL THEN
                    current_layer_id := NULL;
                END IF;
                CONTINUE;
            END IF;

            -- Allocate containers to this drawer
            container_count := LEAST(container_fit, remaining);
            remaining := remaining - container_count;

            -- Get drawer coordinates
            SELECT drawer_coordinate INTO drawer_coordinate
            FROM drawer_coordinates
            WHERE drawer_id = drawer_id;

            -- Return this allocation
            RETURN NEXT;

            -- Exit if all containers have been allocated
            IF remaining <= 0 THEN
                EXIT;
            END IF;
        END LOOP;
        
        -- NOTE: We removed the DROP FUNCTION line since the helper function is now permanent
        
        -- If still remaining containers, raise a notice
        IF remaining > 0 THEN
            RAISE NOTICE 'Unable to allocate all containers in the specified freezer. Remaining: %', remaining;
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """
    with engine.begin() as conn:
        conn.execute(text(allocation_function_sql))

# Initialize database functions
def init_db_functions():
    create_drawer_coordinates_view()
    create_capacity_check_functions()
    create_available_space_function()
    create_allocation_function()
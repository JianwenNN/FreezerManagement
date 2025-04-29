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

# Function to create sample allocation function
def create_allocation_function():
    allocation_function_sql = """
    CREATE OR REPLACE FUNCTION find_drawer_for_containers(
        p_study_name VARCHAR,
        p_container_type_id INTEGER,
        p_sample_type VARCHAR
    ) RETURNS INTEGER AS $$
    DECLARE
        drawer_id INTEGER;
    BEGIN
        -- Look for drawer with the same study first (for study samples only)
        IF p_sample_type = 'study_sample_container' THEN
            WITH study_drawers AS (
                SELECT DISTINCT drawer_id
                FROM study_sample_container
                WHERE study_name = p_study_name
            ),
            drawer_counts AS (
                SELECT 
                    d.id AS drawer_id,
                    COUNT(ssc.id) AS container_count,
                    dc.max_capacity
                FROM drawer d
                JOIN drawer_capacity dc ON d.drawer_type_id = dc.drawer_type_id AND dc.container_type_id = p_container_type_id
                LEFT JOIN study_sample_container ssc ON d.id = ssc.drawer_id AND ssc.container_type_id = p_container_type_id
                WHERE d.reserved = FALSE  -- Exclude reserved drawers
                GROUP BY d.id, dc.max_capacity
            )
            
            SELECT dc.drawer_id INTO drawer_id
            FROM drawer_counts dc
            JOIN study_drawers sd ON dc.drawer_id = sd.drawer_id
            WHERE dc.container_count < dc.max_capacity
            ORDER BY (dc.max_capacity - dc.container_count) DESC
            LIMIT 1;
        END IF;
        
        IF drawer_id IS NULL THEN
            IF p_sample_type = 'study_sample_container' THEN
                WITH drawer_counts AS (
                    SELECT 
                        d.id AS drawer_id,
                        COUNT(ssc.id) AS container_count,
                        dc.max_capacity
                    FROM drawer d
                    JOIN drawer_capacity dc ON d.drawer_type_id = dc.drawer_type_id AND dc.container_type_id = p_container_type_id
                    LEFT JOIN study_sample_container ssc ON d.id = ssc.drawer_id AND ssc.container_type_id = p_container_type_id
                    WHERE d.reserved = FALSE  -- Exclude reserved drawers
                    GROUP BY d.id, dc.max_capacity
                )
                SELECT drawer_id INTO drawer_id
                FROM drawer_counts
                WHERE container_count < max_capacity
                ORDER BY (max_capacity - container_count) DESC
                LIMIT 1;
            ELSIF p_sample_type = 'stdqc_container' THEN
                WITH drawer_counts AS (
                    SELECT 
                        d.id AS drawer_id,
                        COUNT(sqc.id) AS container_count,
                        dc.max_capacity
                    FROM drawer d
                    JOIN drawer_capacity dc ON d.drawer_type_id = dc.drawer_type_id AND dc.container_type_id = p_container_type_id
                    LEFT JOIN stdqc_container sqc ON d.id = sqc.drawer_id AND sqc.container_type_id = p_container_type_id
                    WHERE d.reserved = FALSE  -- Exclude reserved drawers
                    GROUP BY d.id, dc.max_capacity
                )
                SELECT drawer_id INTO drawer_id
                FROM drawer_counts
                WHERE container_count < max_capacity
                ORDER BY (max_capacity - container_count) DESC
                LIMIT 1;
            END IF;
        END IF;
        
        RETURN drawer_id;
    END;
    $$ LANGUAGE plpgsql;
    """
    with engine.begin() as conn:
        conn.execute(text(allocation_function_sql))

# Initialize database functions
def init_db_functions():
    create_drawer_coordinates_view()
    create_capacity_check_functions()
    create_allocation_function()
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
        CONCAT(f.asset_id, '-', l.layer_number, '-', r.rack_number, '-', d.drawer_number) AS drawer_coordinate
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
    capacity_check_sql = """
    CREATE OR REPLACE FUNCTION check_drawer_container_capacity() RETURNS TRIGGER AS $$
    DECLARE
        drawer_type INTEGER;
        container_type INTEGER;
        current_count INTEGER;
        max_capacity INTEGER;
    BEGIN
        -- Get container info
        SELECT c.container_type_id, d.drawer_type_id
        INTO container_type, drawer_type
        FROM container c
        JOIN drawer d ON c.drawer_id = d.id
        WHERE c.id = NEW.container_id;
        
        -- Get current count of containers in this drawer of this type
        SELECT COUNT(*) INTO current_count
        FROM container
        WHERE drawer_id = (SELECT drawer_id FROM container WHERE id = NEW.container_id)
        AND container_type_id = container_type;
        
        -- Get max capacity
        SELECT max_capacity INTO max_capacity
        FROM drawer_capacity
        WHERE drawer_type_id = drawer_type AND container_type_id = container_type;
        
        -- Check capacity
        IF current_count > max_capacity THEN
            RAISE EXCEPTION 'Drawer capacity exceeded (% containers of type %, maximum is %)', 
                            current_count, container_type, max_capacity;
        END IF;
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    
    DROP TRIGGER IF EXISTS enforce_study_samples_capacity ON study_samples;
    DROP TRIGGER IF EXISTS enforce_nonglp_samples_capacity ON nonglp_preparation_samples;
    DROP TRIGGER IF EXISTS enforce_glp_samples_capacity ON glp_preparation_sample;
    
    CREATE TRIGGER enforce_study_samples_capacity
    BEFORE INSERT ON study_samples
    FOR EACH ROW EXECUTE FUNCTION check_drawer_container_capacity();
    
    CREATE TRIGGER enforce_nonglp_samples_capacity
    BEFORE INSERT ON nonglp_preparation_samples
    FOR EACH ROW EXECUTE FUNCTION check_drawer_container_capacity();
    
    CREATE TRIGGER enforce_glp_samples_capacity
    BEFORE INSERT ON glp_preparation_sample
    FOR EACH ROW EXECUTE FUNCTION check_drawer_container_capacity();
    """
    with engine.begin() as conn:
        conn.execute(text(capacity_check_sql))

# Function to create sample allocation function
def create_allocation_function():
    allocation_function_sql = """
    CREATE OR REPLACE FUNCTION find_drawer_for_sample(
        p_study_name VARCHAR, 
        p_project_id VARCHAR,
        p_container_type_id INTEGER
    ) RETURNS INTEGER AS $$
    DECLARE
        drawer_id INTEGER;
    BEGIN
        -- First, look for a drawer that:
        -- 1. Already has containers of the same type
        -- 2. Has space available
        -- 3. Contains samples from the same study/project
        
        WITH sample_containers AS (
            -- Get all containers with samples from the same study/project
            SELECT DISTINCT c.id AS container_id, c.drawer_id
            FROM container c
            LEFT JOIN study_samples ss ON c.id = ss.container_id
            LEFT JOIN nonglp_preparation_samples nps ON c.id = nps.container_id
            LEFT JOIN glp_preparation_sample gps ON c.id = gps.container_id
            WHERE 
                (ss.study_name = p_study_name AND ss.project_id = p_project_id) OR
                (nps.study_name = p_study_name AND nps.project_id = p_project_id) OR
                (gps.study_name = p_study_name AND gps.project_id = p_project_id)
        ),
        drawer_counts AS (
            -- Count containers by drawer and check against capacity
            SELECT 
                d.id AS drawer_id,
                d.drawer_type_id,
                COUNT(c.id) AS container_count,
                dc.max_capacity
            FROM drawer d
            JOIN drawer_type dt ON d.drawer_type_id = dt.id
            JOIN drawer_capacity dc ON d.drawer_type_id = dc.drawer_type_id AND dc.container_type_id = p_container_type_id
            LEFT JOIN container c ON d.id = c.drawer_id AND c.container_type_id = p_container_type_id
            GROUP BY d.id, d.drawer_type_id, dc.max_capacity
        )
        
        -- First try to find a drawer with same study/project samples that has room
        SELECT dc.drawer_id INTO drawer_id
        FROM drawer_counts dc
        JOIN sample_containers sc ON dc.drawer_id = sc.drawer_id
        WHERE dc.container_count < dc.max_capacity
        ORDER BY dc.max_capacity - dc.container_count
        LIMIT 1;
        
        -- If no drawer with same project, look for any drawer with space
        IF drawer_id IS NULL THEN
            SELECT drawer_id INTO drawer_id
            FROM drawer_counts
            WHERE container_count < max_capacity
            ORDER BY max_capacity - container_count DESC
            LIMIT 1;
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
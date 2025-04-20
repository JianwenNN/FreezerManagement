"""Initial schema for freezer management system

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-04-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create container_type table
    op.create_table(
        'container_type',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('dimensions', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create drawer_type table
    op.create_table(
        'drawer_type',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create freezer table
    op.create_table(
        'freezer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.String(50), nullable=False),
        sa.Column('temperature', sa.Numeric(5, 2), nullable=False),
        sa.Column('num_of_layers', sa.Integer(), nullable=False),
        sa.Column('num_of_rack_per_layer', sa.Integer(), nullable=False),
        sa.Column('num_of_drawer_per_rack', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('num_of_layers > 0', name='check_positive_layers'),
        sa.CheckConstraint('num_of_rack_per_layer > 0', name='check_positive_racks'),
        sa.CheckConstraint('num_of_drawer_per_rack > 0', name='check_positive_drawers'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asset_id')
    )
    
    # Create drawer_capacity table
    op.create_table(
        'drawer_capacity',
        sa.Column('drawer_type_id', sa.Integer(), nullable=False),
        sa.Column('container_type_id', sa.Integer(), nullable=False),
        sa.Column('max_capacity', sa.Integer(), nullable=False),
        sa.CheckConstraint('max_capacity > 0', name='check_positive_capacity'),
        sa.ForeignKeyConstraint(['container_type_id'], ['container_type.id'], ),
        sa.ForeignKeyConstraint(['drawer_type_id'], ['drawer_type.id'], ),
        sa.PrimaryKeyConstraint('drawer_type_id', 'container_type_id')
    )
    
    # Create layer table
    op.create_table(
        'layer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('freezer_id', sa.Integer(), nullable=False),
        sa.Column('layer_number', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.CheckConstraint('layer_number > 0', name='check_positive_layer_number'),
        sa.ForeignKeyConstraint(['freezer_id'], ['freezer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('freezer_id', 'layer_number', name='uq_layer_freezer_number')
    )
    
    # Create rack table
    op.create_table(
        'rack',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('layer_id', sa.Integer(), nullable=False),
        sa.Column('rack_number', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.CheckConstraint('rack_number > 0', name='check_positive_rack_number'),
        sa.ForeignKeyConstraint(['layer_id'], ['layer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('layer_id', 'rack_number', name='uq_rack_layer_number')
    )
    
    # Create drawer table
    op.create_table(
        'drawer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rack_id', sa.Integer(), nullable=False),
        sa.Column('drawer_number', sa.Integer(), nullable=False),
        sa.Column('drawer_type_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.CheckConstraint('drawer_number > 0', name='check_positive_drawer_number'),
        sa.ForeignKeyConstraint(['drawer_type_id'], ['drawer_type.id'], ),
        sa.ForeignKeyConstraint(['rack_id'], ['rack.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rack_id', 'drawer_number', name='uq_drawer_rack_number')
    )
    
    # Create container table
    op.create_table(
        'container',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.String(100), nullable=False),
        sa.Column('drawer_id', sa.Integer(), nullable=False),
        sa.Column('container_type_id', sa.Integer(), nullable=False),
        sa.Column('position_in_drawer', sa.String(50), nullable=True),
        sa.Column('date_added', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['container_type_id'], ['container_type.id'], ),
        sa.ForeignKeyConstraint(['drawer_id'], ['drawer.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('container_id')
    )
    
    # Create study_samples table
    op.create_table(
        'study_samples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=False),
        sa.Column('study_name', sa.String(200), nullable=False),
        sa.Column('project_id', sa.String(100), nullable=False),
        sa.Column('storage_date', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['container_id'], ['container.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create nonglp_preparation_samples table
    op.create_table(
        'nonglp_preparation_samples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=False),
        sa.Column('study_name', sa.String(200), nullable=False),
        sa.Column('project_id', sa.String(100), nullable=False),
        sa.Column('preparation_date', sa.Date(), nullable=False),
        sa.Column('storage_date', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['container_id'], ['container.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create glp_preparation_sample table
    op.create_table(
        'glp_preparation_sample',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=False),
        sa.Column('preparation_id', sa.String(100), nullable=False),
        sa.Column('preparation_date', sa.Date(), nullable=False),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('study_name', sa.String(200), nullable=False),
        sa.Column('project_id', sa.String(100), nullable=False),
        sa.Column('expiration_date', sa.Date(), nullable=False),
        sa.Column('storage_date', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['container_id'], ['container.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('preparation_id')
    )
    
    # Create indexes for better query performance
    op.create_index(op.f('ix_container_drawer_id'), 'container', ['drawer_id'], unique=False)
    op.create_index(op.f('ix_study_samples_container_id'), 'study_samples', ['container_id'], unique=False)
    op.create_index(op.f('ix_nonglp_preparation_samples_container_id'), 'nonglp_preparation_samples', ['container_id'], unique=False)
    op.create_index(op.f('ix_glp_preparation_sample_container_id'), 'glp_preparation_sample', ['container_id'], unique=False)
    op.create_index(op.f('ix_glp_preparation_sample_expiration_date'), 'glp_preparation_sample', ['expiration_date'], unique=False)
    
    # Create drawer coordinates view
    op.execute("""
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
    """)
    
    # Create capacity check function
    op.execute("""
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
    """)
    
    # Create capacity check triggers
    op.execute("""
    CREATE TRIGGER enforce_study_samples_capacity
    BEFORE INSERT ON study_samples
    FOR EACH ROW EXECUTE FUNCTION check_drawer_container_capacity();
    """)
    
    op.execute("""
    CREATE TRIGGER enforce_nonglp_samples_capacity
    BEFORE INSERT ON nonglp_preparation_samples
    FOR EACH ROW EXECUTE FUNCTION check_drawer_container_capacity();
    """)
    
    op.execute("""
    CREATE TRIGGER enforce_glp_samples_capacity
    BEFORE INSERT ON glp_preparation_sample
    FOR EACH ROW EXECUTE FUNCTION check_drawer_container_capacity();
    """)
    
    # Create sample allocation function
    op.execute("""
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
    """)
    
    # Add initial data for container and drawer types
    op.execute("""
    INSERT INTO container_type (name, dimensions, description) VALUES
    ('Large', '10x10', 'Standard 10x10 container'),
    ('Small', '6x8', 'Compact 6x8 container');
    """)
    
    op.execute("""
    INSERT INTO drawer_type (name, description) VALUES
    ('Standard', 'Standard drawer size'),
    ('Large', 'Larger drawer size');
    """)
    
    op.execute("""
    INSERT INTO drawer_capacity (drawer_type_id, container_type_id, max_capacity) VALUES
    (1, 1, 5),  -- Standard drawer: 5 large (10x10) containers
    (1, 2, 6),  -- Standard drawer: 6 small (6x8) containers
    (2, 1, 6),  -- Large drawer: 6 large (10x10) containers
    (2, 2, 7);  -- Large drawer: 7 small (6x8) containers
    """)

    # Add this to your upgrade() function
    op.execute("""
    CREATE OR REPLACE FUNCTION allocate_containers_in_proximity(
        p_container_type_id INTEGER,
        p_container_count INTEGER
    ) RETURNS TABLE (
        drawer_id INTEGER,
        drawer_coordinate TEXT,
        container_count INTEGER,
        remaining_count INTEGER
    ) AS $$
    DECLARE
        total_to_allocate INTEGER := p_container_count;
        remaining INTEGER := p_container_count;
        current_rack_id INTEGER := NULL;
        current_layer_id INTEGER := NULL;
        current_freezer_id INTEGER := NULL;
        container_fit INTEGER;
        max_capacity INTEGER;
        current_count INTEGER;
    BEGIN
        -- First pass: Try to fill drawers in the same rack
        WHILE remaining > 0 LOOP
            IF current_rack_id IS NULL THEN
                -- Find a rack with maximum available space
                WITH drawer_capacity_info AS (
                    SELECT 
                        d.id AS drawer_id,
                        d.drawer_type_id,
                        d.rack_id,
                        r.layer_id,
                        l.freezer_id,
                        dc.max_capacity,
                        COALESCE((
                            SELECT COUNT(*)
                            FROM container c
                            WHERE c.drawer_id = d.id AND c.container_type_id = p_container_type_id
                        ), 0) AS current_count,
                        (dc.max_capacity - COALESCE((
                            SELECT COUNT(*)
                            FROM container c
                            WHERE c.drawer_id = d.id AND c.container_type_id = p_container_type_id
                        ), 0)) AS available_space
                    FROM drawer d
                    JOIN rack r ON d.rack_id = r.id
                    JOIN layer l ON r.layer_id = l.id
                    JOIN drawer_capacity dc ON d.drawer_type_id = dc.drawer_type_id AND dc.container_type_id = p_container_type_id
                    WHERE (dc.max_capacity - COALESCE((
                        SELECT COUNT(*)
                        FROM container c
                        WHERE c.drawer_id = d.id AND c.container_type_id = p_container_type_id
                    ), 0)) > 0
                ),
                rack_availability AS (
                    SELECT 
                        rack_id,
                        layer_id,
                        freezer_id,
                        SUM(available_space) AS total_space
                    FROM drawer_capacity_info
                    GROUP BY rack_id, layer_id, freezer_id
                    ORDER BY total_space DESC
                    LIMIT 1
                )
                SELECT rack_id, layer_id, freezer_id INTO current_rack_id, current_layer_id, current_freezer_id
                FROM rack_availability;
                
                -- If no rack found, exit
                IF current_rack_id IS NULL THEN
                    EXIT;
                END IF;
            END IF;
            
            -- Find best drawer in current rack
            WITH drawer_info AS (
                SELECT 
                    d.id AS drawer_id,
                    dc.max_capacity,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM container c
                        WHERE c.drawer_id = d.id AND c.container_type_id = p_container_type_id
                    ), 0) AS current_count,
                    (dc.max_capacity - COALESCE((
                        SELECT COUNT(*)
                        FROM container c
                        WHERE c.drawer_id = d.id AND c.container_type_id = p_container_type_id
                    ), 0)) AS available_space
                FROM drawer d
                JOIN drawer_capacity dc ON d.drawer_type_id = dc.drawer_type_id AND dc.container_type_id = p_container_type_id
                WHERE d.rack_id = current_rack_id
                AND (dc.max_capacity - COALESCE((
                    SELECT COUNT(*)
                    FROM container c
                    WHERE c.drawer_id = d.id AND c.container_type_id = p_container_type_id
                ), 0)) > 0
                ORDER BY available_space DESC
                LIMIT 1
            )
            SELECT 
                drawer_id, max_capacity, current_count, available_space 
            INTO 
                drawer_id, max_capacity, current_count, container_fit
            FROM drawer_info;
            
            -- If no drawer found in this rack, move to another rack in same layer
            IF drawer_id IS NULL THEN
                current_rack_id := NULL;
                
                WITH layer_racks AS (
                    SELECT id 
                    FROM rack 
                    WHERE layer_id = current_layer_id 
                    AND id != current_rack_id
                    ORDER BY rack_number
                    LIMIT 1
                )
                SELECT id INTO current_rack_id FROM layer_racks;
                
                -- If no other rack in this layer, try another layer in same freezer
                IF current_rack_id IS NULL THEN
                    current_layer_id := NULL;
                    
                    WITH freezer_layers AS (
                        SELECT id 
                        FROM layer 
                        WHERE freezer_id = current_freezer_id 
                        AND id != current_layer_id
                        ORDER BY layer_number
                        LIMIT 1
                    )
                    SELECT id INTO current_layer_id FROM freezer_layers;
                    
                    -- If no other layer in this freezer, try another freezer
                    IF current_layer_id IS NULL THEN
                        current_freezer_id := NULL;
                        
                        WITH another_freezer AS (
                            SELECT id 
                            FROM freezer 
                            WHERE id != current_freezer_id
                            LIMIT 1
                        )
                        SELECT id INTO current_freezer_id FROM another_freezer;
                        
                        -- If no other freezer, we're out of options
                        IF current_freezer_id IS NULL THEN
                            EXIT;
                        END IF;
                        
                        -- Get first layer in new freezer
                        SELECT id INTO current_layer_id 
                        FROM layer 
                        WHERE freezer_id = current_freezer_id 
                        ORDER BY layer_number 
                        LIMIT 1;
                    END IF;
                    
                    -- Get first rack in new layer
                    SELECT id INTO current_rack_id 
                    FROM rack 
                    WHERE layer_id = current_layer_id 
                    ORDER BY rack_number 
                    LIMIT 1;
                END IF;
                
                CONTINUE;
            END IF;
            
            -- Determine how many containers we can fit in this drawer
            container_count := LEAST(container_fit, remaining);
            remaining := remaining - container_count;
            
            -- Get drawer coordinate
            SELECT drawer_coordinate INTO drawer_coordinate
            FROM drawer_coordinates
            WHERE drawer_coordinates.drawer_id = drawer_id;
            
            -- Return this drawer allocation
            RETURN NEXT;
            
            -- If we've allocated all containers, exit
            IF remaining <= 0 THEN
                EXIT;
            END IF;
        END LOOP;
    END;
    $$ LANGUAGE plpgsql;
    """)


def downgrade():
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS enforce_study_samples_capacity ON study_samples")
    op.execute("DROP TRIGGER IF EXISTS enforce_nonglp_samples_capacity ON nonglp_preparation_samples")
    op.execute("DROP TRIGGER IF EXISTS enforce_glp_samples_capacity ON glp_preparation_sample")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS check_drawer_container_capacity()")
    op.execute("DROP FUNCTION IF EXISTS find_drawer_for_sample(VARCHAR, VARCHAR, INTEGER)")
    
    # Drop views
    op.execute("DROP VIEW IF EXISTS drawer_coordinates")
    op.execute("DROP FUNCTION IF EXISTS allocate_containers_in_proximity(INTEGER, INTEGER);")
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('glp_preparation_sample')
    op.drop_table('nonglp_preparation_samples')
    op.drop_table('study_samples')
    op.drop_table('container')
    op.drop_table('drawer')
    op.drop_table('rack')
    op.drop_table('layer')
    op.drop_table('drawer_capacity')
    op.drop_table('freezer')
    op.drop_table('drawer_type')
    op.drop_table('container_type')
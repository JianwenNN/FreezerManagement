"""Initial schema for freezer management system

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-04-27 12:00:00.000000

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
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_container_type_id', ['id'])
    )
    
    # Create drawer_type table
    op.create_table(
        'drawer_type',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_drawer_type_id', ['id'])
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
        sa.UniqueConstraint('asset_id'),
        sa.Index('ix_freezer_id', ['id'])
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
        sa.UniqueConstraint('freezer_id', 'layer_number', name='uq_layer_freezer_number'),
        sa.Index('ix_layer_id', ['id'])
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
        sa.UniqueConstraint('layer_id', 'rack_number', name='uq_rack_layer_number'),
        sa.Index('ix_rack_id', ['id'])
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
        sa.UniqueConstraint('rack_id', 'drawer_number', name='uq_drawer_rack_number'),
        sa.Index('ix_drawer_id', ['id'])
    )
    
    # Create study_sample_container table
    op.create_table(
        'study_sample_container',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('drawer_id', sa.Integer(), nullable=False),
        sa.Column('container_type_id', sa.Integer(), nullable=False),
        sa.Column('container_barcode', sa.String(100), nullable=False),
        sa.Column('study_name', sa.String(100), nullable=False),
        sa.Column('position_in_drawer', sa.String(50), nullable=True),
        sa.Column('date_added', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['container_type_id'], ['container_type.id'], ),
        sa.ForeignKeyConstraint(['drawer_id'], ['drawer.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('container_barcode'),
        sa.Index('ix_study_sample_container_id', ['id']),
        sa.Index('ix_study_sample_container_drawer_id', ['drawer_id'])
    )
    
    # Create stdqc_container table
    op.create_table(
        'stdqc_container',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('drawer_id', sa.Integer(), nullable=False),
        sa.Column('container_type_id', sa.Integer(), nullable=False),
        sa.Column('compound_name', sa.String(100), nullable=False),
        sa.Column('matrix', sa.String(50), nullable=False),
        sa.Column('anticoagulant', sa.String(50), nullable=False),
        sa.Column('prep_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_id', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('position_in_drawer', sa.String(50), nullable=True),
        sa.Column('date_added', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['container_type_id'], ['container_type.id'], ),
        sa.ForeignKeyConstraint(['drawer_id'], ['drawer.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_stdqc_container_id', ['id']),
        sa.Index('ix_stdqc_container_drawer_id', ['drawer_id'])
    )
    
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
    
    # Create capacity check functions for study samples
    op.execute("""
    CREATE OR REPLACE FUNCTION check_study_sample_container_capacity() RETURNS TRIGGER AS $$
    DECLARE
        drawer_type INTEGER;
        container_type INTEGER;
        current_count INTEGER;
        max_capacity INTEGER;
    BEGIN
        -- Get drawer and container type
        SELECT NEW.container_type_id, d.drawer_type_id
        INTO container_type, drawer_type
        FROM drawer d
        WHERE d.id = NEW.drawer_id;
        
        -- Get current count of this container type in the drawer
        SELECT COUNT(*) INTO current_count
        FROM study_sample_container
        WHERE drawer_id = NEW.drawer_id
        AND container_type_id = container_type;
        
        -- Get max capacity
        SELECT max_capacity INTO max_capacity
        FROM drawer_capacity
        WHERE drawer_type_id = drawer_type AND container_type_id = container_type;
        
        -- Check capacity
        IF current_count >= max_capacity THEN
            RAISE EXCEPTION 'Drawer capacity exceeded (% study sample containers of type %, maximum is %)', 
                            current_count, container_type, max_capacity;
        END IF;
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    
    # Create capacity check functions for STDQC containers
    op.execute("""
    CREATE OR REPLACE FUNCTION check_stdqc_container_capacity() RETURNS TRIGGER AS $$
    DECLARE
        drawer_type INTEGER;
        container_type INTEGER;
        current_count INTEGER;
        max_capacity INTEGER;
    BEGIN
        -- Get drawer and container type
        SELECT NEW.container_type_id, d.drawer_type_id
        INTO container_type, drawer_type
        FROM drawer d
        WHERE d.id = NEW.drawer_id;
        
        -- Get current count of this container type in the drawer
        SELECT COUNT(*) INTO current_count
        FROM stdqc_container
        WHERE drawer_id = NEW.drawer_id
        AND container_type_id = container_type;
        
        -- Get max capacity
        SELECT max_capacity INTO max_capacity
        FROM drawer_capacity
        WHERE drawer_type_id = drawer_type AND container_type_id = container_type;
        
        -- Check capacity
        IF current_count >= max_capacity THEN
            RAISE EXCEPTION 'Drawer capacity exceeded (% STDQC containers of type %, maximum is %)', 
                            current_count, container_type, max_capacity;
        END IF;
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    
    # Create capacity check triggers
    op.execute("""
    CREATE TRIGGER enforce_study_samples_capacity
    BEFORE INSERT ON study_sample_container
    FOR EACH ROW EXECUTE FUNCTION check_study_sample_container_capacity();
    """)
    
    op.execute("""
    CREATE TRIGGER enforce_stdqc_samples_capacity
    BEFORE INSERT ON stdqc_container
    FOR EACH ROW EXECUTE FUNCTION check_stdqc_container_capacity();
    """)
    
    # Create allocation function for containers
    op.execute("""
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
    """)
    
    # Create allocation function for multiple containers
    op.execute("""
    CREATE OR REPLACE FUNCTION allocate_containers_in_proximity(
        p_container_type_id INTEGER,
        p_container_count INTEGER,
        p_sample_type VARCHAR
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
        -- Helper function to calculate available space based on container type
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
        BEGIN
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

        -- Loop until all containers are allocated or no more space
        WHILE remaining > 0 LOOP
            IF current_rack_id IS NULL THEN
                -- Find a rack with maximum available space
                WITH rack_availability AS (
                    SELECT r.id AS rack_id, r.layer_id, l.freezer_id, 
                        SUM(available_space_in_drawer(d.id, p_container_type_id, p_sample_type)) AS total_space
                    FROM drawer d
                    JOIN rack r ON d.rack_id = r.id
                    JOIN layer l ON r.layer_id = l.id
                    WHERE available_space_in_drawer(d.id, p_container_type_id, p_sample_type) > 0
                    GROUP BY r.id, r.layer_id, l.freezer_id
                    ORDER BY total_space DESC
                    LIMIT 1
                )
                SELECT rack_id, layer_id, freezer_id INTO current_rack_id, current_layer_id, current_freezer_id
                FROM rack_availability;

                -- If no rack found, exit
                IF current_rack_id IS NULL THEN
                    RAISE NOTICE 'No available space for containers';
                    EXIT;
                END IF;
            END IF;

            -- Find best drawer in current rack
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

                -- If no other rack in this layer, try another layer in same freezer
                IF current_rack_id IS NULL THEN
                    current_layer_id := NULL;
                    -- Find another layer in the same freezer
                    WITH freezer_layers AS (
                        SELECT id FROM layer 
                        WHERE freezer_id = current_freezer_id 
                        AND id != current_layer_id
                        ORDER BY layer_number
                        LIMIT 1
                    )
                    SELECT id INTO current_layer_id FROM freezer_layers;

                    -- If no other layer in this freezer, try another freezer
                    IF current_layer_id IS NULL THEN
                        current_freezer_id := NULL;
                        -- Find another freezer
                        WITH another_freezer AS (
                            SELECT id FROM freezer 
                            WHERE id != current_freezer_id
                            LIMIT 1
                        )
                        SELECT id INTO current_freezer_id FROM another_freezer;

                        -- If no other freezer, exit
                        IF current_freezer_id IS NULL THEN
                            RAISE NOTICE 'No more available storage for containers';
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

            -- Allocate containers
            container_count := LEAST(container_fit, remaining);
            remaining := remaining - container_count;

            -- Get drawer coordinates
            SELECT drawer_coordinate INTO drawer_coordinate
            FROM drawer_coordinates
            WHERE drawer_id = drawer_id;

            -- Return the allocation for this drawer
            RETURN NEXT;

            -- Exit if all containers have been allocated
            IF remaining <= 0 THEN
                EXIT;
            END IF;
        END LOOP;
        
        -- If still remaining containers, raise a notice
        IF remaining > 0 THEN
            RAISE NOTICE 'Unable to allocate all containers. Remaining: %', remaining;
        END IF;

        -- Drop helper function
        DROP FUNCTION IF EXISTS available_space_in_drawer(INTEGER, INTEGER, VARCHAR);
    END;
    $$ LANGUAGE plpgsql;
    """)
    
    # Add initial data for container and drawer types
    op.execute("""
    INSERT INTO container_type (name, description) VALUES
    ('Large', 'Standard large container'),
    ('Small', 'Compact small container');
    """)
    
    op.execute("""
    INSERT INTO drawer_type (name, description) VALUES
    ('Standard', 'Standard drawer size'),
    ('Large', 'Larger drawer size');
    """)
    
    op.execute("""
    INSERT INTO drawer_capacity (drawer_type_id, container_type_id, max_capacity) VALUES
    (1, 1, 5),  -- Standard drawer: 5 large containers
    (1, 2, 6),  -- Standard drawer: 6 small containers
    (2, 1, 6),  -- Large drawer: 6 large containers
    (2, 2, 7);  -- Large drawer: 7 small containers
    """)


def downgrade():
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS enforce_study_samples_capacity ON study_sample_container")
    op.execute("DROP TRIGGER IF EXISTS enforce_stdqc_samples_capacity ON stdqc_container")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS check_study_sample_container_capacity()")
    op.execute("DROP FUNCTION IF EXISTS check_stdqc_container_capacity()")
    op.execute("DROP FUNCTION IF EXISTS find_drawer_for_containers(VARCHAR, INTEGER, VARCHAR)")
    op.execute("DROP FUNCTION IF EXISTS allocate_containers_in_proximity(INTEGER, INTEGER, VARCHAR)")
    
    # Drop views
    op.execute("DROP VIEW IF EXISTS drawer_coordinates")
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('stdqc_container')
    op.drop_table('study_sample_container')
    op.drop_table('drawer')
    op.drop_table('rack')
    op.drop_table('layer')
    op.drop_table('drawer_capacity')
    op.drop_table('freezer')
    op.drop_table('drawer_type')
    op.drop_table('container_type')
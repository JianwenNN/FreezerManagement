"""Initial schema for freezer management system

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-04-27 12:00:00.000000

Schema overview
---------------
Tables (managed by Alembic Python API):
    freezer, layer, rack, drawer,
    study_sample_container, stdqc_container

SQL objects (loaded from app/sql/):
    views/      drawer_coordinates
    functions/  available_space_in_drawer
                allocate_containers_in_proximity
                check_study_sample_container_capacity
                check_stdqc_container_capacity
    triggers/   enforce_study_samples_capacity
                enforce_stdqc_samples_capacity
"""

import os
from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision      = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on    = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _load_sql(relative_path: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base, "..", "app", "sql", relative_path)
    with open(full_path) as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:

    op.create_table(
        'freezer',
        sa.Column('id',                     sa.Integer(),     nullable=False),
        sa.Column('asset_id',               sa.String(50),    nullable=False),
        sa.Column('temperature',            sa.Numeric(5, 2), nullable=False),
        sa.Column('num_of_layers',          sa.Integer(),     nullable=False),
        sa.Column('num_of_rack_per_layer',  sa.Integer(),     nullable=False),
        sa.Column('num_of_drawer_per_rack', sa.Integer(),     nullable=False),
        # Capacity per drawer — determined by the physical drawer dimensions.
        # A drawer holds EITHER type, never both at once.
        # The first container placed locks the drawer to that type;
        # an empty drawer is flexible again.
        sa.Column('study_sample_capacity',  sa.Integer(),     nullable=False),
        sa.Column('stdqc_capacity',         sa.Integer(),     nullable=False),
        sa.Column('description',            sa.Text(),        nullable=True),
        sa.Column('location',               sa.String(100),   nullable=True),
        sa.Column('created_at',             sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('num_of_layers > 0',          name='check_positive_layers'),
        sa.CheckConstraint('num_of_rack_per_layer > 0',  name='check_positive_racks'),
        sa.CheckConstraint('num_of_drawer_per_rack > 0', name='check_positive_drawers'),
        sa.CheckConstraint('study_sample_capacity > 0',  name='check_positive_study_capacity'),
        sa.CheckConstraint('stdqc_capacity > 0',         name='check_positive_stdqc_capacity'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asset_id'),
        sa.Index('ix_freezer_id', 'id'),
    )

    op.create_table(
        'layer',
        sa.Column('id',           sa.Integer(), nullable=False),
        sa.Column('freezer_id',   sa.Integer(), nullable=False),
        sa.Column('layer_number', sa.Integer(), nullable=False),
        sa.Column('description',  sa.Text(),    nullable=True),
        sa.CheckConstraint('layer_number > 0', name='check_positive_layer_number'),
        sa.ForeignKeyConstraint(['freezer_id'], ['freezer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('freezer_id', 'layer_number', name='uq_layer_freezer_number'),
        sa.Index('ix_layer_id', 'id'),
    )

    op.create_table(
        'rack',
        sa.Column('id',          sa.Integer(), nullable=False),
        sa.Column('layer_id',    sa.Integer(), nullable=False),
        sa.Column('rack_number', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(),    nullable=True),
        sa.CheckConstraint('rack_number > 0', name='check_positive_rack_number'),
        sa.ForeignKeyConstraint(['layer_id'], ['layer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('layer_id', 'rack_number', name='uq_rack_layer_number'),
        sa.Index('ix_rack_id', 'id'),
    )

    op.create_table(
        'drawer',
        sa.Column('id',              sa.Integer(),   nullable=False),
        sa.Column('rack_id',         sa.Integer(),   nullable=False),
        sa.Column('drawer_number',   sa.Integer(),   nullable=False),
        sa.Column('description',     sa.Text(),      nullable=True),
        sa.Column('reserved',        sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('reserved_reason', sa.String(200), nullable=True),
        sa.CheckConstraint('drawer_number > 0', name='check_positive_drawer_number'),
        sa.ForeignKeyConstraint(['rack_id'], ['rack.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rack_id', 'drawer_number', name='uq_drawer_rack_number'),
        sa.Index('ix_drawer_id', 'id'),
    )

    op.create_table(
        'study_sample_container',
        sa.Column('id',                 sa.Integer(),              nullable=False),
        sa.Column('drawer_id',          sa.Integer(),              nullable=False),
        sa.Column('container_barcode',  sa.String(100),            nullable=False),
        sa.Column('study_name',         sa.String(100),            nullable=False),
        sa.Column('position_in_drawer', sa.String(50),             nullable=True),
        sa.Column('date_added',         sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['drawer_id'], ['drawer.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('container_barcode'),
        sa.Index('ix_study_sample_container_id',        'id'),
        sa.Index('ix_study_sample_container_drawer_id', 'drawer_id'),
    )

    op.create_table(
        'stdqc_container',
        sa.Column('id',                 sa.Integer(),              nullable=False),
        sa.Column('drawer_id',          sa.Integer(),              nullable=False),
        sa.Column('compound_name',      sa.String(100),            nullable=False),
        sa.Column('matrix',             sa.String(50),             nullable=False),
        sa.Column('anticoagulant',      sa.String(50),             nullable=False),
        sa.Column('prep_date',          sa.DateTime(timezone=True),nullable=False),
        sa.Column('source_id',          sa.String(100),            nullable=True),
        sa.Column('description',        sa.Text(),                 nullable=True),
        sa.Column('position_in_drawer', sa.String(50),             nullable=True),
        sa.Column('date_added',         sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['drawer_id'], ['drawer.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_stdqc_container_id',        'id'),
        sa.Index('ix_stdqc_container_drawer_id', 'drawer_id'),
    )

    # Views
    op.execute(_load_sql("views/drawer_coordinates.sql"))

    # Functions — available_space_in_drawer must come before
    # allocate_containers_in_proximity because the latter calls the former.
    op.execute(_load_sql("functions/available_space_in_drawer.sql"))
    op.execute(_load_sql("functions/allocate_containers_in_proximity.sql"))
    op.execute(_load_sql("functions/check_study_sample_container_capacity.sql"))
    op.execute(_load_sql("functions/check_stdqc_container_capacity.sql"))

    # Triggers
    op.execute(_load_sql("triggers/enforce_study_samples_capacity.sql"))
    op.execute(_load_sql("triggers/enforce_stdqc_samples_capacity.sql"))


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:

    op.execute("DROP TRIGGER IF EXISTS enforce_study_samples_capacity ON study_sample_container")
    op.execute("DROP TRIGGER IF EXISTS enforce_stdqc_samples_capacity ON stdqc_container")

    op.execute("DROP FUNCTION IF EXISTS allocate_containers_in_proximity(INTEGER, VARCHAR, VARCHAR)")
    op.execute("DROP FUNCTION IF EXISTS available_space_in_drawer(INTEGER, VARCHAR)")
    op.execute("DROP FUNCTION IF EXISTS check_study_sample_container_capacity()")
    op.execute("DROP FUNCTION IF EXISTS check_stdqc_container_capacity()")

    op.execute("DROP VIEW IF EXISTS drawer_coordinates")

    op.drop_table('stdqc_container')
    op.drop_table('study_sample_container')
    op.drop_table('drawer')
    op.drop_table('rack')
    op.drop_table('layer')
    op.drop_table('freezer')

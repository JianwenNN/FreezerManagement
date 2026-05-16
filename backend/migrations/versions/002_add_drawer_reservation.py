"""Add drawer_reservation table for soft-hold allocation pattern

Revision ID: 002_add_drawer_reservation
Revises: 001_initial_schema
Create Date: 2025-04-27 13:00:00.000000

Why this table exists
----------------------
The allocation flow has two steps:
  1. Suggest  — read-only, returns a plan + reservation tokens
  2. Confirm  — short transaction, inserts containers

Between steps 1 and 2 the user reviews the plan. During that window
other users could claim the same drawers. The reservation record acts
as a soft hold: it does not block inserts (no DB-level lock is held),
but the confirm endpoint checks for an active reservation before
proceeding. If the reservation has expired the endpoint re-checks live
capacity and proceeds if space is still available.

Expired rows are purged by a background job (APScheduler, every minute).
"""

from alembic import op
import sqlalchemy as sa


revision      = '002_add_drawer_reservation'
down_revision = '001_initial_schema'
branch_labels = None
depends_on    = None


import os


def _load_sql(relative_path: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base, "..", "app", "sql", relative_path)
    with open(full_path) as fh:
        return fh.read()


def upgrade() -> None:
    op.create_table(
        'drawer_reservation',
        sa.Column('id',             sa.Integer(),              nullable=False),
        sa.Column('drawer_id',      sa.Integer(),              nullable=False),
        sa.Column('sample_type',    sa.String(50),             nullable=False),
        sa.Column('reserved_count', sa.Integer(),              nullable=False),
        # UUID token returned to the frontend and echoed back at confirmation
        sa.Column('token',          sa.String(36),             nullable=False),
        sa.Column('expires_at',     sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_at',     sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('reserved_count > 0', name='check_positive_reserved_count'),
        sa.CheckConstraint(
            "sample_type IN ('study_sample_container', 'stdqc_container')",
            name='check_reservation_sample_type'
        ),
        sa.ForeignKeyConstraint(['drawer_id'], ['drawer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token', name='uq_reservation_token'),
        # Index on expires_at — used by the background cleanup job
        sa.Index('ix_drawer_reservation_expires_at', 'expires_at'),
        # Index on drawer_id + sample_type — used by confirm to find active reservations
        sa.Index('ix_drawer_reservation_drawer_sample', 'drawer_id', 'sample_type'),
    )


    # Re-create available_space_in_drawer now that drawer_reservation exists.
    # The version created in 001 queries this table at call time (PL/pgSQL resolves
    # table references lazily), but recreating it here makes the dependency explicit
    # and ensures the function is correct even if 001 is inspected in isolation.
    op.execute(_load_sql("functions/available_space_in_drawer.sql"))


def downgrade() -> None:
    # Revert available_space_in_drawer to a version without reservation awareness.
    # We drop and recreate rather than maintaining a separate "pre-reservation" version,
    # since downgrading 002 means drawer_reservation no longer exists.
    op.execute("""
        CREATE OR REPLACE FUNCTION available_space_in_drawer(
            p_drawer_id   INTEGER,
            p_sample_type VARCHAR
        )
        RETURNS INTEGER AS $$
        DECLARE
            v_study_capacity INTEGER;
            v_stdqc_capacity INTEGER;
            v_max_capacity   INTEGER;
            v_current_count  INTEGER;
            v_other_count    INTEGER;
        BEGIN
            SELECT f.study_sample_capacity, f.stdqc_capacity
            INTO   v_study_capacity, v_stdqc_capacity
            FROM   drawer d
            JOIN   rack  r ON d.rack_id  = r.id
            JOIN   layer l ON r.layer_id = l.id
            JOIN   freezer f ON l.freezer_id = f.id
            WHERE  d.id = p_drawer_id;

            IF v_study_capacity IS NULL THEN RETURN 0; END IF;

            IF p_sample_type = 'study_sample_container' THEN
                v_max_capacity := v_study_capacity;
            ELSIF p_sample_type = 'stdqc_container' THEN
                v_max_capacity := v_stdqc_capacity;
            ELSE
                RETURN 0;
            END IF;

            IF p_sample_type = 'study_sample_container' THEN
                SELECT COUNT(*) INTO v_other_count FROM stdqc_container WHERE drawer_id = p_drawer_id;
            ELSE
                SELECT COUNT(*) INTO v_other_count FROM study_sample_container WHERE drawer_id = p_drawer_id;
            END IF;

            IF v_other_count > 0 THEN RETURN 0; END IF;

            IF p_sample_type = 'study_sample_container' THEN
                SELECT COUNT(*) INTO v_current_count FROM study_sample_container WHERE drawer_id = p_drawer_id;
            ELSE
                SELECT COUNT(*) INTO v_current_count FROM stdqc_container WHERE drawer_id = p_drawer_id;
            END IF;

            RETURN GREATEST(0, v_max_capacity - v_current_count);
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.drop_table('drawer_reservation')

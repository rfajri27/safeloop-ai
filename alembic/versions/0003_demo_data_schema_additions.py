"""demo data schema additions

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11 23:30:00.000000

The demo data package (safeloop-demo-data) needs four small additions
to the MVP schema; see its README, "Schema additions":

- asset_links.code (unique): agents and the Judge cite links as asset_model:L-104
- safeguard_type gains 'mechanical': NRV-101 is a safeguard but not an IPL
- documents: unique on (doc_code, revision) instead of doc_code, so the
  superseded SOP revision sits alongside the current one
- users.handle and golden_items.item_code (both unique): demo login by
  handle; eval results keyed by GH-01, QA-01, ...

The demo users seeded by 0002 are re-keyed onto the package's deterministic
ids and handles, so data/sql/seed.sql (which references them) loads cleanly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (0002 display name, id, handle, display name, email) — from data/seed/users.json
DEMO_USERS = [
    ("Rina", "40d1955b-cf40-574a-95ee-497c28120572", "rina", "Rina", "rina@example.com"),
    ("Dimas", "d87eaf84-07c0-5137-bbaa-a633b4bfa7cb", "dimas", "Dimas", "dimas@example.com"),
    ("Agus", "deb0fd4b-7de7-5a21-83ec-6beaadbd61a8", "agus", "Agus", "agus@example.com"),
    ("Auditor", "6fac6620-8bee-52b4-a203-f5221b683e5b", "auditor", "Maya", "maya@example.com"),
    ("Admin", "84061316-19a7-506e-9756-d45cc875fe66", "admin", "Budi", "budi@example.com"),
]


def upgrade() -> None:
    # Cannot run inside a transaction block on PostgreSQL < 12; fine on 12+.
    op.execute("ALTER TYPE safeguard_type ADD VALUE IF NOT EXISTS 'mechanical'")

    op.add_column('asset_links', sa.Column('code', sa.String(length=16), nullable=True, comment='L-101 ... L-118; cited as asset_model:<code>'))
    op.create_unique_constraint('uq_asset_links_code', 'asset_links', ['code'])

    op.drop_constraint('documents_doc_code_key', 'documents', type_='unique')
    op.create_unique_constraint('uq_documents_doc_code_revision', 'documents', ['doc_code', 'revision'])

    op.add_column('golden_items', sa.Column('item_code', sa.String(length=16), nullable=True, comment='GH-01, QA-01, OOC-01, GR-01, RCA-01'))
    op.create_unique_constraint('uq_golden_items_item_code', 'golden_items', ['item_code'])

    op.add_column('users', sa.Column('handle', sa.String(length=32), nullable=True, comment='Demo login handle: rina, dimas, agus, auditor, admin'))

    # Re-key the 0002 demo users. Fails (rather than orphaning rows) if one is
    # already referenced, since the foreign keys have no ON UPDATE CASCADE.
    for old_name, user_id, handle, display_name, email in DEMO_USERS:
        op.execute(
            sa.text(
                """
                UPDATE users SET id = CAST(:id AS uuid), handle = :handle,
                                 display_name = :display_name, email = :email
                WHERE is_demo AND lower(display_name) = lower(:old_name)
                  AND id <> CAST(:id AS uuid)
                  AND NOT EXISTS (SELECT 1 FROM users WHERE id = CAST(:id AS uuid))
                """
            ).bindparams(id=user_id, handle=handle, display_name=display_name, email=email, old_name=old_name)
        )

    # Any other user gets a handle from the display name, suffixed if taken.
    op.execute(
        """
        WITH base AS (
            SELECT id, left(regexp_replace(lower(display_name), '[^a-z0-9]+', '_', 'g'), 23) AS h,
                   row_number() OVER (
                       PARTITION BY left(regexp_replace(lower(display_name), '[^a-z0-9]+', '_', 'g'), 23)
                       ORDER BY created_at, id
                   ) AS n
            FROM users WHERE handle IS NULL
        )
        UPDATE users u
        SET handle = CASE
            WHEN b.n = 1 AND NOT EXISTS (SELECT 1 FROM users x WHERE x.handle = b.h) THEN b.h
            ELSE b.h || '_' || left(replace(u.id::text, '-', ''), 8)
        END
        FROM base b WHERE u.id = b.id
        """
    )
    op.alter_column('users', 'handle', nullable=False)
    op.create_unique_constraint('uq_users_handle', 'users', ['handle'])


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value; 'mechanical' stays on safeguard_type.
    op.drop_constraint('uq_users_handle', 'users', type_='unique')
    op.drop_column('users', 'handle')

    op.drop_constraint('uq_golden_items_item_code', 'golden_items', type_='unique')
    op.drop_column('golden_items', 'item_code')

    # Fails if a document has more than one revision stored.
    op.drop_constraint('uq_documents_doc_code_revision', 'documents', type_='unique')
    op.create_unique_constraint('documents_doc_code_key', 'documents', ['doc_code'])

    op.drop_constraint('uq_asset_links_code', 'asset_links', type_='unique')
    op.drop_column('asset_links', 'code')

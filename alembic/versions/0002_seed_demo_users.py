"""seed demo users

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 22:40:00.000000

The MVP has no password store: POST /auth/demo-login issues a token for one of
these seeded users, matched by display name (rina, dimas, agus, auditor, admin).
Seeding them here breaks the chicken-and-egg of needing an admin token to
create the first user. Idempotent: existing demo users are left untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (display name / login handle, role) — personas from the MVP design
DEMO_USERS = [
    ("Rina", "process_safety_engineer"),
    ("Dimas", "reliability_engineer"),
    ("Agus", "operator"),
    ("Auditor", "auditor"),
    ("Admin", "admin"),
]


def upgrade() -> None:
    for display_name, role in DEMO_USERS:
        op.execute(
            sa.text(
                """
                INSERT INTO users (display_name, role, is_demo)
                SELECT :name, CAST(:role AS user_role), true
                WHERE NOT EXISTS (
                    SELECT 1 FROM users
                    WHERE is_demo AND lower(display_name) = lower(:name)
                )
                """
            ).bindparams(name=display_name, role=role)
        )


def downgrade() -> None:
    # Fails if a demo user is already referenced (audit log, approvals, ...),
    # which protects the append-only history.
    op.execute(
        sa.text("DELETE FROM users WHERE is_demo AND lower(display_name) = ANY(:names)")
        .bindparams(names=[name.lower() for name, _ in DEMO_USERS])
    )

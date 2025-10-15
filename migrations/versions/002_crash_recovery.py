"""crash recovery: retry lease column + dead letter uniqueness

Revision ID: 002
Revises: 001
Create Date: 2026-07-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "delivery_attempts",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Two concurrent final attempts must not both dead-letter the same delivery.
    op.execute(
        "DELETE FROM dead_letters a USING dead_letters b "
        "WHERE a.id > b.id AND a.event_id = b.event_id AND a.endpoint_id = b.endpoint_id"
    )
    op.create_unique_constraint(
        "uq_dead_letter_event_endpoint", "dead_letters", ["event_id", "endpoint_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_dead_letter_event_endpoint", "dead_letters", type_="unique")
    op.drop_column("delivery_attempts", "next_retry_at")

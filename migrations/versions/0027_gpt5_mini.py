from typing import Sequence, Union

from alembic import op

revision: str = "0027_gpt5_mini"
down_revision: Union[str, None] = "0026_media_engagement_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE setting SET value=to_jsonb('gpt-5-mini'::text), updated_at=now() "
        "WHERE key='llm_model'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE setting SET value=to_jsonb('gpt-5.6-terra'::text), updated_at=now() "
        "WHERE key='llm_model' AND value=to_jsonb('gpt-5-mini'::text)"
    )

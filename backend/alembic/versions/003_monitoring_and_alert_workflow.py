"""Persist monitoring zones and alert workflow fields already used by the API."""
from alembic import op
import sqlalchemy as sa
revision = "003_monitoring_alerts"
down_revision = "002_expanded_intelligence_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("monitoring_zones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("min_lat", sa.Float(), nullable=False),
        sa.Column("max_lat", sa.Float(), nullable=False),
        sa.Column("min_lon", sa.Float(), nullable=False),
        sa.Column("max_lon", sa.Float(), nullable=False),
        sa.Column("sensitivity", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("alert_email", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("idx_zones_active", "monitoring_zones", ["is_active"])
    op.create_index("idx_zones_bbox", "monitoring_zones", ["min_lat", "max_lat", "min_lon", "max_lon"])
    for column in [sa.Column("risk_score", sa.Float()), sa.Column("assigned_to", sa.Uuid()),
                   sa.Column("assigned_analyst_name", sa.String(255)), sa.Column("acknowledged_at", sa.DateTime()),
                   sa.Column("acknowledged_by", sa.String(255)), sa.Column("resolution_notes", sa.Text())]:
        op.add_column("alerts", column)
    op.create_foreign_key("fk_alerts_assigned_to", "alerts", "users", ["assigned_to"], ["id"], ondelete="SET NULL")


def downgrade():
    op.drop_constraint("fk_alerts_assigned_to", "alerts", type_="foreignkey")
    for name in ["resolution_notes", "acknowledged_by", "acknowledged_at", "assigned_analyst_name", "assigned_to", "risk_score"]:
        op.drop_column("alerts", name)
    op.drop_table("monitoring_zones")

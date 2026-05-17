"""init schema with postgis + 4 tables

Revision ID: 0001
Revises:
Create Date: 2026-05-17

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("deal_id", sa.Text, nullable=False),
        sa.Column("deal_date", sa.Date, nullable=False),
        sa.Column("city", sa.Text, nullable=False),
        sa.Column("neighborhood", sa.Text),
        sa.Column("street", sa.Text),
        sa.Column("house_number", sa.Text),
        sa.Column("property_type", sa.Text, nullable=False),
        sa.Column("rooms", sa.Numeric(3, 1)),
        sa.Column("sqm", sa.Numeric(7, 2)),
        sa.Column("price", sa.Numeric(12, 0), nullable=False),
        sa.Column(
            "geom",
            Geometry(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.UniqueConstraint("deal_id", "deal_date", name="transactions_deal_unique"),
    )
    op.create_index(
        "transactions_geom_gix",
        "transactions",
        ["geom"],
        postgresql_using="gist",
    )
    op.create_index(
        "transactions_city_rooms_date_idx",
        "transactions",
        ["city", "rooms", "deal_date"],
    )

    op.create_table(
        "listings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_listing_id", sa.Text, nullable=False),
        sa.Column("city", sa.Text, nullable=False),
        sa.Column("neighborhood", sa.Text),
        sa.Column("address", sa.Text),
        sa.Column("rooms", sa.Numeric(3, 1)),
        sa.Column("sqm", sa.Numeric(7, 2)),
        sa.Column("price", sa.Numeric(12, 0)),
        sa.Column("property_type", sa.Text),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("raw_json", sa.dialects.postgresql.JSONB),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326)),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("source", "source_listing_id", name="listings_source_unique"),
    )
    op.create_index(
        "listings_geom_gix",
        "listings",
        ["geom"],
        postgresql_using="gist",
    )

    op.create_table(
        "scan_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("step", sa.String(32)),
        sa.Column("error_msg", sa.Text),
        sa.Column("filters_json", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("result_count", sa.Integer),
        sa.Column("skipped_json", sa.dialects.postgresql.JSONB),
    )

    op.create_table(
        "scan_results",
        sa.Column(
            "scan_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rank", sa.Integer, primary_key=True),
        sa.Column(
            "listing_id",
            sa.BigInteger,
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asking_price", sa.Numeric(12, 0), nullable=False),
        sa.Column("estimated_value", sa.Numeric(12, 0), nullable=False),
        sa.Column("median_ppsqm", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 4), nullable=False),
        sa.Column("comparable_count", sa.Integer, nullable=False),
        sa.Column("radius_m", sa.Integer, nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
    )
    op.create_index("scan_results_scan_idx", "scan_results", ["scan_id"])


def downgrade() -> None:
    op.drop_index("scan_results_scan_idx", table_name="scan_results")
    op.drop_table("scan_results")
    op.drop_table("scan_runs")
    op.drop_index("listings_geom_gix", table_name="listings")
    op.drop_table("listings")
    op.drop_index("transactions_city_rooms_date_idx", table_name="transactions")
    op.drop_index("transactions_geom_gix", table_name="transactions")
    op.drop_table("transactions")

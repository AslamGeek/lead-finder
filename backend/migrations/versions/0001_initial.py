"""Initial normalized application schema with PostGIS geography indexes."""
from alembic import op
from migrations.schema_0001 import Base
revision='0001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    if op.get_bind().dialect.name=='postgresql':op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    Base.metadata.create_all(bind=op.get_bind())
def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())

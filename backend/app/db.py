from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings
engine=create_engine(settings.database_url,pool_pre_ping=True,connect_args={"check_same_thread":False} if settings.database_url.startswith("sqlite") else {})
Session=sessionmaker(engine,expire_on_commit=False)
def get_session():
    with Session() as session:
        yield session

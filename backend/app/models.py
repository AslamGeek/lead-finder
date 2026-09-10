from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column,LargeBinary,String,Text,Float,Integer,Boolean,DateTime,ForeignKey,Uuid,JSON,Table,Index,UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from geoalchemy2 import Geography
def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
J=JSON().with_variant(JSONB,'postgresql')
class Identity:
    id=Column(Uuid,primary_key=True,default=uuid4)
    created_at=Column(DateTime(timezone=True),default=now,nullable=False)
class User(Identity,Base):
    __tablename__='users'
    name=Column(String(200),nullable=False)
class Location(Identity,Base):
    __tablename__='locations'
    provider_id=Column(String(200),index=True,nullable=False)
    display_name=Column(String(500),nullable=False)
    city=Column(String(200));district=Column(String(200));state=Column(String(200));country=Column(String(200))
    latitude=Column(Float,nullable=False);longitude=Column(Float,nullable=False)
    bounding_box=Column(J)
class SearchJob(Identity,Base):
    __tablename__='search_jobs'
    user_id=Column(Uuid,ForeignKey('users.id'))
    location_id=Column(Uuid,ForeignKey('locations.id'),nullable=False)
    request=Column(J,nullable=False)
    stage=Column(String(40),default='queued',index=True)
    progress_percent=Column(Integer,default=0)
    raw_observations=Column(Integer,default=0);unique_entities=Column(Integer,default=0)
    entities_enriched=Column(Integer,default=0);duplicate_merges=Column(Integer,default=0)
    queries_executed=Column(Integer,default=0);pages_crawled=Column(Integer,default=0)
    errors=Column(J,default=list);normalized_terms=Column(J,default=list);query_variants=Column(J,default=list)
    cancel_requested=Column(Boolean,default=False)
    completed_at=Column(DateTime(timezone=True))
    duration_seconds=Column(Float)
class SearchQuery(Identity,Base):
    __tablename__='search_queries'
    job_id=Column(Uuid,ForeignKey('search_jobs.id'),index=True,nullable=False)
    query=Column(String(200),nullable=False)
    source=Column(String(100),nullable=False)
class Observation(Identity,Base):
    __tablename__='raw_observations'
    job_id=Column(Uuid,ForeignKey('search_jobs.id'),index=True,nullable=False)
    source=Column(String(100),nullable=False);source_record_id=Column(String(200),nullable=False)
    source_url=Column(Text);query_used=Column(String(200))
    payload=Column(J,nullable=False)
    __table_args__=(Index('ix_raw_source_record','job_id','source','source_record_id'),)
class BusinessEntity(Identity,Base):
    __tablename__='business_entities'
    job_id=Column(Uuid,ForeignKey('search_jobs.id'),index=True,nullable=False)
    name=Column(String(500),nullable=False,index=True)
    entity_type=Column(String(100),index=True);facility_type=Column(String(100))
    category=Column(String(200),index=True);description=Column(Text)
    website=Column(Text);phone=Column(String(40));email=Column(String(320));whatsapp=Column(Text)
    address=Column(Text);locality=Column(String(200));city=Column(String(200));district=Column(String(200))
    state=Column(String(200));postal_code=Column(String(40));country=Column(String(200))
    latitude=Column(Float);longitude=Column(Float)
    rating=Column(Float);review_count=Column(Integer)
    source_count=Column(Integer,default=1);completeness_score=Column(Integer,default=0)
    confidence_score=Column(Float,default=0)
    doctor_count=Column(Integer);online_booking=Column(Boolean);emergency_available=Column(Boolean)
    is_demo=Column(Boolean,default=False);possible_duplicate=Column(Boolean,default=False)
    updated_at=Column(DateTime(timezone=True),default=now,onupdate=now)
    last_verified_at=Column(DateTime(timezone=True))
class EntityLocation(Identity,Base):
    __tablename__='entity_locations'
    entity_id=Column(Uuid,ForeignKey('business_entities.id'),index=True,nullable=False,unique=True)
    point=Column(Geography(geometry_type='POINT',srid=4326,spatial_index=False).with_variant(Text,'sqlite'),nullable=False)
Index('ix_entity_location_point',EntityLocation.point,postgresql_using='gist').ddl_if(dialect='postgresql')
class EntityContact(Identity,Base):
    __tablename__='entity_contacts'
    entity_id=Column(Uuid,ForeignKey('business_entities.id'),index=True,nullable=False)
    kind=Column(String(50),nullable=False);value=Column(Text,nullable=False)
class EntitySource(Identity,Base):
    __tablename__='entity_sources'
    entity_id=Column(Uuid,ForeignKey('business_entities.id'),index=True,nullable=False)
    observation_id=Column(Uuid,ForeignKey('raw_observations.id'),nullable=False,unique=True)
class Evidence(Identity,Base):
    __tablename__='entity_attribute_evidence'
    entity_id=Column(Uuid,ForeignKey('business_entities.id'),index=True,nullable=False)
    attribute_name=Column(String(100),nullable=False);value_text=Column(Text,nullable=False)
    source_url=Column(Text);source_name=Column(String(100));source_record_id=Column(String(200))
    evidence_text=Column(Text);extraction_method=Column(String(50),nullable=False)
    confidence=Column(Float,nullable=False);retrieved_at=Column(DateTime(timezone=True),default=now)
class MergeEvent(Identity,Base):
    __tablename__='entity_merge_events'
    entity_id=Column(Uuid,ForeignKey('business_entities.id'),index=True,nullable=False)
    observation_id=Column(Uuid,ForeignKey('raw_observations.id'),nullable=False)
    score=Column(Integer,nullable=False);signals=Column(J,nullable=False);action=Column(String(30),nullable=False)
class CrawlPage(Identity,Base):
    __tablename__='crawl_pages'
    entity_id=Column(Uuid,ForeignKey('business_entities.id'),index=True,nullable=False)
    url=Column(Text,nullable=False);status=Column(String(40));content_hash=Column(String(64))
    error=Column(Text);extracted=Column(J)
class ExportJob(Identity,Base):
    __tablename__='export_jobs'
    job_id=Column(Uuid,ForeignKey('search_jobs.id'),index=True,nullable=False)
    format=Column(String(10),nullable=False);request=Column(J,nullable=False)
    payload=Column(LargeBinary);status=Column(String(30),default='queued');path=Column(Text);error=Column(Text);duration_seconds=Column(Float)
DIMENSIONS={}
for name in ['categories','specialties','subspecialties','services']:
    table=Table(name,Base.metadata,Column('id',Uuid,primary_key=True,default=uuid4),Column('key',String(200),unique=True,nullable=False),Column('label',String(200),nullable=False))
    link=Table('entity_'+name,Base.metadata,Column('id',Uuid,primary_key=True,default=uuid4),Column('entity_id',Uuid,ForeignKey('business_entities.id'),nullable=False,index=True),Column('term_id',Uuid,ForeignKey(name+'.id'),nullable=False),UniqueConstraint('entity_id','term_id'))
    DIMENSIONS[name]=(table,link)

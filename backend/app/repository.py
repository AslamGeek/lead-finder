from uuid import UUID
from datetime import date,datetime
from sqlalchemy import select,func,or_,cast
from geoalchemy2 import Geography
from .models import BusinessEntity,EntityLocation,DIMENSIONS,Evidence,EntitySource,Observation
from .rules import distance_km,confidence_band
def value(v):
    if isinstance(v,(UUID,datetime,date)): return str(v)
    return v
def columns(obj):
    return {c.name:value(getattr(obj,c.name)) for c in obj.__table__.columns}
FILTER_KEYS={'search','entity_type','category','specialty','min_rating','min_reviews','has_website','has_email','has_whatsapp','max_distance','bbox'}
def query_entities(job,filters):
    unknown=set(filters)-FILTER_KEYS
    if unknown: raise ValueError('Unknown filters: '+', '.join(sorted(unknown)))
    q=select(BusinessEntity).where(BusinessEntity.job_id==job.id)
    for name in ['entity_type','category']:
        if filters.get(name): q=q.where(getattr(BusinessEntity,name)==filters[name])
    if filters.get('search'):
        term=str(filters['search'])[:200].replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        q=q.where(or_(BusinessEntity.name.ilike('%'+term+'%',escape='\\'),BusinessEntity.address.ilike('%'+term+'%',escape='\\')))
    if filters.get('specialty'):
        table,link=DIMENSIONS['specialties']
        q=q.where(BusinessEntity.id.in_(select(link.c.entity_id).join(table,link.c.term_id==table.c.id).where(table.c.label==filters['specialty'])))
    for key,col in [('min_rating','rating'),('min_reviews','review_count')]:
        if filters.get(key) not in (None,''):
            n=float(filters[key])
            if not 0<=n<= (5 if key=='min_rating' else 10000000): raise ValueError('Invalid '+key)
            q=q.where(getattr(BusinessEntity,col)>=n)
    for key,col in [('has_website','website'),('has_email','email'),('has_whatsapp','whatsapp')]:
        if filters.get(key) not in (None,''):
            if str(filters[key]).lower() not in ('true','false'): raise ValueError('Invalid boolean filter')
            q=q.where(getattr(BusinessEntity,col).is_not(None) if str(filters[key]).lower()=='true' else getattr(BusinessEntity,col).is_(None))
    if filters.get('bbox') or filters.get('max_distance'):
        q=q.join(EntityLocation,EntityLocation.entity_id==BusinessEntity.id)
    if filters.get('bbox'):
        box=filters['bbox']
        if isinstance(box,str): box=box.split(',')
        if len(box)!=4: raise ValueError('bbox requires west,south,east,north')
        w,s,e,n=map(float,box)
        if not (-180<=w<e<=180 and -90<=s<n<=90): raise ValueError('Invalid bounding box')
        q=q.where(func.ST_Intersects(EntityLocation.point,cast(func.ST_MakeEnvelope(w,s,e,n,4326),Geography)))
    if filters.get('max_distance'):
        radius=float(filters['max_distance'])
        if not 0<radius<=100: raise ValueError('Distance must be between 0 and 100 km')
        loc=job.request['location']
        center=func.ST_SetSRID(func.ST_MakePoint(loc['longitude'],loc['latitude']),4326)
        q=q.where(func.ST_DWithin(EntityLocation.point,cast(center,Geography),radius*1000))
    return q
def ordered(q,sort,job):
    descending=sort.startswith('-');key=sort.lstrip('-')
    allowed={'name','entity_type','category','rating','review_count','source_count','completeness_score','confidence_score','city'}
    if key=='distance_km':
        loc=job.request['location']
        center=cast(func.ST_SetSRID(func.ST_MakePoint(loc['longitude'],loc['latitude']),4326),Geography)
        point=select(EntityLocation.point).where(EntityLocation.entity_id==BusinessEntity.id).scalar_subquery()
        col=func.ST_Distance(point,center)
    elif key in allowed: col=getattr(BusinessEntity,key)
    else: raise ValueError('Invalid sort column')
    return q.order_by((col.desc() if descending else col.asc()).nullslast(),BusinessEntity.id)
def serialize_entity(session,entity,job,detail=False):
    result=columns(entity)
    for key,(table,link) in DIMENSIONS.items():
        terms=session.execute(select(table.c.key,table.c.label).join(link,link.c.term_id==table.c.id).where(link.c.entity_id==entity.id)).all()
        result[key]=[x.label for x in terms]
    loc=job.request['location']
    d=distance_km(loc['latitude'],loc['longitude'],entity.latitude,entity.longitude)
    result['distance_km']=round(d,2) if d is not None else None
    result['confidence']=confidence_band(entity.confidence_score)
    if detail:
        result['evidence']=[columns(x) for x in session.scalars(select(Evidence).where(Evidence.entity_id==entity.id))]
        result['sources']=sources(session,entity.id)
    return result
def sources(session,entity_id):
    return [o.payload for o in session.scalars(select(Observation).join(EntitySource,EntitySource.observation_id==Observation.id).where(EntitySource.entity_id==entity_id))]

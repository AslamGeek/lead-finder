import asyncio,secrets,logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from uuid import UUID
from pathlib import Path
from fastapi import FastAPI,APIRouter,Depends,HTTPException,Header,Query,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import select,func,text
from .config import settings
from .db import Session,engine,get_session
from .models import Base,SearchJob,Location,BusinessEntity,ExportJob
from .schemas import SearchRequest,ExportRequest
from .repository import columns,query_entities,ordered,serialize_entity,sources,FILTER_KEYS
from .sources import PhotonProvider
from .demo import LOCATIONS
from .rules import TaxonomyService,distance_km
logging.basicConfig(level=logging.INFO,format='%(message)s')
TERMINAL={'completed','partially_completed','failed','cancelled'}
pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='demo-job')
@asynccontextmanager
async def lifespan(app):
    if settings.app_mode=='demo':
        Base.metadata.create_all(engine)
        with Session() as session:
            for job in session.scalars(select(SearchJob).where(SearchJob.stage.not_in(TERMINAL))):
                job.stage='failed';job.errors=[{'error':'Local demo process restarted before job completion'}]
            for export in session.scalars(select(ExportJob).where(ExportJob.status=='queued')):
                export.status='failed';export.error='Local demo process restarted'
            session.commit()
    yield
app=FastAPI(title='FieldAtlas API',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.allowed_origins,allow_credentials=False,allow_methods=['GET','POST','OPTIONS'],allow_headers=['Content-Type','X-API-Key'])
def auth(x_api_key:str|None=Header(default=None)):
    if settings.api_key and not secrets.compare_digest(x_api_key or '',settings.api_key):raise HTTPException(401,'A valid workspace API key is required')
api=APIRouter(prefix='/api',dependencies=[Depends(auth)])
def get_or_404(session,model,id):
    obj=session.get(model,id)
    if not obj:raise HTTPException(404,'Record not found')
    return obj
@app.get('/health')
def health():
    return {'status':'ok','mode':settings.app_mode}
@api.get('/meta')
def meta():
    return {'mode':settings.app_mode,'taxonomy':TaxonomyService().rules,'max_terms':15}
@api.get('/locations/autocomplete')
async def autocomplete(q:str=Query(min_length=2,max_length=100),mode:str='live'):
    if mode=='demo':return [x for x in LOCATIONS if q.casefold() in x['display_name'].casefold()]
    if mode!='live':raise HTTPException(422,'Invalid mode')
    try:return await PhotonProvider().autocomplete(q)
    except Exception:raise HTTPException(502,'Location provider is unavailable. Please retry.')
@api.get('/search-jobs')
def jobs(session=Depends(get_session)):
    return [columns(x) for x in session.scalars(select(SearchJob).order_by(SearchJob.created_at.desc()).limit(30))]
@api.post('/search-jobs',status_code=201)
def create_job(request:SearchRequest,session=Depends(get_session)):
    if request.mode=='live' and settings.app_mode!='live':raise HTTPException(409,'This API is in demo mode. Configure PostgreSQL/PostGIS and Redis, then set APP_MODE=live.')
    active=session.scalar(select(func.count()).select_from(SearchJob).where(SearchJob.stage.not_in(TERMINAL)))
    if active>=3:raise HTTPException(429,'Three jobs are already active. Wait or cancel one before starting another.')
    loc=Location(**request.location.model_dump())
    session.add(loc);session.flush()
    job=SearchJob(location_id=loc.id,request=request.model_dump(mode='json'))
    session.add(job);session.commit()
    try:
        if settings.app_mode=='demo':
            from .pipeline import run_pipeline
            pool.submit(lambda:asyncio.run(run_pipeline(job.id)))
        else:
            from .tasks import discover
            discover.delay(str(job.id))
    except Exception:
        job.stage='failed';job.errors=[{'stage':'queued','error':'Worker queue unavailable'}];session.commit()
        raise HTTPException(503,'Job saved but worker queue is unavailable')
    return columns(job)
@api.get('/search-jobs/{job_id}')
def get_job(job_id:UUID,session=Depends(get_session)):return columns(get_or_404(session,SearchJob,job_id))
@api.post('/search-jobs/{job_id}/cancel')
def cancel(job_id:UUID,session=Depends(get_session)):
    job=get_or_404(session,SearchJob,job_id)
    if job.stage not in TERMINAL:
        job.cancel_requested=True
        if job.stage=='queued':job.stage='cancelled'
        session.commit()
    return columns(job)
def filtered_rows(session,job,filters,sort):
    # SQLite is restricted to the small fictional local demonstration.
    if session.bind.dialect.name=='sqlite':
        spatial={k:filters.get(k) for k in ['bbox','max_distance']}
        q=query_entities(job,{k:v for k,v in filters.items() if k not in spatial})
        entities=list(session.scalars(ordered(q,sort if sort.lstrip('-')!='distance_km' else 'name',job)))
        rows=[serialize_entity(session,e,job) for e in entities]
        if spatial['max_distance']:
            try:r=float(spatial['max_distance'])
            except ValueError:raise ValueError('Invalid distance')
            if not 0<r<=100:raise ValueError('Distance must be between 0 and 100 km')
            rows=[x for x in rows if x['distance_km'] is not None and x['distance_km']<=r]
        if spatial['bbox']:
            w,s,e,n=map(float,spatial['bbox'].split(','))
            if not (-180<=w<e<=180 and -90<=s<n<=90):raise ValueError('Invalid bounding box')
            rows=[x for x in rows if x['longitude'] is not None and x['latitude'] is not None and w<=x['longitude']<=e and s<=x['latitude']<=n]
        if sort.lstrip('-')=='distance_km':rows.sort(key=lambda x:x['distance_km'] if x['distance_km'] is not None else float('inf'),reverse=sort.startswith('-'))
        return rows
    return None
@api.get('/entities')
def entities(request:Request,job_id:UUID,page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=100),sort:str='name',session=Depends(get_session)):
    job=get_or_404(session,SearchJob,job_id)
    unknown=set(request.query_params)-FILTER_KEYS-{'job_id','page','page_size','sort'}
    if unknown:raise HTTPException(422,'Unknown filters: '+', '.join(sorted(unknown)))
    filters={k:v for k,v in request.query_params.items() if k in FILTER_KEYS and v!=''}
    try:
        demo=filtered_rows(session,job,filters,sort)
        if demo is not None:return {'items':demo[(page-1)*page_size:page*page_size],'total':len(demo),'page':page,'page_size':page_size}
        q=query_entities(job,filters);total=session.scalar(select(func.count()).select_from(q.subquery()))
        items=session.scalars(ordered(q,sort,job).offset((page-1)*page_size).limit(page_size))
        return {'items':[serialize_entity(session,x,job) for x in items],'total':total,'page':page,'page_size':page_size}
    except (ValueError,TypeError):raise HTTPException(422,'Invalid filter or sort value')
@api.get('/entities/{entity_id}')
def entity(entity_id:UUID,session=Depends(get_session)):
    e=get_or_404(session,BusinessEntity,entity_id)
    return serialize_entity(session,e,session.get(SearchJob,e.job_id),True)
@api.get('/entities/{entity_id}/sources')
def entity_sources(entity_id:UUID,session=Depends(get_session)):
    get_or_404(session,BusinessEntity,entity_id);return sources(session,entity_id)
@api.post('/exports',status_code=201)
def create_export(request:ExportRequest,session=Depends(get_session)):
    job=get_or_404(session,SearchJob,request.job_id)
    if job.stage not in ('completed','partially_completed'):raise HTTPException(409,'Wait until the search is complete')
    if request.scope=='selected':
        count=session.scalar(select(func.count()).select_from(BusinessEntity).where(BusinessEntity.job_id==job.id,BusinessEntity.id.in_(request.entity_ids)))
        if count!=len(set(request.entity_ids)):raise HTTPException(422,'Selected entities must belong to this search job')
    try:query_entities(job,{k:v for k,v in request.filters.items() if k not in ('bbox','max_distance')})
    except ValueError:raise HTTPException(422,'Invalid export filters')
    export=ExportJob(job_id=job.id,format=request.format,request=request.model_dump(mode='json'))
    session.add(export);session.commit()
    try:
        if settings.app_mode=='demo':
            from .exports import run_export
            pool.submit(run_export,export.id)
        else:
            from .tasks import export as export_task
            export_task.delay(str(export.id))
    except Exception:
        export.status='failed';export.error='Worker queue unavailable';session.commit()
        raise HTTPException(503,'Export queue unavailable')
    return {k:v for k,v in columns(export).items() if k!='payload'}
@api.get('/exports/{export_id}')
def export_status(export_id:UUID,session=Depends(get_session)):
    ex=get_or_404(session,ExportJob,export_id)
    return {k:v for k,v in columns(ex).items() if k!='payload'}
@api.get('/exports/{export_id}/download')
def download(export_id:UUID,session=Depends(get_session)):
    ex=get_or_404(session,ExportJob,export_id)
    if ex.status!='completed' or ex.payload is None:raise HTTPException(409,'Export is not ready')
    media={'csv':'text/csv','json':'application/json','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}[ex.format]
    return Response(content=ex.payload,media_type=media,headers={'Content-Disposition':f'attachment; filename="fieldatlas-{ex.id}.{ex.format}"'})
app.include_router(api)

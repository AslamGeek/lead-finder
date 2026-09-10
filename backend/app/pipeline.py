import asyncio,json,logging,time
from datetime import datetime,timezone
from sqlalchemy import select,insert
from .db import Session
from .models import *
from .schemas import SearchRequest
from .sources import DemoSource,OverpassSource
from .rules import TaxonomyService,normalize,normalize_phone,normalize_url,match_score,completeness,distance_km
from .crawler import Crawler
from .config import settings
log=logging.getLogger('fieldatlas')
class Cancelled(Exception): pass
def stage(session,job,name,percent):
    session.refresh(job)
    if job.cancel_requested: raise Cancelled()
    job.stage=name;job.progress_percent=percent
    session.commit()
    log.info(json.dumps({'job_id':str(job.id),'stage':name,'status':'running'}))
def assign_terms(session,entity,classified):
    names={'category':'categories','specialty':'specialties','subspecialty':'subspecialties','service':'services'}
    for term in classified:
        table,link=DIMENSIONS[names[term['dimension']]]
        found=session.execute(select(table.c.id).where(table.c.key==term['key'])).scalar()
        if found is None:
            # Race-safe deterministic term UUID and dialect-aware conflict handling.
            from uuid import uuid5,NAMESPACE_URL
            found=uuid5(NAMESPACE_URL,'fieldatlas:'+term['dimension']+':'+term['key'])
            if session.bind.dialect.name=='postgresql':
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                session.execute(pg_insert(table).values(id=found,key=term['key'],label=term['label']).on_conflict_do_nothing())
            else: session.execute(insert(table).values(id=found,key=term['key'],label=term['label']))
        session.execute(insert(link).values(entity_id=entity.id,term_id=found))
def evidence(session,entity,attribute,val,raw,method='source_api',confidence=.95,text=None):
    if val is None: return
    session.add(Evidence(entity_id=entity.id,attribute_name=attribute,value_text=str(val),source_url=raw.source_url,source_name=raw.source,source_record_id=raw.source_record_id,evidence_text=text or str(val),extraction_method=method,confidence=confidence,retrieved_at=raw.retrieved_at))
async def run_pipeline(job_id,session_factory=Session):
    started=time.monotonic()
    with session_factory() as session:
        job=session.get(SearchJob,job_id)
        if not job or job.stage!='queued': return
        # Lock ensures two deliveries cannot execute the same job concurrently.
        job=session.scalar(select(SearchJob).where(SearchJob.id==job_id).with_for_update())
        if job.stage!='queued': return
        errors=[];groups=[];raw_pairs=[]
        try:
            stage(session,job,'planning',5)
            request=SearchRequest.model_validate(job.request)
            tax=TaxonomyService();normalized,variants=tax.expand(request.terms)
            job.normalized_terms=normalized;job.query_variants=variants;session.commit()
            source=DemoSource() if request.mode=='demo' else OverpassSource()
            stage(session,job,'discovering',12)
            seen=set()
            for index,query in enumerate(variants):
                stage(session,job,'discovering',12+int(25*index/max(1,len(variants))))
                session.add(SearchQuery(job_id=job.id,query=query,source=source.name))
                try:
                    rows=await source.search(query,request.location,request.radius_km if request.scope=='radius' else None)
                    for raw in rows[:settings.max_results_per_query]:
                        key=(raw.source,raw.source_record_id)
                        if key in seen: continue
                        seen.add(key)
                        if request.scope=='city':
                            w,s,e,n=request.location.bounding_box
                            if raw.longitude is None or raw.latitude is None or not (w<=raw.longitude<=e and s<=raw.latitude<=n): continue
                        elif raw.latitude is not None and raw.longitude is not None:
                            if distance_km(request.location.latitude,request.location.longitude,raw.latitude,raw.longitude)>request.radius_km: continue
                        record=Observation(job_id=job.id,source=raw.source,source_record_id=raw.source_record_id,source_url=raw.source_url,query_used=query,payload=raw.model_dump(mode='json'))
                        session.add(record);session.flush();raw_pairs.append((raw,record))
                    job.queries_executed+=1
                except Exception as exc:
                    errors.append({'source':source.name,'query':query,'stage':'discovering','error':str(exc)[:500]})
                job.raw_observations=len(raw_pairs);job.errors=list(errors);session.commit()
            stage(session,job,'resolving_entities',42)
            for raw,record in raw_pairs:
                clean={'name':raw.name.strip(),'phone':normalize_phone(raw.phone_raw),'website':normalize_url(raw.website_raw),'address':raw.address_raw,'latitude':raw.latitude,'longitude':raw.longitude}
                candidates=[(match_score(clean,g['clean']),g) for g in groups]
                best=max(candidates,key=lambda x:x[0][0]) if candidates else None
                if best and best[0][0]>=70:
                    group=best[1];group['observations'].append((raw,record))
                    group['merges'].append((record,best[0][0],best[0][1],'merged'))
                    job.duplicate_merges+=1
                    for key,val in clean.items():
                        if group['clean'].get(key) is None and val is not None: group['clean'][key]=val
                else:
                    group={'clean':clean,'observations':[(raw,record)],'merges':[],'possible_duplicate':bool(best and best[0][0]>=50)}
                    if group['possible_duplicate']: group['merges'].append((record,best[0][0],best[0][1],'flagged'))
                    groups.append(group)
            stage(session,job,'enriching',55)
            crawler=Crawler();domain_cache={};crawl_pages=0
            for index,group in enumerate(groups):
                stage(session,job,'enriching',55+int(20*index/max(1,len(groups))))
                group['pages']=[]
                if settings.crawl_enabled and group['clean']['website'] and request.mode=='live':
                    from urllib.parse import urlsplit
                    domain=urlsplit(group['clean']['website']).hostname
                    if domain not in domain_cache:
                        if crawl_pages>=settings.max_crawl_pages_per_job:
                            errors.append({'stage':'enriching','error':'Job crawl-page budget reached; remaining websites left unknown'})
                            continue
                        domain_cache[domain]=await crawler.crawl(group['clean']['website'])
                        crawl_pages+=len(domain_cache[domain])
                    group['pages']=domain_cache[domain]
                    job.pages_crawled+=len(group['pages'])
                    if any('error' not in p for p in group['pages']): job.entities_enriched+=1
                    for page in group['pages']:
                        if page.get('error'): errors.append({'stage':'enriching','url':page['url'],'error':page['error']})
            stage(session,job,'categorizing',78)
            for group in groups:
                raw,record=group['observations'][0];clean=group['clean']
                source_text=' '.join(r.name+' '+(r.category_raw or '')+' '+' '.join(r.metadata.get('services',[])) for r,_ in group['observations'])
                text=source_text+' '+' '.join(p.get('text','') for p in group['pages'])
                classified=tax.classify(text)
                entity_type=raw.metadata.get('entity_type')
                if not entity_type:
                    for kind,words in [('hospital',['hospital']),('clinic',['clinic']),('doctor',['doctors','doctor']),('school',['school']),('restaurant',['restaurant']),('hotel',['hotel']),('retail',['shop'])]:
                        if any(w in normalize(source_text).split() for w in words): entity_type=kind;break
                category=next((x['label'] for x in classified if x['dimension']=='category'),None)
                if not category and any(x['dimension']=='specialty' for x in classified): category='Healthcare'
                entity=BusinessEntity(job_id=job.id,**clean,entity_type=entity_type,facility_type='multispecialty_hospital' if 'multispecialty' in normalize(raw.name) else None,category=category,city=request.location.city,district=request.location.district,state=request.location.state,country=request.location.country,rating=raw.rating,review_count=raw.review_count,source_count=len(set(r.source for r,_ in group['observations'])),confidence_score=.95,is_demo=raw.is_demo,possible_duplicate=group['possible_duplicate'],last_verified_at=None if raw.is_demo else raw.retrieved_at)
                # Location components are provider fields only; a radius search does not establish an entity's city.
                if not raw.is_demo:
                    tags=raw.metadata.get('tags',{})
                    entity.city=tags.get('addr:city');entity.district=tags.get('addr:district');entity.state=tags.get('addr:state');entity.country=tags.get('addr:country')
                session.add(entity);session.flush()
                if entity.latitude is not None and entity.longitude is not None:
                    session.add(EntityLocation(entity_id=entity.id,point=f'SRID=4326;POINT({entity.longitude} {entity.latitude})'))
                for r,o in group['observations']:
                    session.add(EntitySource(entity_id=entity.id,observation_id=o.id))
                    for field,raw_field in [('name','name'),('phone','phone_raw'),('website','website_raw'),('address','address_raw'),('latitude','latitude'),('longitude','longitude'),('rating','rating'),('review_count','review_count')]:
                        evidence(session,entity,field,getattr(r,raw_field),r)
                for page in group['pages']:
                    session.add(CrawlPage(entity_id=entity.id,url=page['url'],status='failed' if page.get('error') else 'completed',error=page.get('error'),content_hash=page.get('hash'),extracted={k:v for k,v in page.items() if k not in ('text','error')}))
                    if page.get('error'): continue
                    for field in ['email','phone','whatsapp','address']:
                        val=page.get(field)
                        if field=='phone': val=normalize_phone(val)
                        if val and not getattr(entity,field): setattr(entity,field,val)
                        if val:
                            session.add(Evidence(entity_id=entity.id,attribute_name=field,value_text=val,source_url=page['url'],source_name='official_website',extraction_method=page.get('methods',{}).get(field,'regex'),evidence_text=val,confidence=.9))
                for field in ['phone','email','whatsapp']:
                    if getattr(entity,field): session.add(EntityContact(entity_id=entity.id,kind=field,value=getattr(entity,field)))
                assign_terms(session,entity,classified)
                for term in classified:
                    # Every matched source/page keeps its own classification provenance.
                    for r,_ in group['observations']:
                        source_hits=tax.classify(r.name+' '+(r.category_raw or '')+' '+' '.join(r.metadata.get('services',[])))
                        for hit in source_hits:
                            if hit['key']==term['key']:evidence(session,entity,term['dimension'],term['label'],r,'keyword_match',.9,json.dumps(hit['signals']))
                    for page in group['pages']:
                        for hit in tax.classify(page.get('text','')):
                            if hit['key']==term['key']:session.add(Evidence(entity_id=entity.id,attribute_name=term['dimension'],value_text=term['label'],source_url=page['url'],source_name='official_website',extraction_method='keyword_match',confidence=.9,evidence_text=json.dumps(hit['signals'])))
                for o,score,signals,action in group['merges']: session.add(MergeEvent(entity_id=entity.id,observation_id=o.id,score=score,signals=signals,action=action))
                clean.update({'email':entity.email,'phone':entity.phone,'source_count':entity.source_count,'category':category,'services':[t['label'] for t in classified if t['dimension']=='service'],'last_verified_at':entity.last_verified_at})
                entity.completeness_score=completeness(clean)
                group['entity']=entity
            session.commit()
            stage(session,job,'calculating_metrics',95)
            job.unique_entities=len(groups);job.errors=errors
            job.stage='partially_completed' if errors and groups else 'failed' if errors and not groups else 'completed'
            job.progress_percent=100
        except Cancelled:
            session.rollback();session.refresh(job);job.stage='cancelled'
        except Exception as exc:
            session.rollback();session.refresh(job);job.stage='failed';job.errors=errors+[{'stage':job.stage,'error':str(exc)[:500]}]
            log.exception(json.dumps({'job_id':str(job.id),'status':'failed'}))
        job.completed_at=datetime.now(timezone.utc);job.duration_seconds=round(time.monotonic()-started,2)
        session.commit()
        log.info(json.dumps({'job_id':str(job.id),'status':job.stage,'duration':job.duration_seconds,'raw_observations':job.raw_observations,'unique_entities':job.unique_entities,'duplicate_merges':job.duplicate_merges}))

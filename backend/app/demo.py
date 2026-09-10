"""Fictional fixtures only. Never used in live discovery."""
from uuid import uuid5, NAMESPACE_URL
from .schemas import RawObservation
KADAPA = {'provider_id':'demo:kadapa','display_name':'Kadapa, Andhra Pradesh, India','city':'Kadapa','district':'YSR Kadapa','state':'Andhra Pradesh','country':'India','latitude':14.4673,'longitude':78.8242,'bounding_box':[78.75,14.40,78.91,14.54]}
LOCATIONS=[KADAPA,{**KADAPA,'provider_id':'demo:kadiri','display_name':'Kadiri, Andhra Pradesh, India','city':'Kadiri','district':'Sri Sathya Sai','latitude':14.112,'longitude':78.16,'bounding_box':None}]
NAMES=['Cedar Bone & Joint Hospital','Meadow Orthopaedic Clinic','Riverbend Spine Centre','Northstar Multispecialty Hospital','Oakwell Joint Replacement Centre','Juniper Orthopedics','Willow Spine Clinic','Bluebird Bone & Joint Clinic','Evergreen Orthopaedic Hospital','Harbor Joint Care','Crescent Spine Clinic','Maple Multispecialty Hospital']
def observations():
    rows=[]
    for i,name in enumerate(NAMES):
        rows.append(RawObservation(source='fictional_fixture',source_record_id=f'demo-{i}',source_url=f'https://example.com/fictional/{i}',query_used='orthopaedics',name=name,category_raw='orthopedics joint replacement spine clinic' if i%3==0 else 'orthopedics',address_raw=f'{12+i*7} Example Road, Kadapa',website_raw=f'https://provider-{i}.example.com' if i%4!=3 else None,latitude=14.4673+(i-5)*.009,longitude=78.8242+((i*3)%7-3)*.008,metadata={'fixture':True,'entity_type':'hospital' if 'Hospital' in name else 'clinic','services':['knee replacement'] if i%3==0 else []},is_demo=True))
    rows.append(rows[0].model_copy(update={'source':'fictional_directory','source_record_id':'directory-0'}))
    return rows
def snapshot():
    from .rules import TaxonomyService,normalize_url,distance_km,completeness
    tax=TaxonomyService()
    entities=[]
    for i,raw in enumerate(observations()[:12]):
        categories=tax.classify(raw.name+' '+(raw.category_raw or '')+' '+' '.join(raw.metadata['services']))
        e={'id':str(uuid5(NAMESPACE_URL,raw.source_record_id)),'name':raw.name,'entity_type':raw.metadata['entity_type'],'facility_type':'multispecialty_hospital' if 'Multispecialty' in raw.name else None,'category':'Healthcare','specialties':[c['label'] for c in categories if c['dimension']=='specialty'],'subspecialties':[c['label'] for c in categories if c['dimension']=='subspecialty'],'services':raw.metadata['services'],'phone':None,'email':None,'whatsapp':None,'website':normalize_url(raw.website_raw),'address':raw.address_raw,'city':'Kadapa','latitude':raw.latitude,'longitude':raw.longitude,'rating':None,'review_count':None,'source_count':2 if i==0 else 1,'confidence_score':.95,'confidence':'High','last_verified_at':None,'is_demo':True,'distance_km':round(distance_km(KADAPA['latitude'],KADAPA['longitude'],raw.latitude,raw.longitude),2),'categories':categories,'evidence':[{'attribute_name':'name','value_text':raw.name,'source_name':raw.source,'source_url':raw.source_url,'extraction_method':'source_api','confidence':.95,'evidence_text':'Fictional development fixture. Not a verified business.'}],'sources':[raw.model_dump(mode='json')]}
        e['completeness_score']=completeness(e)
        entities.append(e)
    return {'location':KADAPA,'locations':LOCATIONS,'terms':['orthopaedics','bone & joint','joint replacement','spine clinic'],'entities':entities,'is_demo':True,'raw_observations':13}

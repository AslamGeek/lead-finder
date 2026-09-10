import asyncio
import json
import re
from abc import ABC,abstractmethod
import httpx
from .config import settings
from .schemas import GeoLocation,RawObservation,SearchRequest
from .demo import LOCATIONS,observations
from .rules import normalize,distance_km,TaxonomyService
async def request_json(method,url,**kwargs):
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout,headers={'User-Agent':settings.user_agent},follow_redirects=False) as client:
                async with client.stream(method,url,**kwargs) as response:
                    response.raise_for_status()
                    body=bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body)>8_000_000: raise ValueError('Provider response exceeds 8MB')
                    return json.loads(body)
        except (httpx.TimeoutException,httpx.NetworkError,httpx.HTTPStatusError):
            if attempt==2: raise
            await asyncio.sleep(2**attempt)
class GeocodingProvider(ABC):
    @abstractmethod
    async def autocomplete(self,q): ...
class PhotonProvider(GeocodingProvider):
    async def autocomplete(self,q):
        data=await request_json('GET','https://photon.komoot.io/api/',params={'q':q,'limit':6})
        results=[]
        for feature in data.get('features',[]):
            p=feature['properties'];lon,lat=feature['geometry']['coordinates']
            parts=list(dict.fromkeys(x for x in [p.get('name'),p.get('city'),p.get('state'),p.get('country')] if x))
            extent=p.get('extent')
            bounds=[extent[0],extent[3],extent[2],extent[1]] if extent and len(extent)==4 else None
            results.append(GeoLocation(provider_id=f"photon:{p.get('osm_type')}:{p.get('osm_id')}",display_name=', '.join(parts),city=p.get('city') or p.get('name'),district=p.get('county'),state=p.get('state'),country=p.get('country'),latitude=lat,longitude=lon,bounding_box=bounds))
        return results
class DiscoverySource(ABC):
    name:str
    @abstractmethod
    async def search(self,query,location,radius_km): ...
class DemoSource(DiscoverySource):
    name='fictional_fixture'
    async def search(self,query,location,radius_km):
        tax=TaxonomyService()
        canonical,_=tax.expand([query])
        result=[]
        for r in observations():
            content=normalize(r.name+' '+(r.category_raw or ''))
            keys=[x['key'] for x in tax.classify(content)]
            matches=normalize(query) in content or any(c in keys for c in canonical)
            distance=distance_km(location.latitude,location.longitude,r.latitude,r.longitude)
            if matches and distance is not None and (radius_km is None or distance<=radius_km):
                result.append(r.model_copy(update={'query_used':query}))
        return result
class OverpassSource(DiscoverySource):
    name='openstreetmap'
    async def search(self,query,location,radius_km):
        # Escape user text as a literal regex and then an Overpass quoted string.
        literal=re.escape(normalize(query))
        pattern=json.dumps(literal)
        if radius_km is not None:
            area=f'(around:{radius_km*1000},{location.latitude},{location.longitude})'
        elif location.bounding_box:
            w,s,e,n=location.bounding_box;area=f'({s},{w},{n},{e})'
        else: raise ValueError('City bounds unavailable')
        clauses=[f'nwr[{key}~{pattern},i]{area};' for key in ['name','healthcare:speciality','description','amenity','shop','office','tourism','leisure']]
        # Taxonomy-backed OSM tag variants preserve generic industry support.
        clean=normalize(query)
        tags=[]
        if any(t in clean for t in ['hospital','clinic','orthop','spine','joint']): tags=['["amenity"~"hospital|clinic|doctors"]','["healthcare"]']
        elif 'school' in clean: tags=['["amenity"="school"]']
        elif 'restaurant' in clean: tags=['["amenity"="restaurant"]']
        elif 'hotel' in clean: tags=['["tourism"="hotel"]']
        elif 'gym' in clean or 'fitness' in clean: tags=['["leisure"="fitness_centre"]']
        clauses.extend(f'nwr{tag}{area};' for tag in tags)
        script='[out:json][timeout:25];('+''.join(clauses)+f');out center tags {settings.max_results_per_query};'
        data=await request_json('POST','https://overpass-api.de/api/interpreter',data={'data':script})
        tax=TaxonomyService();canonical,_=tax.expand([query])
        results=[]
        for item in data.get('elements',[])[:settings.max_results_per_query]:
            t=item.get('tags',{});name=t.get('name')
            if not name: continue
            text=' '.join(str(v) for v in t.values())
            keys=[c['key'] for c in tax.classify(text)]
            # Broad tag retrieval must not silently label every hospital orthopedic.
            if tags and not (any(c in keys for c in canonical) or clean in normalize(text) or clean in ['hospital','clinic','doctor','doctors']):
                continue
            center=item.get('center',item)
            address=', '.join(t[k] for k in ['addr:housenumber','addr:street','addr:suburb','addr:city','addr:postcode'] if t.get(k))
            results.append(RawObservation(source=self.name,source_record_id=f"{item['type']}/{item['id']}",source_url=f"https://www.openstreetmap.org/{item['type']}/{item['id']}",query_used=query,name=name,category_raw=t.get('healthcare:speciality') or t.get('healthcare') or t.get('amenity') or t.get('shop') or t.get('office') or t.get('tourism'),address_raw=address or None,phone_raw=t.get('contact:phone') or t.get('phone'),website_raw=t.get('contact:website') or t.get('website'),latitude=center.get('lat'),longitude=center.get('lon'),metadata={'tags':t}))
        return results

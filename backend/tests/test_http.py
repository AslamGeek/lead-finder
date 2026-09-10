import asyncio,socket
import httpx,pytest
from app.sources import PhotonProvider,OverpassSource
from app.crawler import Crawler
from app.schemas import GeoLocation
from app.demo import KADAPA
@pytest.mark.asyncio
async def test_mocked_public_sources_return_canonical_data(monkeypatch):
    def response(request):
        if 'photon' in str(request.url):
            return httpx.Response(200,json={'features':[{'geometry':{'coordinates':[78.8242,14.4673]},'properties':{'osm_type':'R','osm_id':123,'name':'Kadapa','country':'India','extent':[78.75,14.54,78.91,14.4]}}]})
        return httpx.Response(200,json={'elements':[{'type':'node','id':1,'lat':14.46,'lon':78.82,'tags':{'name':'Test orthopedic clinic','healthcare':'clinic','healthcare:speciality':'orthopaedics'}}]})
    real=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(response),**kwargs))
    places=await PhotonProvider().autocomplete('kad')
    assert places[0].provider_id=='photon:R:123'
    rows=await OverpassSource().search('orthopaedics',GeoLocation(**KADAPA),25)
    assert len(rows)==1 and rows[0].rating is None and rows[0].source=='openstreetmap'
@pytest.mark.asyncio
async def test_crawler_validates_redirects_and_extracts_contacts(monkeypatch):
    def dns(host,*args):
        ip='127.0.0.1' if host=='private.test' else '93.184.216.34'
        return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))]
    monkeypatch.setattr(socket,'getaddrinfo',dns)
    def response(request):
        assert isinstance(request.extensions.get('sni_hostname'),str)
        if request.url.path=='/robots.txt':return httpx.Response(200,headers={'content-type':'text/plain'},text='User-agent: *\nAllow: /')
        if request.url.path=='/redirect':return httpx.Response(302,headers={'location':'http://private.test/'})
        return httpx.Response(200,headers={'content-type':'text/html'},text='<title>Example clinic</title><a href="mailto:test@example.com">Contact</a><h1>Spine surgery</h1>')
    real=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(response),**kwargs))
    with pytest.raises(ValueError):await Crawler().fetch('https://public.test/redirect')
    pages=await Crawler().crawl('https://public.test/')
    assert pages[0]['email']=='test@example.com' and 'Spine surgery' in pages[0]['headings']

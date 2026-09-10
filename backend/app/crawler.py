"""Bounded public website fetcher with DNS pinning and per-redirect validation."""
import asyncio,hashlib,ipaddress,json,re,socket
from collections import defaultdict,deque
from urllib.parse import urlsplit,urljoin,urlunsplit
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup
from .config import settings
PRIORITIES=['contact','about','services','specialties','departments','team','doctors','locations','appointments']
async def resolve_public(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
        raise ValueError('Only public HTTP(S) URLs on standard ports are allowed')
    if p.hostname.lower() in ('localhost','metadata.google.internal') or p.hostname.endswith('.localhost'):
        raise ValueError('Private destination blocked')
    infos=await asyncio.to_thread(socket.getaddrinfo,p.hostname,p.port or (443 if p.scheme=='https' else 80),0,socket.SOCK_STREAM)
    addresses=list(dict.fromkeys(i[4][0] for i in infos))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError('Non-public DNS destination blocked')
    return p,addresses[0]
class Crawler:
    def __init__(self):
        self.global_limit=asyncio.Semaphore(4)
        self.domains=defaultdict(lambda:asyncio.Semaphore(1))
    async def fetch(self,url):
        for _ in range(6):
            p,ip=await resolve_public(url)
            host=('['+ip+']') if ':' in ip else ip
            pinned=urlunsplit((p.scheme,host+(':'+str(p.port) if p.port else ''),p.path or '/',p.query,''))
            async with self.global_limit,self.domains[p.hostname]:
                async with httpx.AsyncClient(timeout=httpx.Timeout(15),trust_env=False,follow_redirects=False) as client:
                    async with client.stream('GET',pinned,headers={'Host':p.netloc,'User-Agent':settings.user_agent},extensions={'sni_hostname':p.hostname}) as response:
                        if response.is_redirect:
                            url=urljoin(url,response.headers.get('location',''));continue
                        response.raise_for_status()
                        kind=response.headers.get('content-type','').lower()
                        if not any(x in kind for x in ['text/html','text/plain','application/xhtml']):
                            raise ValueError('Non-HTML response')
                        body=bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body)>settings.max_html_bytes_per_page: raise ValueError('Page byte limit exceeded')
                        return url,body.decode('utf-8',errors='replace')
        raise ValueError('Redirect limit exceeded')
    async def crawl(self,url):
        origin=urlsplit(url)
        root=f'{origin.scheme}://{origin.netloc}/'
        robot=RobotFileParser()
        try:
            _,rules=await self.fetch(urljoin(root,'robots.txt'))
            robot.parse(rules.splitlines())
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code==404: robot.parse([])
            else: return [{'url':url,'error':'robots.txt unavailable; crawl skipped'}]
        except Exception:
            return [{'url':url,'error':'robots.txt validation failed; crawl skipped'}]
        queue=deque([(url,0)]);seen=set();pages=[]
        while queue and len(seen)<settings.max_pages_per_domain:
            current,depth=queue.popleft()
            if current in seen or depth>2: continue
            seen.add(current)
            if not robot.can_fetch(settings.user_agent,current): continue
            try:
                final,html=await self.fetch(current)
                if urlsplit(final).hostname!=origin.hostname: raise ValueError('Cross-domain redirect excluded from enrichment')
                parsed=parse_html(html,final)
                pages.append({'url':final,'hash':hashlib.sha256(html.encode()).hexdigest(),**parsed})
                soup=BeautifulSoup(html,'html.parser')
                links=[urljoin(final,a.get('href','')) for a in soup.select('a[href]')]
                links=[x.split('#')[0] for x in links if urlsplit(x).netloc==origin.netloc and any('/'+p in urlsplit(x).path.lower() for p in PRIORITIES)]
                queue.extend((x,depth+1) for x in sorted(set(links))[:settings.max_pages_per_domain])
            except Exception as exc: pages.append({'url':current,'error':str(exc)[:300]})
        return pages
def parse_html(html,url):
    soup=BeautifulSoup(html,'html.parser')
    ld=[]
    for script in soup.select('script[type="application/ld+json"]'):
        try: ld.append(json.loads(script.string or script.get_text()))
        except (ValueError,TypeError): pass
    for tag in soup(['script','style','noscript']): tag.decompose()
    text=soup.get_text(' ',strip=True)[:100000]
    links=[a.get('href','') for a in soup.select('a[href]')]
    email=next((x[7:].split('?')[0] for x in links if x.startswith('mailto:')),None)
    if not email:
        match=re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',text)
        email=match.group(0) if match else None
    phone=next((x[4:] for x in links if x.startswith('tel:')),None)
    whatsapp=next((x for x in links if urlsplit(x).hostname in ('wa.me','api.whatsapp.com')),None)
    structured=[]
    def visit(node):
        if isinstance(node,list):
            for item in node:visit(item)
        elif isinstance(node,dict):
            types=node.get('@type',[])
            types=[types] if isinstance(types,str) else types
            if any(t in ('LocalBusiness','Organization','MedicalBusiness','Hospital','MedicalClinic','Dentist','Physician','Restaurant','Hotel','School') for t in types):structured.append(node)
            for key in ('@graph','mainEntity','department'):
                if key in node:visit(node[key])
    visit(ld)
    address=None;methods={}
    for node in structured:
        for key,target in [('email','email'),('telephone','phone')]:
            val=node.get(key)
            if isinstance(val,str) and val.strip():
                if target=='email' and email is None:email=val;methods['email']='json_ld'
                if target=='phone' and phone is None:phone=val;methods['phone']='json_ld'
        a=node.get('address')
        if isinstance(a,str):address=a
        elif isinstance(a,dict):address=', '.join(str(a[k]) for k in ('streetAddress','addressLocality','addressRegion','postalCode','addressCountry') if a.get(k)) or None
        if address:methods['address']='json_ld'
    canonical=soup.select_one('link[rel="canonical"]')
    return {'address':address,'methods':methods,'email':email,'phone':phone,'whatsapp':whatsapp,'title':soup.title.get_text(strip=True) if soup.title else None,'headings':[h.get_text(' ',strip=True) for h in soup.select('h1,h2,h3')][:40],'text':text,'json_ld':ld,'canonical_url':urljoin(url,canonical['href']) if canonical and canonical.get('href') else None,'social_links':[x for x in links if urlsplit(x).hostname in ('www.facebook.com','www.instagram.com','www.linkedin.com')]}

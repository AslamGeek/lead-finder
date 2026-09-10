from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from pydantic import AliasChoices,Field,model_validator,field_validator
from pydantic_settings import BaseSettings,SettingsConfigDict
class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=('.env','.env.local'),extra='ignore',populate_by_name=True,hide_input_in_errors=True)
    app_mode:str='demo'
    database_url:str='sqlite:///./fieldatlas-demo.db'
    redis_url:str=''
    api_key:str=''
    cors_origins:str=Field(default='http://localhost:3000,http://127.0.0.1:3000',validation_alias=AliasChoices('ALLOWED_ORIGINS','CORS_ORIGINS'))
    frontend_url:str=''
    geocoding_provider:str='photon'
    geocoding_api_key:str=''
    user_agent:str='FieldAtlas/1.0 (local demo)'
    max_total_search_terms:int=Field(default=30,ge=1,le=30)
    max_expansions_per_term:int=Field(default=8,ge=1,le=8)
    max_results_per_query:int=Field(default=100,ge=1,le=100)
    max_discovery_rounds:int=2
    max_pages_per_domain:int=Field(default=8,ge=1,le=8)
    max_html_bytes_per_page:int=Field(default=1_000_000,ge=1000,le=5_000_000)
    max_crawl_pages_per_job:int=Field(default=400,ge=1,le=400)
    crawl_enabled:bool=False
    export_dir:str='./exports'
    request_timeout:float=20
    @field_validator('database_url')
    @classmethod
    def postgres_driver(cls,url):
        if url.startswith('postgres://'):url='postgresql+psycopg://'+url[len('postgres://'):]
        elif url.startswith('postgresql://'):url='postgresql+psycopg://'+url[len('postgresql://'):]
        return url
    @field_validator('redis_url')
    @classmethod
    def redis_tls(cls,url):
        if url.startswith('rediss://'):
            p=urlsplit(url);q=dict(parse_qsl(p.query));q['ssl_cert_reqs']='required'
            return urlunsplit((p.scheme,p.netloc,p.path,urlencode(q),''))
        return url
    @property
    def allowed_origins(self):
        origins=list(dict.fromkeys(x.strip().rstrip('/') for x in (self.cors_origins+','+self.frontend_url).split(',') if x.strip()))
        if any('*' in x or urlsplit(x).scheme not in ('http','https') or not urlsplit(x).netloc or urlsplit(x).path for x in origins):raise ValueError('CORS origins must be exact HTTP(S) origins')
        return origins
    @model_validator(mode='after')
    def deployment(self):
        if self.app_mode not in ('demo','live'):raise ValueError('APP_MODE must be demo or live')
        self.allowed_origins
        if self.app_mode=='live':
            if not self.database_url.startswith('postgresql+psycopg://'):raise ValueError('Live mode requires PostgreSQL/PostGIS DATABASE_URL')
            if not self.redis_url.startswith(('redis://','rediss://')):raise ValueError('Live mode requires a Redis protocol URL, not a REST URL')
            if len(self.api_key)<24:raise ValueError('Set a strong API_KEY of at least 24 characters in live mode')
        return self
settings=Settings()

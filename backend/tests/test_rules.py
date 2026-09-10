from datetime import datetime,timezone,timedelta
import pytest
from app.rules import TaxonomyService,normalize,normalize_phone,normalize_url,match_score,completeness,distance_km
from app.crawler import parse_html,resolve_public
from app.exports import export_bytes
def test_query_synonyms_are_stable_and_bounded():
    t=TaxonomyService();canonical,expanded=t.expand([' Orthopaedics ','bone & joint','arthroplasty']*10)
    assert canonical==['orthopedics','joint_replacement']
    assert len(expanded)<=30 and len(set(expanded))==len(expanded)
    assert 'knee replacement' in expanded
def test_normalization_preserves_unknowns():
    assert normalize('  Bone & Joint  ')=='bone and joint'
    assert normalize_phone('+91 (12345) 67890')=='+911234567890'
    assert normalize_phone('unknown') is None
    assert normalize_url('https://EXAMPLE.com/a#fragment')=='https://example.com/a'
    assert normalize_url('javascript:alert(1)') is None
def test_classification_uses_thresholds_and_word_boundaries():
    t=TaxonomyService()
    assert not t.classify('joint pain and bone care')
    hits=t.classify('We offer knee replacement and spine surgery.')
    assert {'joint_replacement','spine','knee_replacement'}<={h['key'] for h in hits}
    assert all(h['signals'] for h in hits)
def test_weighted_merge_preserves_distant_branches():
    a={'name':'Example clinic','phone':'+911234567890','website':'https://example.com/','latitude':14.0,'longitude':78.0,'address':'10 Main Road'}
    assert match_score(a,dict(a))[0]>=70
    assert match_score(a,{**a,'latitude':15.0})[0]<70
    assert match_score({'name':'One'},{'name':'Different'})[0]==0
def test_known_geographic_distance():
    assert distance_km(0,0,0,1)==pytest.approx(111.195,abs=.01)
    assert distance_km(None,0,0,1) is None
def test_completeness_does_not_credit_stale_verification():
    assert completeness({})==0
    assert completeness({'last_verified_at':datetime.now(timezone.utc)-timedelta(days=400)})==0
def test_json_ld_contacts_are_extracted():
    p=parse_html('<script type="application/ld+json">{"@type":"LocalBusiness","email":"hello@example.com","telephone":"+441234567890","address":{"streetAddress":"12 High St","addressLocality":"Test City"}}</script>','https://example.com/')
    assert p['email']=='hello@example.com'
    assert p['phone']=='+441234567890'
    assert '12 High St' in p['address']
@pytest.mark.asyncio
@pytest.mark.parametrize('url',['http://127.0.0.1','http://169.254.169.254/latest/meta-data','http://10.0.0.1','http://[::1]','file:///etc/passwd','http://user:pass@example.com','http://localhost'])
async def test_ssrf_rejects_private_targets(url):
    with pytest.raises((ValueError,OSError)):await resolve_public(url)
def test_exports_escape_spreadsheet_formulas_but_keep_json_exact():
    row={'id':'fixture','name':'=CMD()','phone':'+441234567890','categories':[],'sources':[]}
    assert b"'=CMD()" in export_bytes([row],{},'csv')
    assert b'"name": "=CMD()"' in export_bytes([row],{},'json')

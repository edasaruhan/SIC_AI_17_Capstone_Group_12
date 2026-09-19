"""Prediction and one-request message service. No network at import time."""
from pathlib import Path
from contextlib import contextmanager
import hashlib, json, sqlite3, time, re
import pandas as pd
import numpy as np
import joblib, requests
from features import RAW_COLUMNS
ROOT=Path(__file__).resolve().parent
POLICY={1:'Aksiyon Yok',2:'Aksiyon Yok',3:'Aksiyon Yok',4:'Etkileşim Mesajı',5:'Sadakat Teklifi',6:'Sadakat Teklifi',7:'İndirim Teklifi',8:'İndirim Teklifi',9:'Win-Back Teklifi',10:'Win-Back Teklifi'}
CATEGORIES={'Mobile':'cep telefonu','Mobile Phone':'cep telefonu','Laptop & Accessory':'bilgisayar ve aksesuar','Fashion':'moda','Grocery':'market','Others':'diğer ürünler'}

class GenerationError(Exception):
    """Only curated, secret-free messages may be exposed in the UI."""


FINISH_REASONS=frozenset({'FINISH_REASON_UNSPECIFIED','STOP','MAX_TOKENS','SAFETY',
    'RECITATION','OTHER','BLOCKLIST','PROHIBITED_CONTENT','SPII','MALFORMED_FUNCTION_CALL',
    'IMAGE_SAFETY','IMAGE_PROHIBITED_CONTENT','IMAGE_RECITATION','IMAGE_OTHER',
    'NO_IMAGE','UNEXPECTED_TOOL_CALL','TOO_MANY_TOOL_CALLS','MISSING_THOUGHT_SIGNATURE'})
BLOCK_REASONS=frozenset({'BLOCK_REASON_UNSPECIFIED','SAFETY','OTHER','BLOCKLIST',
    'PROHIBITED_CONTENT','IMAGE_SAFETY'})
TOKEN_FIELDS=('promptTokenCount','candidatesTokenCount','thoughtsTokenCount',
    'cachedContentTokenCount','toolUsePromptTokenCount','totalTokenCount')


def safe_code(value, allowed):
    if value is None:return 'bildirilmedi'
    return value if isinstance(value,str) and value in allowed else 'tanınmayan/geçersiz kod'


def valid_token_count(value):
    return type(value) is int and 0<=value<=2**63-1


def response_details(payload):
    """Allowlisted enum values and bounded integers only; never echo API text."""
    data=payload if isinstance(payload,dict) else {}
    candidates=data.get('candidates')
    candidate=candidates[0] if isinstance(candidates,list) and candidates and isinstance(candidates[0],dict) else {}
    feedback=data.get('promptFeedback')
    feedback=feedback if isinstance(feedback,dict) else {}
    usage=data.get('usageMetadata')
    usage=usage if isinstance(usage,dict) else {}
    details=[f"finishReason={safe_code(candidate.get('finishReason'),FINISH_REASONS)}",
             f"promptFeedback.blockReason={safe_code(feedback.get('blockReason'),BLOCK_REASONS)}"]
    for name in TOKEN_FIELDS:
        value=usage.get(name)
        rendered=str(value) if valid_token_count(value) else ('bildirilmedi' if name not in usage else 'geçersiz')
        details.append(f'{name}={rendered}')
    return '; '.join(details)


def response_error(message,payload):
    return GenerationError(f'Yanıt işleme hatası: {message} Taslak kaydedilmedi. Güvenli ayrıntılar: {response_details(payload)}')


def parse_message(payload):
    try:
        feedback=payload.get('promptFeedback',{})
        block=feedback.get('blockReason')
        if block is not None and block!='BLOCK_REASON_UNSPECIFIED':
            explanation='İstek güvenlik filtresi nedeniyle engellendi.' if block=='SAFETY' else 'İstek sağlayıcının içerik/politika denetimi nedeniyle engellendi.'
            raise response_error(explanation,payload)
        candidates=payload.get('candidates',[])
        if not candidates:
            raise response_error('Aday mesaj yok; yanıt boş veya engellenmiş olabilir.',payload)
        candidate=candidates[0]
        finish=candidate.get('finishReason')
        if finish=='MAX_TOKENS':
            raise response_error('Çıktı token sınırına ulaşıldı (MAX_TOKENS); mesaj tamamlanmadı.',payload)
        if finish in ('SAFETY','IMAGE_SAFETY'):
            raise response_error('Üretim güvenlik filtresi nedeniyle durduruldu (SAFETY).',payload)
        if finish in ('RECITATION','BLOCKLIST','PROHIBITED_CONTENT','SPII','IMAGE_PROHIBITED_CONTENT','IMAGE_RECITATION'):
            raise response_error('Üretim içerik, gizlilik veya alıntı denetimi nedeniyle engellendi.',payload)
        if finish!='STOP':
            raise response_error('Üretimin normal biçimde tamamlandığı doğrulanamadı; STOP durumu alınmadı.',payload)
        message=''.join(p.get('text','') for p in candidate.get('content',{}).get('parts',[]) if not p.get('thought')).strip()
        if not message:
            raise response_error('Tamamlanmış, boş olmayan bir mesaj alınamadı.',payload)
        usage=payload.get('usageMetadata',{})
        if not isinstance(usage,dict) or any(not valid_token_count(usage[name]) for name in TOKEN_FIELDS if name in usage):
            raise response_error('Yanıt şeması: token kullanım sayıları geçerli değil.',payload)
        tokens=usage.get('totalTokenCount',0)
    except (AttributeError, TypeError, ValueError, KeyError, IndexError):
        raise response_error('Yanıt şeması: mesaj veya kullanım alanları beklenen biçimde değil.',payload) from None
    return message,tokens


def request_message(prompt, key, model_name):
    """One request, certificate verification enabled, no retries or redirects."""
    try:
        response=requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent',
            headers={'x-goog-api-key':key},
            json={'contents':[{'parts':[{'text':prompt}]}],
                  'generationConfig':{'maxOutputTokens':2048,'thinkingConfig':{'thinkingLevel':'low'}}},
            timeout=(10,45), verify=True, allow_redirects=False)
    except requests.exceptions.Timeout:
        raise GenerationError('Zaman aşımı (Timeout): bağlantı 10 saniyede veya yanıt 45 saniyede tamamlanamadı. İstek sunucuya ulaşmış olabilir.') from None
    except requests.exceptions.SSLError:
        raise GenerationError('SSL hatası (SSLError): sunucu sertifikası doğrulanamadı. Sistem saatini ve güvenilir sertifika/proxy ayarlarını kontrol edin. SSL doğrulaması açık tutuldu.') from None
    except requests.exceptions.ProxyError:
        raise GenerationError('Proxy hatası (ProxyError): yapılandırılmış proxy üzerinden bağlantı kurulamadı. Proxy erişimini ve ayarlarını kontrol edin.') from None
    except requests.exceptions.ConnectionError:
        raise GenerationError('Bağlantı hatası (ConnectionError): Google sunucusuna bağlantı kurulamadı veya bağlantı kesildi. DNS, güvenlik duvarı ve uygulamanın ağ erişim iznini kontrol edin.') from None
    except requests.exceptions.HTTPError:
        raise GenerationError('HTTP hatası (HTTPError): sunucu isteği kabul etmedi.') from None
    except requests.exceptions.RequestException:
        raise GenerationError('İstek aktarım hatası (RequestException): istek hazırlanamadı veya yanıt aktarımı tamamlanamadı.') from None
    if response.status_code != 200:
        guidance={400:'İstek parametrelerini ve modelin desteklediği üretim ayarlarını kontrol edin.',
                  401:'API anahtarının geçerliliğini kontrol edin.',
                  403:'API anahtarı kısıtlarını ve model erişim izinlerini kontrol edin.',
                  404:'GEMINI_MODEL adını ve bu modele erişiminizi kontrol edin.',
                  429:'Kota veya istek sınırına ulaşıldı; hesabınızın kotasını kontrol edin.'}
        detail=guidance.get(response.status_code, 'Sunucu isteği tamamlayamadı.' if response.status_code>=500 else 'Beklenmeyen HTTP durumu; yönlendirme takip edilmedi.')
        raise GenerationError(f'HTTP hatası: {response.status_code}. {detail}')
    try:
        payload=response.json()
    except ValueError:
        raise response_error('JSON: sunucudan geçerli JSON alınamadı.',{}) from None
    return parse_message(payload)
def predict(model, raw, customer_id=None):
    score=float(model.predict_proba(raw[RAW_COLUMNS])[0,1])*100
    reference=pd.read_csv(ROOT/'data/live_reference.csv')
    same=reference[reference.CustomerID.eq(customer_id)]
    if len(same) and abs(float(same.iloc[0].LiveRiskScore)-score)<1e-4:
        segment=int(same.iloc[0].LiveSegment)
    else:
        rank=np.searchsorted(np.sort(reference.LiveRiskScore),score,side='right')
        segment=int(np.clip(np.ceil(10*rank/len(reference)),1,10))
    return {'score':score,'prediction':int(model.predict(raw[RAW_COLUMNS])[0]),'segment':segment,'action':POLICY[segment]}

def prompt_for(raw,result):
    r=raw.iloc[0]
    context={'aksiyon':result['action'],'kategori':CATEGORIES.get(str(r.PreferedOrderCat),'ürünler'),'gecmis_sikayet':bool(r.Complain==1),'onayli_teklif':None}
    return '''Türkçe e-ticaret CRM iletişim taslağı yaz. Yalnızca en fazla iki kısa cümle yaz; siz dili kullan.
İsim, indirim, fiyat, kupon, kampanya, sadakat avantajı, yeni ürün, stok veya hesaba tanımlanan teklif uydurma.
Onaylı teklif bilgisi yok; teklif gerektiren aksiyonda bile yalnızca genel bir davet yaz.
Şikâyet işareti varsa önce empati kur. Şikâyetin kategoriyle ilgili olduğunu, hâlâ açık olduğunu veya çözüldüğünü varsayma.
Kategoriyi doğal kullan. Risk, churn, segment veya tahminlerden bahsetme. Destek hizmetinin her zaman açık olduğunu iddia etme.
Müşteri bağlamı:\n'''+json.dumps(context,ensure_ascii=False)

@contextmanager
def connect():
    p=ROOT/'runtime';p.mkdir(exist_ok=True)
    db=sqlite3.connect(p/'events.sqlite',timeout=30)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS messages (key TEXT PRIMARY KEY, text TEXT, created TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS events (created TEXT, status TEXT, duration REAL, tokens INTEGER)')
        db.commit()
        with db:
            yield db
    finally:
        db.close()

def generate(prompt,key,model_name='gemini-3.6-flash',limit=10):
    if not re.fullmatch(r'[a-zA-Z0-9._-]+',model_name):raise GenerationError('Ayar hatası: geçersiz model adı.')
    if not key or key.strip()=='PASTE_YOUR_KEY_LOCALLY':raise GenerationError('Ayar hatası: yerel dosyaya geçerli bir GEMINI_API_KEY girin.')
    if not key.isascii() or any(c.isspace() for c in key):raise GenerationError('Ayar hatası: API anahtarında boşluk veya desteklenmeyen karakter var.')
    if limit<1:raise GenerationError('Ayar hatası: DAILY_REQUEST_LIMIT pozitif bir tam sayı olmalı.')
    cache_key=hashlib.sha256((model_name+'\n'+prompt).encode()).hexdigest()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT text FROM messages WHERE key=?',(cache_key,)).fetchone()
        if old:return old[0],True,None
        used=db.execute("SELECT COUNT(*) FROM events WHERE date(created)=date('now') AND status IN ('started','ok','error')").fetchone()[0]
        if used>=limit:raise GenerationError(f'Günlük uygulama sınırı ({limit} deneme) doldu.')
        cursor=db.execute("INSERT INTO events VALUES (datetime('now'),'started',0,0)")
        event=cursor.lastrowid;db.commit()
    started=time.perf_counter()
    try:
        message,tokens=request_message(prompt,key,model_name)
        with connect() as db:
            db.execute("INSERT OR REPLACE INTO messages VALUES (?,?,datetime('now'))",(cache_key,message))
            db.execute("UPDATE events SET status='ok',duration=?,tokens=? WHERE rowid=?",(time.perf_counter()-started,tokens,event))
        return message,False,tokens
    except Exception:
        try:
            with connect() as db:db.execute("UPDATE events SET status='error',duration=? WHERE rowid=?",(time.perf_counter()-started,event))
        except sqlite3.Error:
            pass  # Preserve the original error; never log exception bodies/headers.
        raise

"""Run: python -m streamlit run app.py"""
import os, json, hmac, time, sqlite3
from pathlib import Path
import pandas as pd
import joblib
import streamlit as st
from features import RAW_COLUMNS
from service import predict,prompt_for,generate,connect,GenerationError
ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='Retain | Canlı CRM',page_icon='📊',layout='wide')
def setting(name,default=''):
    # Local secrets take precedence over stale inherited environment settings.
    try:
        value=st.secrets.get(name)
    except FileNotFoundError:
        value=None
    except Exception:
        st.error('Ayar dosyası okunamadı. .streamlit/secrets.toml TOML biçimini kontrol edin. Güvenlik için ayrıntılar gösterilmedi.')
        st.stop()
    return str(value) if value is not None else os.environ.get(name,default)
password=setting('APP_PASSWORD')
if password and not st.session_state.get('authenticated'):
    st.title('Retain · Sunum erişimi')
    entered=st.text_input('Uygulama parolası',type='password')
    if st.button('Giriş yap'):
        if hmac.compare_digest(entered,password):st.session_state.authenticated=True;st.rerun()
        else:st.error('Parola yanlış.')
    st.stop()
st.markdown('<style>.stApp{background:#f4f7fb}h1,h2,h3{color:#102b49}[data-testid="stMetric"]{background:white;padding:18px;border-radius:12px;border-left:4px solid #16a58b}</style>',unsafe_allow_html=True)
@st.cache_resource
def load_model():
    windows_model=ROOT/'models/final_pipeline.windows.joblib'
    path=windows_model if os.name=='nt' and windows_model.exists() else ROOT/'models/final_pipeline.joblib'
    return joblib.load(path)
@st.cache_data
def load_csv(name):return pd.read_csv(ROOT/'data'/name)
model=load_model();metadata=json.loads((ROOT/'models/metadata.json').read_text())
customers=load_csv('customers.csv');raws=load_csv('raw_test.csv').set_index('CustomerID')
live=load_csv('live_reference.csv')
st.sidebar.title('retain.')
section=st.sidebar.radio('Çalışma alanı',['Canlı müşteri analizi','Model performansı','Aksiyon simülasyonu','Kayıtlı mesajlar','İzleme ve yöntem'])
st.sidebar.caption('Grup 12 · Samsung Innovation Campus')
st.sidebar.info('Risk analizi yerel modelle çalışır. Gemini yalnızca mesaj düğmesiyle çağrılır.')
with st.sidebar.expander('Ayar durumu (değerler gizli)'):
    for name in ['GEMINI_API_KEY','GEMINI_MODEL','APP_PASSWORD','DAILY_REQUEST_LIMIT']:
        value=setting(name)
        try:from_secrets=name in st.secrets
        except FileNotFoundError:from_secrets=False
        source='Streamlit secrets' if from_secrets else 'Ortam değişkeni / varsayılan'
        st.caption(f'{name}: {"tanımlı" if value else "eksik"} · {source}')
if not password:st.sidebar.caption('Yerel demo. İnternete açmadan önce APP_PASSWORD tanımlayın.')
if section=='Canlı müşteri analizi':
    st.title('Müşteriyi seç. Analizi çalıştır.')
    st.caption('Kaydedilmiş XGBoost modeli düğmeye basıldığında yeniden tahmin üretir.')
    ordered=live.sort_values('LiveRiskScore',ascending=False).CustomerID.tolist()
    cid=st.selectbox('Müşteri ID',ordered)
    row=raws.loc[[cid]].copy()
    st.dataframe(row,use_container_width=True)
    with st.expander('Senaryo için müşteri bilgilerini değiştir'):
        st.caption('Değişiklikler orijinal veriyi değiştirmez. Üyelik süresinin birimi veri sözlüğünde belirtilmemiştir.')
        edit=st.checkbox('Senaryo düzenlemeyi aç')
        if edit:
            for col in ['Tenure','OrderCount','CouponUsed','DaySinceLastOrder']:
                value=row.iloc[0][col]
                missing=st.checkbox(f'{col}: eksik değer',value=bool(pd.isna(value)),key=f'{cid}_{col}_missing')
                v=st.number_input(col,min_value=0.0,value=0.0 if pd.isna(value) else float(value),key=f'{cid}_{col}')
                row.loc[cid,col]=float('nan') if missing else v
            row.loc[cid,'Complain']=int(st.checkbox('Geçmiş şikâyet var',value=bool(row.iloc[0].Complain),key=f'{cid}_complaint'))
    fingerprint=row.to_json(orient='split')
    if st.button('Risk analizi yap',type='primary'):
        start=time.perf_counter();result=predict(model,row,cid)
        st.session_state.analysis=(fingerprint,result,time.perf_counter()-start)
        st.session_state.pop('message',None)
    analysis=st.session_state.get('analysis')
    if analysis and analysis[0]==fingerprint:
        result=analysis[1];cols=st.columns(3)
        cols[0].metric('Model skoru / 100',f"{result['score']:.2f}")
        cols[1].metric('Göreli risk dilimi',f"{result['segment']} / 10")
        cols[2].metric('Önerilen aksiyon',result['action'])
        st.caption(f'Gerçek model hesaplaması: {analysis[2]*1000:.1f} ms. Skor kalibre edilmiş olasılık değildir.')
        st.info('Aksiyon, varsayımsal simülasyonda öğrenilen politikaya dayanır; gerçek kampanya etkisi veya risk azalması kanıtı değildir.')
        if result['action']=='Aksiyon Yok':st.success('Bu müşteri için pazarlama mesajı önerilmiyor. Şikâyet incelemesi ayrıca yapılabilir.')
        else:
            prompt=prompt_for(row,result)
            with st.expander('Gemini’ye gönderilecek prompt'):st.code(prompt,language=None)
            api_key=setting('GEMINI_API_KEY');model_name=setting('GEMINI_MODEL','gemini-3.6-flash')
            st.caption(f'Model: {model_name}. Onaylı kampanya bilgisi yok; teklif içermeyen taslak hazırlanır.')
            if not api_key:st.warning('Canlı mesaj için .streamlit/secrets.toml dosyasına GEMINI_API_KEY ekleyin. Anahtarı sohbete veya GitHub’a koymayın.')
            if st.button('Gemini ile mesaj üret',disabled=not bool(api_key)):
                st.session_state.pop('message',None)
                try:
                    try:daily_limit=int(setting('DAILY_REQUEST_LIMIT','10'))
                    except (ValueError,TypeError):raise GenerationError('Ayar hatası: DAILY_REQUEST_LIMIT tam sayı olmalı.') from None
                    with st.spinner('Mesaj hazırlanıyor…'):
                        message,cached,tokens=generate(prompt,api_key,model_name,daily_limit)
                    st.session_state.message=(fingerprint,message,cached,tokens)
                except GenerationError as error:st.error(f'{error} Otomatik tekrar yapılmadı.')
                except sqlite3.Error:st.error('Yerel kayıt hatası (SQLite): runtime klasörünün yazma iznini ve veritabanı erişimini kontrol edin. Otomatik tekrar yapılmadı.')
                except Exception as error:st.error(f'Beklenmeyen uygulama hatası ({type(error).__name__}): mesaj işlemi tamamlanamadı. Güvenlik için ham hata ayrıntıları gizlendi. Otomatik tekrar yapılmadı.')
            msg=st.session_state.get('message')
            if msg and msg[0]==fingerprint:
                st.subheader('İletişim taslağı');st.write(msg[1])
                st.caption(('Daha önce üretilen sonuç kullanıldı; yeni istek yok.' if msg[2] else f'Canlı Gemini çıktısı · toplam token: {msg[3]}')+' İnsan incelemesi bekliyor; gönderim yapılmadı.')
                st.download_button('Taslağı indir',msg[1],file_name=f'mesaj_{cid}.txt')
elif section=='Model performansı':
    st.title('Çalışan modelin performansı')
    st.caption('Bu sayfadaki test sonuçları paket içindeki eğitilmiş modelden hesaplandı.')
    for col,(name,value) in zip(st.columns(5),metadata['metrics'].items()):col.metric(name,f'{value:.4f}')
    st.dataframe(pd.DataFrame(metadata['confusion_matrix'],index=['Gerçek: churn yok','Gerçek: churn var'],columns=['Tahmin: yok','Tahmin: var']))
    st.info(f"Notebook ile karşılaştırma: {metadata['prediction_disagreements']} farklı sınıf tahmini; en büyük skor farkı {metadata['max_score_difference']:.6f} / 100. Ortam sürümleri metadata.json içinde kayıtlıdır.")
    st.subheader('Önceki notebook doğrulaması (arşiv)')
    st.dataframe(load_csv('nested_cv_summary.csv'))
    st.warning('Test kümesi daha önce incelendi; tamamen bağımsız son test değildir. Arşiv çapraz doğrulama sonuçları bu yeniden eğitimde tekrar hesaplanmadı.')
    st.subheader('Canlı modelin dilimlerine göre ortalama skor')
    st.bar_chart(live.groupby('LiveSegment').LiveRiskScore.mean())
elif section=='Aksiyon simülasyonu':
    st.title('Thompson Sampling · Senaryo sonuçları')
    st.warning('Varsayımsal başarı olasılıkları; 30 günlük aktif kalma ödülü. Maliyetler dahil değil. Gerçek churn azalması veya kâr ölçümü değildir.')
    st.dataframe(load_csv('simulation_summary.csv'),use_container_width=True)
    st.line_chart(load_csv('simulation_runs.csv').set_index('Seed')[['StaticExpectedPercent','TSFinalPolicyExpectedPercent']])
    st.subheader('Varsayılan segment–aksiyon başarı olasılıkları')
    st.dataframe(load_csv('scenario_probabilities.csv'),use_container_width=True)
elif section=='Kayıtlı mesajlar':
    st.title('İncelenmiş sekiz örnek')
    st.caption('Kayıtlı örnekler; bu sayfa API çağrısı yapmaz.')
    for _,m in load_csv('reviewed_messages.csv').iterrows():
        with st.expander(f"{m.CustomerID} · {m.SelectedAction}"):
            st.write(m.ReviewedMessage);st.caption(m.ReviewStatus)
else:
    st.title('İzleme ve yöntem')
    with connect() as db:events=pd.read_sql_query('SELECT * FROM events ORDER BY rowid DESC LIMIT 50',db)
    st.dataframe(events,use_container_width=True)
    st.write('Kaydedilenler: istek zamanı, başarı/hata, yanıt süresi, bildirilen token sayısı. Anahtar ve müşteri bilgisi olay kayıtlarına yazılmaz. Taslaklar yerel SQLite önbelleğinde saklanır.')
    st.write('Her işlemde tek HTTP çağrısı; otomatik tekrar yok. Aynı prompt ve model için sonuç yeniden kullanılır. Varsayılan sınır: sunucu başına UTC gününde 10 deneme; parasal harcama garantisi değildir.')
    st.write('Yeni/ değiştirilmiş girdinin dilimi, dondurulmuş test referansındaki skor sırasından hesaplanır; aynı skorlar üst sıraya alınır. Mevcut müşterilerin eşit skorları müşteri ID ile sıralanır. Bu eşikler nüfus geneline ait risk sınırları değildir.')
    st.write('Model yerelde joblib ile yüklenir; features.py aynı özellikleri üretir. Yalnız güvenilir model dosyalarını yükleyin. İnternetten yeni etiketler gelmediği için gerçek zamanlı F1 veya drift alarmı uygulanmadı.')

# Retain — Canlı müşteri analizi ve Gemini mesaj taslağı

Samsung Innovation Campus · Grup 12

Retain, kaydedilmiş XGBoost modeliyle müşteri riskini hesaplayan bir Streamlit dashboard'udur. Aksiyon önerileri simülasyona dayanır. Gemini yalnızca kullanıcı düğmeye bastığında iletişim taslağı üretir; gerçek müşteriye gönderim yapılmaz.

## Gereksinimler ve Windows kurulumu

**Python 3.12 kullanın.** Paket sürümleri `requirements.txt` içinde sabittir. Komutları bu README'nin bulunduğu uygulama klasöründe çalıştırın (grup deposunda `dashboard/`).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .streamlit/secrets.toml)) {
    Copy-Item secrets.example.toml .streamlit/secrets.toml
}
notepad .streamlit/secrets.toml
```

Yerel editörde `GEMINI_API_KEY` ve `APP_PASSWORD` yer tutucularını değiştirin. Anahtarı veya parolayı GitHub'a, sohbete ya da loglara koymayın. `GEMINI_MODEL` hesabınızın erişebildiği model adı olmalıdır. `DAILY_REQUEST_LIMIT` günlük deneme sınırıdır; örnek dosyada 10'dur, mevcut yerel kurulumda kullanıcı isteğiyle 50 yapılmıştır. Bulut ayarını ayrıca seçin.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Yerel adres: http://127.0.0.1:8501 . Sonraki açılışlarda `BASLAT.bat` kullanılabilir. Sanal ortam kurulu Python 3.12'ye bağlıdır; başka bilgisayara kopyalamayın.

Linux/macOS'ta uygulama klasöründe:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
[ -f .streamlit/secrets.toml ] || cp secrets.example.toml .streamlit/secrets.toml
# secrets.toml dosyasını yerel editörde doldurun.
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

## Canlı demo

1. Belirlediğiniz uygulama parolasıyla giriş yapın.
2. Canlı müşteri analizi ekranında 54023 numaralı müşteriyi seçip **Risk analizi yap** düğmesine basın. Bu işlem yereldir.
3. **Gemini ile mesaj üret** düğmesine yalnızca bir canlı API isteği yapmak istediğinizde basın. Aynı prompt/model sonucu varsa önbellekten gelir.
4. Taslağı insan incelemesinden geçirin. Uygulama e-posta, SMS veya başka bir kanaldan müşteriye gönderim yapmaz.
5. Model performansı ve Aksiyon simülasyonu sayfalarını inceleyin; simülasyon sonuçlarını gerçek kampanya başarısı olarak sunmayın.

Kullanıcı, yerel dashboard üzerinden canlı Gemini üretiminin başarılı olduğunu doğruladı. Teslim hazırlığında yeni ücretli API testi yapılmadı. Bulut yayını henüz yapılmadı.

## Model ve çevrimdışı doğrulama

- `features.py`: 18 ham sütundan 21 özellik oluşturur; ön işleme modeli pipeline içindedir.
- `models/final_pipeline.joblib`: orijinal hazır model; Linux'ta uygulama bunu seçer.
- `models/final_pipeline.windows.joblib`: Windows uyumlu kayıt. `app.py` Windows'ta bu dosyayı seçer; orijinal korunmuştur.
- `convert_model_windows.py`: mevcut ağaçları yeniden eğitim yapmadan Windows kayıt biçimine dönüştürür. Normal kullanımda çalıştırılması gerekmez.
- `models/metadata.json`: eğitim ortamı ve sabit test metrikleri.
- `data/`: uygulama için müşteri, referans, simülasyon ve kayıtlı örnek CSV'leri.

Python 3.12 ve sabitlenmiş sklearn/XGBoost sürümleri korunmalıdır. Windows'ta 1.126 referans sınıf tahmini eşleşti; en büyük skor farkı 0,000003811 / 100 oldu. Linux seçim yolu ve bağımlılık dosyaları incelendi; hazırlık bilgisayarında WSL/Linux bulunmadığından Linux üzerinde gerçek model yükleme testi henüz yapılmadı. İlk bulut açılışında model yüklemesi ve yerel risk analizi doğrulanmalıdır. Joblib dosyaları yalnızca güvenilen kaynaklardan yüklenmelidir.

```powershell
.\.venv\Scripts\python.exe -m unittest test_service -v
.\.venv\Scripts\python.exe validate_model.py
```

Linux için `.venv/bin/python` kullanın. Bu kontroller API isteği yapmaz ve model eğitmez. `train_model.py` yalnızca arşiv/tekrarlanabilirlik için bulunur; sunucu başlangıcında çalışmaz, yeniden eğitim bu teslimin kapsamı değildir.

## Streamlit Community Cloud

Grup deposu düzeninde giriş dosyası **`dashboard/app.py`** olacaktır. `dashboard/requirements.txt` giriş dosyasıyla aynı dizindedir. Depo kökündeki `.streamlit/config.toml` bulut içindir; `dashboard/.streamlit/config.toml` uygulama klasöründen yerel başlatmayı destekler. İkisinde de `server.address=127.0.0.1` bulunmaz; yerel erişim kısıtı başlatma komutunda uygulanır. Uygulama veri/model yollarını `app.py` dosyasının konumuna göre çözer.

Yayımlama yetkisi verildiğinde:

1. Streamlit Community Cloud'da hedef GitHub deposunu ve yayımlanacak dalı seçin.
2. Main file path: `dashboard/app.py`.
3. Advanced settings → Python version: **3.12**.
4. Secrets alanına `secrets.example.toml` yapısını kullanarak gerçek değerleri yalnızca platform arayüzünde girin. Güçlü `APP_PASSWORD` tanımlayın. Gerçek `secrets.toml` dosyasını depoya eklemeyin.
5. Açılıştan sonra giriş ekranını, model yüklemesini ve risk analizini doğrulayın. Gemini düğmesi ücretli çağrı yapabilir; otomatik testte kullanmayın.

Bu klasör tek başına ayrı depo yapılırsa giriş yolu `app.py` olur. Grup deposu teslimi için `dashboard/app.py` kullanılır.

[Resmî yayımlama ve Python seçimi](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · [Secrets yönetimi](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) · [Dosya ve bağımlılık düzeni](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)

## Sınırlamalar ve maliyet

Aksiyon sonuçları varsayımsal başarı olasılıklarıyla simülasyondur; gerçek churn azalması, kâr veya kampanya etkisi kanıtı değildir. Risk skoru kalibre edilmiş olasılık değildir. Dilimler sabit test grubuna göredir; test kümesi geliştirme sırasında incelenmiştir. Yeni etiketli veri olmadığı için canlı F1 veya drift izleme yapılmaz.

Mesajlar en fazla iki kısa cümle istenen taslaklardır. API çıktı üst sınırı 2048 token, düşünme düzeyi low'dur. Otomatik tekrar ve yönlendirme takibi yoktur; SSL doğrulaması açıktır, güvenlik filtreleri kapatılmaz. Yalnızca engellenmemiş, `STOP` ile tamamlanan, boş olmayan mesajlar kaydedilir. Hatalarda yalnız izin verilen durum kodları ve sayısal token kullanımı gösterilir.

Günlük sınır UTC gününe göre uygulama genelindedir; başarısız denemeler de sayılır. Bu sınır parasal harcama garantisi değildir. SQLite `runtime/` altında olayları ve prompt/model önbelleğini tutar; bunlar GitHub'a taşınmaz. Community Cloud yeniden başlatma/yeniden dağıtımında yerel dosyalar kaybolabilir; kota ve önbellek kalıcı depoya taşınmadan üretim güvencesi sunmaz.

APP_PASSWORD ortak bir parola kapısıdır; kullanıcı bazlı yetkilendirme değildir. Kayıtlı örnekler ve müşterilere ait veri dosyaları depoya dahil edilir; gerçek kişilere ait yeni veri eklemeden önce paylaşım yetkisini kontrol edin.

## Teslim kapsamı

Kod, testler, iki hazır model, metadata, CSV dosyaları, requirements, örnek secrets, başlatıcı ve belgeler teslim edilir. `.streamlit/secrets.toml`, `.env` ve türevleri, `.venv/`, `__pycache__/`, `runtime/`, önbellek ve loglar dışlanır. Mevcut yerel kayıtlar silinmez. Push ve deploy kullanıcı talimatına kadar yapılmaz.

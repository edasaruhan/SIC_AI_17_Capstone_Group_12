# Retain — Yapay Zekâ Destekli Müşteri Kaybı Yönetim Sistemi

Samsung Innovation Campus — AI in Marketing
**Capstone Projesi · Grup 12**

## Canlı Dashboard

### [Dashboard’u aç: retain-grup12.streamlit.app](https://retain-grup12.streamlit.app)

Uygulama giriş parolası, öğretim görevlileriyle ayrıca paylaşılmaktadır. API anahtarı veya uygulama parolası bu depoda saklanmamaktadır.

## Proje Hakkında

**Retain**, e-ticaret müşterilerinin kayıp eğilimini analiz eden ve CRM ekiplerine uygulanabilir aksiyon önerileri sunan uçtan uca bir karar destek sistemidir.

Sistem:

* Hazır XGBoost modeliyle müşteri risk skorunu hesaplar.
* Müşterileri 10 risk segmentine ayırır.
* Risk segmentine göre CRM aksiyonu önerir.
* Thompson Sampling simülasyonuyla aksiyon politikasını değerlendirir.
* Müşterinin kategorisi ve şikâyet geçmişine göre Gemini ile Türkçe iletişim taslağı oluşturur.
* Model performansı, segmentler, aksiyonlar ve mesaj örneklerini dashboard üzerinde gösterir.

Üretilen mesajlar insan incelemesi bekleyen taslaklardır ve gerçek müşterilere otomatik olarak gönderilmez. Aksiyon sonuçları varsayımsal simülasyona dayanır; gerçek kampanya etkisi veya nedensel sonuç olarak değerlendirilmemelidir.

## Sistem Akışı

1. Dashboard üzerinden bir müşteri seçilir.
2. Müşterinin ham özellikleri hazır XGBoost modeline gönderilir.
3. Risk skoru ve churn tahmini hesaplanır.
4. Müşteri risk segmentine atanır.
5. Segmente uygun CRM aksiyonu önerilir.
6. Kullanıcının onayıyla Gemini API çağrılır ve Türkçe iletişim taslağı hazırlanır.
7. Mesaj, insan incelemesi bekleyen taslak olarak gösterilir.

## Model Sonuçları

Model, 4.504 eğitim ve 1.126 test müşterisi kullanılarak değerlendirilmiştir.

| Metrik    | Test sonucu |
| --------- | ----------: |
| Accuracy  |      0.9769 |
| Precision |      0.8942 |
| Recall    |      0.9789 |
| F1        |      0.9347 |
| ROC-AUC   |      0.9975 |

Test kümesi karmaşıklık matrisi:

|                   | Tahmin: Churn Yok | Tahmin: Churn Var |
| ----------------- | ----------------: | ----------------: |
| Gerçek: Churn Yok |               914 |                22 |
| Gerçek: Churn Var |                 4 |               186 |

Model tahminleri, proje notebook’undaki 1.126 referans tahminle karşılaştırılmış ve sınıf tahminlerinin tamamının eşleştiği doğrulanmıştır.

## Aksiyon Politikası

Risk segmentlerine göre kullanılan CRM aksiyonları:

| Risk segmenti | Önerilen aksiyon |
| ------------- | ---------------- |
| 1–3           | Aksiyon Yok      |
| 4             | Etkileşim Mesajı |
| 5–6           | Sadakat Teklifi  |
| 7–8           | İndirim Teklifi  |
| 9–10          | Win-Back Teklifi |

Thompson Sampling simülasyonunda statik politikanın beklenen başarı oranı yaklaşık **%70,01**, öğrenilen politikanın beklenen başarı oranı ise yaklaşık **%74,81** olarak hesaplanmıştır. Bu değerler tanımlanan senaryo olasılıklarına dayanır ve gerçek müşteri davranışı üzerinde ölçülmüş kampanya sonucu değildir.

## Kullanılan Teknolojiler

* Python 3.12
* Streamlit
* XGBoost
* scikit-learn
* pandas ve NumPy
* Gemini API
* SQLite
* GitHub
* Streamlit Community Cloud

## Proje Yapısı

```text
dashboard/
├── app.py                 # Streamlit dashboard
├── service.py             # Tahmin, segment, aksiyon ve Gemini işlemleri
├── features.py            # Özellik hazırlama fonksiyonları
├── models/                # Hazır model ve model bilgileri
├── data/                  # Dashboard veri dosyaları
├── requirements.txt       # Python bağımlılıkları
├── test_service.py        # Çevrimdışı servis testleri
├── validate_model.py      # Model tahmin doğrulaması
├── DEPLOYMENT.md          # Dağıtım ve güvenlik notları
└── README.md              # Ayrıntılı dashboard belgesi
```

## Yerel Kurulum

**Python 3.12** gereklidir. Windows PowerShell’de depo kökünden:

```powershell
cd dashboard
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Copy-Item secrets.example.toml .streamlit/secrets.toml
notepad .streamlit/secrets.toml

.\.venv\Scripts\python.exe -m streamlit run app.py
```

Yerel ayar dosyası aşağıdaki yapıda olmalıdır:

```toml
GEMINI_API_KEY = "API_ANAHTARINIZ"
GEMINI_MODEL = "gemini-3.6-flash"
DAILY_REQUEST_LIMIT = 50
APP_PASSWORD = "UYGULAMA_PAROLANIZ"
```

Gerçek `secrets.toml` dosyası GitHub’a yüklenmemelidir. İlk kurulumdan sonra Windows’ta `dashboard/BASLAT.bat` dosyasıyla uygulama başlatılabilir.

Yerel adres:

```text
http://127.0.0.1:8501
```

## Kontroller

Dashboard klasöründe aşağıdaki komutlar çalıştırılabilir:

```powershell
.\.venv\Scripts\python.exe -m unittest test_service -v
.\.venv\Scripts\python.exe validate_model.py
```

Bu kontroller ücretli API çağrısı yapmaz ve modeli yeniden eğitmez.

## Güvenlik ve Sınırlamalar

* Gemini API anahtarı ve uygulama parolası Streamlit Secrets ile saklanır.
* Gizli bilgiler GitHub deposuna dahil edilmez.
* Gemini yalnızca kullanıcı mesaj üretme düğmesine bastığında çağrılır.
* Günlük uygulama içi istek sınırı uygulanır.
* Mesajlar gerçek müşterilere otomatik gönderilmez.
* Risk segmentleri, test müşterileri arasındaki göreli sıralamaya dayanır.
* Risk skoru kalibre edilmiş bir olasılık olarak yorumlanmamalıdır.
* Streamlit Community Cloud üzerindeki geçici işlem kayıtları yeniden başlatmalarda sıfırlanabilir.

## Belgeler

* [Ayrıntılı Dashboard README](dashboard/README.md)
* [Dağıtım ve Güvenlik Notları](dashboard/DEPLOYMENT.md)
* [Streamlit Community Cloud Dokümantasyonu](https://docs.streamlit.io/deploy/streamlit-community-cloud)

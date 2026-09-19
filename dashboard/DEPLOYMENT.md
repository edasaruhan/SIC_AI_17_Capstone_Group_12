# Teslim ve yayımlama durumu — Grup 12

Retain, hazır XGBoost modeliyle risk analizi ve düğmeyle Gemini mesaj taslağı üretimi sunar. Kullanıcı yerel canlı üretimin başarılı olduğunu doğrulamıştır. Teslim hazırlığında ücretli test, yeniden eğitim ve bulut yayını yapılmamıştır.

## Grup deposu düzeni

- Giriş: `dashboard/app.py`
- Python: **3.12** (Community Cloud Advanced settings üzerinden seçilir)
- Bağımlılıklar: `dashboard/requirements.txt`
- Bulut yapılandırması: depo kökünde `.streamlit/config.toml`; loopback adresi sabitlenmez.
- Veri/model dosyaları: `dashboard/data/` ve `dashboard/models/`; yollar çalışma dizininden bağımsızdır.
- Secrets: Community Cloud Secrets arayüzüne kullanıcı tarafından girilir. Gerçek dosya depoya kopyalanmaz.

## Model uyumluluğu ve kontroller

Windows uyumlu model ve orijinal model birlikte korunur. Windows'ta uyumlu kopya, Linux'ta orijinal seçilir. `validate_model.py`, 1.126 müşterinin tahminlerini referansla karşılaştırır ve gerekli CSV'leri okur. Windows kontrolü geçti; hazırlık bilgisayarında Linux/WSL olmadığı için Linux çalışma testi henüz yapılmadı. İlk bulut başlangıcında model yüklemesi ve risk analizi kontrol edilmelidir.

`test_service.py` ağ çağrılarını taklit ederek hata ayrımını, güvenli tanı bilgilerini, tamamlanmamış yanıtların kaydedilmemesini, önbelleği ve kotayı kontrol eder. Testler gerçek API anahtarı kullanmaz.

## Operasyonel sınırlar

Aksiyonlar simülasyon, mesajlar insan incelemesi bekleyen taslaklardır; müşteriye gönderim yoktur. Uygulama parolası kişi bazlı kimlik doğrulama değildir. Günlük UTC deneme limiti ve SQLite önbelleği yerel disktedir; bulut dosya kaybında süreklilik garantisi yoktur. API otomatik tekrar yapmaz; SSL doğrulaması ve güvenlik filtreleri korunur. Ayrıntılı kurulum, demo ve bulut adımları README'dedir.

# SIC AI 17 · Capstone · Grup 12

Bu depo grup ödevlerini ve **Retain** canlı müşteri analizi dashboard'unu içerir. Önceki ödev belgeleri depo kökünde korunmuştur.

Retain, hazır XGBoost modeliyle müşteri risk analizi yapar ve kullanıcı düğmeye bastığında Gemini ile Türkçe iletişim taslağı üretir. Aksiyon sonuçları simülasyondur; mesajlar insan incelemesi bekleyen taslaklardır ve gerçek müşteriye gönderilmez.

## Dashboard'u yerelde çalıştırma

**Python 3.12** gereklidir. Windows PowerShell'de depo kökünden:

```powershell
cd dashboard
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .streamlit/secrets.toml)) {
    Copy-Item secrets.example.toml .streamlit/secrets.toml
}
notepad .streamlit/secrets.toml
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Anahtar ve parolayı yalnızca yerel editörde doldurun. Adres: http://127.0.0.1:8501 . Kurulumdan sonra `dashboard/BASLAT.bat` kullanılabilir. Hazır model kullanılır; yeniden eğitim gerekmez.

Linux/macOS kurulumu, demo adımları, çevrimdışı kontroller ve sınırlamalar için [dashboard README](dashboard/README.md) belgesine bakın.

## Streamlit Community Cloud hazırlığı

- Depo: `edasaruhan/SIC_AI_17_Capstone_Group_12`
- Hazırlık dalı: `capstone-dashboard` (bu hazırlık sırasında push yapılmadı)
- Main file path: **`dashboard/app.py`**
- Advanced settings → Python version: **3.12**
- Secrets: `dashboard/secrets.example.toml` yapısını kullanarak gerçek değerleri yalnızca Community Cloud Secrets arayüzünde girin. Güçlü `APP_PASSWORD` tanımlayın.
- `dashboard/requirements.txt` bağımlılıkları, kökteki `.streamlit/config.toml` bulut ayarlarını içerir. Bulut sunucusu 127.0.0.1'e sabitlenmez.

Veri ve modeller dosya konumuna göre okunur; giriş dosyası depo kökünden çalıştırılabilir. Windows uyumlu hazır model korunmuştur; Linux orijinal hazır modeli kullanır. Windows tahmin doğrulaması yapılmıştır; Linux çalışma testi ve bulut yayını henüz yapılmamıştır.

Mevcut uygulamada canlı Gemini üretimi kullanıcı tarafından doğrulanmıştır. Bu teslim hazırlığında ücretli API testi yapılmadı. Yayımlama yetkisi verilmeden push veya deploy yapılmaz.

## Kontroller

Uygulama klasöründe, kurulu sanal ortam Python'u ile:

```powershell
.\.venv\Scripts\python.exe -m unittest test_service -v
.\.venv\Scripts\python.exe validate_model.py
```

Bu kontroller dış API çağrısı veya eğitim yapmaz. Gerçek secrets, sanal ortam, runtime önbelleği, işlem kayıtları ve loglar depoya dahil edilmez.

[Dağıtım notları](dashboard/DEPLOYMENT.md) · [Resmî Community Cloud adımları](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

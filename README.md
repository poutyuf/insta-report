# insta-report

**Gelişmiş Instagram Raporlama Aracı**

Bu Python script'i, Instagram kullanıcılarını çeşitli sebeplerle raporlamak için tasarlanmıştır. Hem mobil API üzerinden (session ID ile) hem de web yardım formu üzerinden raporlama yeteneklerine sahiptir. Ayrıca proxy desteği de sunmaktadır.

## Özellikler

- **Çoklu Giriş Yöntemleri:**
  - Mobil API ile giriş (daha stabil)
  - Web AJAX ile giriş (deneysel)
- **Raporlama Seçenekleri:**
  - API üzerinden (session ID gerektirir, çeşitli rapor sebepleri)
  - Web Yardım Formu üzerinden (daha az stabil, dinamik token almayı dener)
- **Proxy Desteği:**
  - Dosyadan proxy listesi yükleme
  - Manuel proxy ekleme
  - Webshare.io API'sinden proxy listesi indirme (API URL'si script içinde tanımlıdır)
  - Rastgele proxy kullanımı ve session bazında proxy rotasyonu
- **Otomatik Kütüphane Kontrolü ve Kurulumu:**
  - Gerekli `requests` ve `rich` kütüphanelerini otomatik olarak kontrol eder ve eksikse kurulum teklif eder.
  - İsteğe bağlı `ms4` kütüphanesini (kullanıcı ID'si almak için) kontrol eder.
- **Kullanıcı Dostu Arayüz:**
  - `rich` kütüphanesi ile renklendirilmiş ve düzenlenmiş konsol çıktıları.
  - Menü tabanlı navigasyon.

## Kurulum ve Kullanım

1.  **Gereksinimler:**
    - Python 3.x
    - `pip` (Python paket yükleyicisi)

2.  **Script'i İndirin:**
    Bu repoyu klonlayın veya `insta-report.py` dosyasını indirin.

3.  **Çalıştırma:**
    ```bash
    python insta-report.py
    ```
    Script ilk çalıştığında, eksik olan temel kütüphaneleri (`requests`, `rich`) kurmayı teklif edecektir.

4.  **Adımlar:**
    - Ana menüden bir giriş yöntemi seçerek Instagram hesabınıza giriş yapın.
    - Hedef kullanıcı adını ve (API raporlaması için) ID'sini belirleyin. `ms4` kütüphanesi yüklüyse ID otomatik alınmaya çalışılır.
    - Proxy kullanmak istiyorsanız, menüden proxy yükleme/ekleme seçeneklerini kullanın.
    - Uygun raporlama yöntemini seçerek hedef kullanıcıyı raporlayın.

## Bağımlılıklar
- `requests`: HTTP istekleri göndermek için.
- `rich`: Gelişmiş konsol arayüzü için.
- `ms4` (isteğe bağlı): Instagram kullanıcı ID'lerini otomatik olarak almak için. `pip install ms4` ile kurulabilir.

## Uyarılar
- Bu araç eğitim ve test amaçlıdır. Kötüye kullanımı kullanıcının sorumluluğundadır.
- Instagram'ın API'leri ve web formları zamanla değişebilir, bu da script'in bazı özelliklerinin çalışmamasına neden olabilir.
- Otomatik işlemler ve raporlama, Instagram'ın kullanım koşullarına aykırı olabilir. Dikkatli kullanın.
- Web AJAX ile giriş ve Yardım Formu ile raporlama yöntemleri daha az stabildir ve her zaman çalışmayabilir.
- Proxy API anahtarınız (Webshare için) script içinde gömülüdür. Güvenlik için bunu bir konfigürasyon dosyasına veya ortam değişkenine taşımayı düşünebilirsiniz.

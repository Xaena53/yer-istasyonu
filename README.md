# Evde uydu yer istasyonu

Meteor-M hava uydularının Eskişehir üstünden geçişlerini hesaplar, iyi geçişlerde RTL-SDR alıcıyla kaydı
kendisi başlatır ve görüntüyü SatDump'a çözdürür.

```
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python istasyon.py gecisler --gun 3     # önümüzdeki geçişler
.venv\Scripts\python istasyon.py gorsel              # cikti/: gökyüzü, harita, 7 günlük takvim
.venv\Scripts\python istasyon.py kontrol             # ayar, TLE yaşı, SatDump, disk alanı, sıradaki geçiş
.venv\Scripts\python istasyon.py calis --kuru        # sıradaki kayıt komutunu göster
.venv\Scripts\python istasyon.py calis               # bekle, geçişte kaydet (alıcı takılı olmalı)
```

### Enkaz bulutları
`enkaz.py`, dört büyük enkaz bulutunun (Fengyun-1C, Kosmos 2251, Iridium 33, Kosmos 1408) parçalarının
istasyon gökyüzünde ufkun 10° üstüne kaç kez çıktığını sayar; CelesTrak katalogundan da olaydan kaç parça
kaydedildiğini ve kaçının hâlâ yörüngede olduğunu yazar. Geçiş hesabı yalnız güncel yörünge verisi (TLE)
yayımlanan parçalarla yapılabildiği için geçiş sayısı bir alt sınırdır. "Uzay enkazı" yazısındaki sayılar,
25 Kasım 2026 tarihli TLE ve katalog kayıtlarıyla şöyle yeniden üretilir:

```
.venv\Scripts\python enkaz.py --bas "2026-11-25 18:00" --veri-klasoru belgeler/enkaz_tle_2026-11-25 --gokyuzu cikti/enkaz_gokyuzu.png --yakin --yakin-km 50 --kesisim-km 420 680
```

`--yakin`, `ayar.json`'daki ilk uyduya (Meteor-M N2-4) eşikten yakın geçen Fengyun-1C parçalarını sayar.
`--kesisim-km 420 680`, her olaydan yörüngesi (yerberi–yeröte arası) Uluslararası Uzay İstasyonu'nun (420 km) ve
İMECE'nin (680 km) irtifasını kesen ve tamamen altına inmiş parçaları sayar.
Herkese açık TLE'lerin hatası birkaç km olabilir: sonuç ölçek verir, çarpışma uyarısı değildir.

## Nasıl çalışır
- `yer_istasyonu/yorunge.py`: Celestrak'tan TLE (12 saatte bir yenilenir, ağ yoksa son kopya), skyfield ile
  geçiş hesabı: ufka çıkış, en yüksek nokta, iniş, yön, iz.
- `yer_istasyonu/kayit.py`: geçişten 1 dk önce `satdump live <pipeline> <klasör> --source rtlsdr ...` çalıştırır,
  süre geçiş + 2 dk. Çıktı `kayitlar/<tarih>_<uydu>/`.
- `yer_istasyonu/gorsel.py`: gökyüzü grafiği, yer izi haritası (Natural Earth), güneşli saatleri gösteren takvim.
- `ayar.json`: konum, en düşük yükseklik (25°), uydular, frekans, alıcı ayarları.

## Dayanıklılık
- TLE satırları sağlama toplamıyla denetlenir; bozuk ya da yarım inen dosya kullanılmaz, eski kopya korunur.
  3 günden eski TLE için uyarı verilir.
- `calis` ağ/TLE hatasında kapanmaz, 10 dk sonra yeniden dener. Geçiş 3 saatten uzaksa saatte bir TLE tazeleyip
  yeniden hesaplar. Bilgisayar uykudan dönünce kaçan geçişi atlar, geç başlarsa kayıt süresini kısaltır.
- SatDump bulunamazsa geçiş atlanır ve söylenir. Kayıt bitince görüntüleri işlemesi için 10 dk pay bırakılır,
  ancak bundan sonra hâlâ kapanmamışsa durdurulur.
  Hata koduyla biterse `satdump.log`'un sonu ekrana yazılır.
- Windows'ta `calis` açıkken bilgisayarın uykuya geçmesi engellenir (ekran yine kapanabilir).
- CelesTrak "veri güncellenmedi" derse eski kopya korunur ve süre dolana dek tekrar sorulmaz.
- Bir uydunun TLE'si alınamazsa diğer uydular hesaplanmaya devam eder.
- `ayar.json` açılışta denetlenir; hatalı alan adıyla söylenir.

## Alıcı gelince
1. RTL-SDR Blog sürücüsü (Zadig) + SatDump kur, `satdump` PATH'te olsun.
2. `satdump live --help` ile seçenek adlarını doğrula; farklıysa `ayar.json` → `alici.ek` ya da `kayit.py`.
3. Anten: kitteki dipol, V-dipol düzeni (kollar ~53 cm, 120°, yatay).

## Test
`python testler/test_istasyon.py` ya da `pytest testler`: 16 test, ağ gerekmez (sabit TLE ile geçiş hesabı, TLE
sağlama/bozuk önbellek, kayıt akışı: SatDump yok / geçiş kaçtı / hata kodu, ayar denetimi, görseller).

Yörünge verisi: CelesTrak. Harita: Natural Earth (kamu malı).

## Belgeler
- `belgeler/alisveris-listesi.md`: alıcı ve anten seçenekleri (Kasım 2026)
- `belgeler/cekim-rehberi.md`: anteni kurma, SatDump ayarları, çekim günü

## Lisans
MIT.

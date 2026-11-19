# Evde uydu yer istasyonu

Meteor-M hava uydularının Eskişehir üstünden geçişlerini hesaplar, iyi geçişlerde RTL-SDR alıcıyla kaydı
kendisi başlatır ve görüntüyü SatDump'a çözdürür.

```
python -m venv .venv && .venv\Scripts\pip install skyfield matplotlib numpy
.venv\Scripts\python istasyon.py gecisler --gun 3     # önümüzdeki geçişler
.venv\Scripts\python istasyon.py gorsel              # cikti/: gökyüzü, harita, 7 günlük takvim
.venv\Scripts\python istasyon.py calis --kuru        # sıradaki kayıt komutunu göster
.venv\Scripts\python istasyon.py calis               # bekle, geçişte kaydet (alıcı takılı olmalı)
```

## Nasıl çalışır
- `yer_istasyonu/yorunge.py`: Celestrak'tan TLE (12 saatte bir yenilenir, ağ yoksa son kopya), skyfield ile
  geçiş hesabı: ufka çıkış, en yüksek nokta, iniş, yön, iz.
- `yer_istasyonu/kayit.py`: geçişten 1 dk önce `satdump live <pipeline> <klasör> --source rtlsdr ...` çalıştırır,
  süre geçiş + 2 dk. Çıktı `kayitlar/<tarih>_<uydu>/`.
- `yer_istasyonu/gorsel.py`: gökyüzü grafiği, yer izi haritası (Natural Earth), güneşli saatleri gösteren takvim.
- `ayar.json`: konum, en düşük yükseklik (25°), uydular, frekans, alıcı ayarları.

## Alıcı gelince
1. RTL-SDR Blog sürücüsü (Zadig) + SatDump kur, `satdump` PATH'te olsun.
2. `satdump live --help` ile seçenek adlarını doğrula; farklıysa `ayar.json` → `alici.ek` ya da `kayit.py`.
3. Anten: kitteki dipol, V-dipol düzeni (kollar ~53 cm, 120°, yatay).

## Test
`python testler/test_istasyon.py` (sabit TLE ile geçiş hesabı, kayıt komutu, güneş yüksekliği).

Yörünge verisi: CelesTrak. Harita: Natural Earth (kamu malı).

## Belgeler
- `belgeler/alisveris-listesi.md`: alıcı ve anten seçenekleri (Kasım 2026)
- `belgeler/cekim-rehberi.md`: anteni kurma, SatDump ayarları, çekim günü

## Lisans
MIT.

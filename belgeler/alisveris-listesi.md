# Evde uydu yer istasyonu: alışveriş listesi (19 Kas 2026 araştırması)

## Alıcı: RTL-SDR Blog V4 ya da V4L (Lite)
- V4 üretimi bitiyor (R828D çip stoğu tükendi); yerine aynı firmanın V4L (Lite) modeli geldi. İkisi de iş görür.
- **Öneri: antenli kit al.** Kitteki teleskopik dipol anten 137 MHz için V-dipol olarak kurulabiliyor
  (her kol ~53 cm, kollar arası 120°, yatay). Ayrıca anten yapmaya gerek kalmaz.

| Seçenek | Fiyat | Not |
|---|---|---|
| Robotzade (Türkiye), V4 + anten seti | 6.120 TL KDV dahil (bir sayfada 4.700 TL + KDV "stokta yok") | Stok belirsiz, sipariş öncesi ara/sor |
| RTL-SDR Blog resmi AliExpress mağazası, V4L | ~31 $ (yalnız alıcı), antenli kit ~40 $ civarı | Kargo + gümrük/vergi ödeme ekranında görünür; 2–4 hafta |

Taklit uyarısı: yalnız "RTL-SDR Blog" markalı, resmi mağazadan al. Ucuz "RTL2832U" klonları 137 MHz'te zayıf.

## Diğer
| Parça | Fiyat | Not |
|---|---|---|
| USB uzatma kablosu (2–3 m) | ~100–200 TL | Alıcıyı antene yakın, bilgisayardan uzak tutar (gürültü az) |
| Basit anten ayağı (kamera tripodu / süpürge sapı) | evde | Anteni açık gökyüzüne, balkon/çatı |

**Tahmini toplam:** ~2.000–2.500 TL (AliExpress, vergi dahil tahmin) ya da ~6.300 TL (Türkiye'den).

## Yazılım (ücretsiz)
- SatDump: kayıt + "METEOR-M N2-x LRPT 80k" çözümü (SDR++ çözücüsü 80k modda çalışmıyor)
- Geçiş tahmini: SatDump'ın kendi takvimi ya da gpredict / N2YO

## Hedef uydu durumu
- NOAA-15/18/19 2025'te kapatıldı.
- Meteor-M N2-4: LRPT 137,9 MHz, 80k. Frekans/mod habersiz değişebiliyor; çekimden önce SatNOGS'a bak.

## Kaynaklar
- https://www.rtl-sdr.com/tag/rtl-sdr-blog-v4/
- https://rtl-sdr.com/rtl-sdr-blog-v4l-lite-now-available-for-purchase
- https://db.satnogs.org/satellite/59051

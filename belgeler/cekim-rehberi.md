# Meteor-M uydu görüntüsü çekim rehberi (alıcı gelince)

## 1. Anten (kitteki dipol, V-dipol düzeni)
- Teleskopik kolların her birini **~53 cm** aç (137 MHz için çeyrek dalga boyu).
- Kolları aralarında **120°** olacak şekilde aç, anteni **yatay** tut (V yere paralel).
- V'nin açık ucu **kuzeye ya da güneye** baksın (Meteor kutuptan kutba geçer).
- Balkon ya da çatı: gökyüzünü en geniş gören yer. Metal korkuluktan 30–50 cm uzak.

## 2. Yazılım
- SatDump'ı indir (Windows sürümü), RTL-SDR Blog sürücüsünü Zadig ile kur (V4/V4L için RTL-SDR Blog sürücüsü şart).
- SatDump → Recorder:
  - Kaynak: RTL-SDR, örnekleme 1.024 Msps, kazanç ~30–40 dB (gürültü tabanına göre)
  - Frekans: **137,900 MHz** (çekimden önce SatNOGS'ta güncel frekansı kontrol et)
  - Pipeline: **METEOR-M N2-x LRPT 80k**
- Geçiş takvimi: SatDump'ın "Tracking" sekmesi, konum Eskişehir. Yüksekliği **40°'nin üstünde** olan geçişleri seç.

## 3. Çekim günü
1. Geçişten 5 dk önce kaydı başlat; uydu ufkun üstüne çıkınca sinyal belirir.
2. Takımyıldız (constellation) ekranında 4 nokta kümesi görünüyorsa çözüm çalışıyor.
3. Geçiş bitince SatDump görüntüleri üretir (MSU-MR kanalları, renkli birleşim).
4. İlk denemelerde görüntü yarım çıkabilir; anten yönü ve kazançla oyna.

## 4. Paylaşım için
- Ham görüntü + Türkiye'yi gösteren kırpma, anten fotoğrafı, kurulumun ekran görüntüsü.
- Tarih/saat ve uydu adını yaz (ör. "Meteor-M N2-4, 3 Ara 2026, 09:41 TR").

## Uyarı
Meteor-M N2-4 test aşamasında görünüyor; LRPT yayını habersiz kapanabilir ya da frekans değiştirebilir.
Çekim günü SatNOGS'ta son gözlemlere bak: https://db.satnogs.org/satellite/59051

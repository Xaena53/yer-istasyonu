"""Büyük enkaz bulutlarının istasyon gökyüzündeki geçişleri.

    .venv\\Scripts\\python enkaz.py                                   # şimdiden itibaren 24 saat, güncel veri
    .venv\\Scripts\\python enkaz.py --bas "2026-11-25 18:00" \\
        --veri-klasoru belgeler/enkaz_tle_2026-11-25 --gokyuzu cikti/enkaz_gokyuzu.png

Her olay için iki sayı verilir:
  - katalog (CelesTrak SATCAT): olaydan kaydedilmiş parça sayısı ve bunlardan henüz atmosfere girmemiş olanlar,
  - yörünge verisi yayımlanan parçalar (CelesTrak GP): geçiş hesabı yalnız bunlarla yapılabilir, bu yüzden
    geçiş sayısı bir alt sınırdır.
Bir "geçiş": parçanın ufkun --en-az derece üstüne çıkması (yükselme olayı). Aralığın başında zaten
gökyüzünde olan parçalar sayılmaz. Konum ayar.json'dan gelir. Saatler UTC verilir, ekrana TSİ de yazılır.
"""
import argparse
import datetime as dt
import json
import os
import statistics
import sys
import time
import urllib.request

import numpy as np
from skyfield.api import EarthSatellite, wgs84

import istasyon as ist
from yer_istasyonu import yorunge

GP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={grup}&FORMAT=TLE"
SATCAT_URL = "https://celestrak.org/satcat/records.php?INTDES={intdes}&FORMAT=JSON"
GRUPLAR = [  # (CelesTrak GP grubu, uluslararası tanıtıcı, olay)
    ("fengyun-1c-debris", "1999-025", "Fengyun-1C, uydusavar testi, 11 Ocak 2007"),
    ("cosmos-2251-debris", "1993-036", "Kosmos 2251, Iridium 33 ile çarpışma, 10 Şubat 2009"),
    ("iridium-33-debris", "1997-051", "Iridium 33, Kosmos 2251 ile çarpışma, 10 Şubat 2009"),
    ("cosmos-1408-debris", "1982-092", "Kosmos 1408, uydusavar testi, 15 Kasım 2021"),
]
TSI = dt.timedelta(hours=3)


def _uyar(mesaj):
    print(f"uyarı: {mesaj}", file=sys.stderr)


def tle_listesi_coz(metin):
    """Ad + iki satırlık kayıtlar; sağlama toplamı tutmayan kayıt atlanır. (geçerliler, atlanan satır sayısı)"""
    satirlar = [s.rstrip() for s in metin.splitlines() if s.strip()]
    gecerli, atlanan, i = [], 0, 0
    while i + 2 < len(satirlar):
        ad, s1, s2 = satirlar[i:i + 3]
        if yorunge.tle_satiri_gecerli(s1, 1) and yorunge.tle_satiri_gecerli(s2, 2):
            gecerli.append((ad.strip(), s1, s2))
            i += 3
        else:
            atlanan += 1
            i += 1           # hizayı kaybetmemek için satır satır ilerle
    return gecerli, atlanan + max(0, len(satirlar) - i)


def satcat_coz(metin):
    """SATCAT JSON → [kayıt]; liste değilse ya da bozuksa None."""
    try:
        kayitlar = json.loads(metin)
    except ValueError:
        return None
    return kayitlar if isinstance(kayitlar, list) and all(isinstance(k, dict) for k in kayitlar) else None


def _onbellekli_indir(url, yol, gecerli_mi, yenile_saat=12):
    """Tazeyse yerel kopya; değilse indir. İndirme/yanıt bozuksa eski kopyayla devam (uyarıyla)."""
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    if os.path.exists(yol) and time.time() - os.path.getmtime(yol) < yenile_saat * 3600:
        return
    try:
        istek = urllib.request.Request(url, headers={"User-Agent": "yer-istasyonu/1.0"})
        metin = urllib.request.urlopen(istek, timeout=60).read().decode("utf-8", "replace")
        time.sleep(2)        # CelesTrak'a nezaket
    except OSError as hata:
        if not os.path.exists(yol):
            raise RuntimeError(f"{url} indirilemedi ({hata})") from hata
        _uyar(f"indirilemedi ({hata}); eski kopya kullanılıyor")
        return
    if gecerli_mi(metin):
        with open(yol + ".yeni", "w", encoding="utf-8") as f:
            f.write(metin)
        os.replace(yol + ".yeni", yol)       # yarıda kesilirse eski kopya bozulmaz
    elif os.path.exists(yol):
        _uyar(f"CelesTrak geçerli veri vermedi ({metin.strip()[:60]!r}); eski kopya kullanılıyor")
        os.utime(yol)                        # "veri güncellenmedi" yanıtı: süre dolana dek tekrar sorma
    else:
        raise RuntimeError(f"CelesTrak geçerli veri vermedi: {metin.strip()[:80]!r}")


def grup_tle_al(grup, klasor=None):
    """klasor verilirse oradan okur (ağ yok); yoksa veri/tle altında 12 saatlik önbellekle indirir."""
    if klasor:
        yol = os.path.join(klasor, f"{grup}.tle")
    else:
        yol = os.path.join(yorunge.TLE_KLASORU, f"grup-{grup}.tle")
        _onbellekli_indir(GP_URL.format(grup=grup), yol, lambda m: bool(tle_listesi_coz(m)[0]))
    with open(yol, encoding="utf-8", errors="replace") as f:
        return tle_listesi_coz(f.read())


def katalog_al(grup, intdes, klasor=None):
    """(katalogdaki enkaz parçası, henüz atmosfere girmemiş olanlar); veri yoksa None."""
    if klasor:
        yol = os.path.join(klasor, f"{grup}.satcat.json")
        if not os.path.exists(yol):
            return None
    else:
        yol = os.path.join(yorunge.TLE_KLASORU, f"satcat-{intdes}.json")
        try:
            _onbellekli_indir(SATCAT_URL.format(intdes=intdes), yol, lambda m: bool(satcat_coz(m)))
        except RuntimeError as hata:
            _uyar(f"katalog alınamadı: {hata}")
            return None
    with open(yol, encoding="utf-8", errors="replace") as f:
        kayitlar = satcat_coz(f.read()) or []
    enkaz = [k for k in kayitlar if k.get("OBJECT_TYPE") == "DEB"]
    return len(enkaz), sum(1 for k in enkaz if not k.get("DECAY_DATE"))


def grup_gecisleri(parcalar, yer, bas, son, en_az):
    """[(yükseliş zamanı, iz)] ve parçaların bas anındaki irtifaları (km).

    iz = (azimut rad dizisi, 90-yükseklik dizisi); parça aralık sonunda hâlâ gökyüzündeyse None.
    """
    ts = yorunge.zaman_olcegi
    sonuc, irtifalar = [], []
    for ad, s1, s2 in parcalar:
        uydu = EarthSatellite(s1, s2, ad, ts)
        konum = uydu.at(bas)
        if np.isnan(konum.position.km).any():   # SGP4 hata verdi (parça çoktan düşmüş olabilir)
            continue
        irtifalar.append(wgs84.height_of(konum).km)
        t, olay = uydu.find_events(yer, bas, son, altitude_degrees=en_az)
        acik = None
        for ti, oi in zip(t, olay):
            if oi == 0:
                acik = [ti, None]
                sonuc.append(acik)
            elif oi == 2 and acik is not None:
                n = max(8, int((ti.tt - acik[0].tt) * 86400 / 4))
                yuk, az, _ = (uydu - yer).at(ts.tt_jd(np.linspace(acik[0].tt, ti.tt, n))).altaz()
                acik[1] = (az.radians, 90 - yuk.degrees)
                acik = None
    return sonuc, irtifalar


def yakin_gecenler(hedef, parcalar, bas, son, esik_km=10.0, kaba_sn=20, kaba_esik_km=500.0):
    """Parçaların hedef uyduya en yakın yaklaşmaları: [(mesafe km, zaman, parça adı)], esik_km altı.

    Önce kaba_sn adımla tarar; kaba_esik_km'den yakına gelen her an için ±kaba_sn penceresinde
    0,1 sn adımla en yakın noktayı bulur. TLE'nin kendi hatası birkaç km olabilir: sonuç ölçek verir,
    çarpışma uyarısı değildir.
    """
    ts = yorunge.zaman_olcegi
    n = int((son.tt - bas.tt) * 86400 / kaba_sn) + 1
    kaba = ts.tt_jd(np.linspace(bas.tt, son.tt, n))
    h_kaba = hedef.at(kaba).position.km
    sonuc = []
    for ad, s1, s2 in parcalar:
        uydu = EarthSatellite(s1, s2, ad, ts)
        d = np.linalg.norm(uydu.at(kaba).position.km - h_kaba, axis=0)
        adaylar = np.where(np.nan_to_num(d, nan=np.inf) < kaba_esik_km)[0]
        en_iyi = None
        # ardışık adaylar tek yaklaşmadır: her ardışık grubun kaba en yakın örneği çevresinde incele
        gruplar = np.split(adaylar, np.where(np.diff(adaylar) > 1)[0] + 1) if len(adaylar) else []
        for grup in gruplar:
            i = int(grup[np.argmin(d[grup])])
            ince = ts.tt_jd(np.linspace(kaba[i].tt - kaba_sn / 86400, kaba[i].tt + kaba_sn / 86400,
                                        int(2 * kaba_sn / 0.1) + 1))
            di = np.linalg.norm(uydu.at(ince).position.km - hedef.at(ince).position.km, axis=0)
            j = int(np.nanargmin(di))
            if di[j] < esik_km and (en_iyi is None or di[j] < en_iyi[0]):
                en_iyi = (float(di[j]), ince[j], ad)
        if en_iyi:
            sonuc.append(en_iyi)
    return sorted(sonuc, key=lambda x: x[0])


def gokyuzu_ciz(izler, en_az, yol):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(6, 6), dpi=400)
    fig.patch.set_alpha(0)
    ax = fig.add_subplot(projection="polar")
    ax.set_facecolor((0, 0, 0, 0))
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)              # yukarı kuzey, sağ doğu (haritadaki gibi yukarıdan bakış)
    ax.set_rlim(0, 90 - en_az)
    for az, r in izler:
        ax.plot(az, r, color="#ffa264", lw=0.7, alpha=0.75, solid_capstyle="round")
    halka = np.linspace(0, 2 * np.pi, 400)
    for rr in range(20, 90 - en_az + 1, 20):
        ax.plot(halka, [rr] * 400, color="#ffffff", lw=0.5, alpha=0.14)
    ax.plot(halka, [90 - en_az] * 400, color="#ffffff", lw=0.9, alpha=0.35)   # ufkun en_az° üstü
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["polar"].set_visible(False)
    ax.grid(False)
    plt.subplots_adjust(0, 0, 1, 1)
    os.makedirs(os.path.dirname(os.path.abspath(yol)), exist_ok=True)
    fig.savefig(yol, transparent=True)
    plt.close(fig)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Enkaz bulutlarının istasyon gökyüzündeki geçişleri")
    p.add_argument("--bas", help='UTC başlangıç, "YYYY-AA-GG SS:DD" (varsayılan: şimdi)')
    p.add_argument("--saat", type=float, default=24, help="hesap süresi (saat, en çok 72)")
    p.add_argument("--en-az", type=int, default=10, help="ufkun kaç derece üstü sayılsın")
    p.add_argument("--veri-klasoru", "--tle-klasoru", dest="veri_klasoru",
                   help="TLE ve katalogu bu klasörden oku (<grup>.tle, <grup>.satcat.json); verilmezse CelesTrak")
    p.add_argument("--gokyuzu", help="Fengyun-1C geçişlerinin gökyüzü çizimi (PNG yolu)")
    p.add_argument("--gokyuzu-saat", type=float, default=1, help="çizime girecek ilk kaç saat")
    p.add_argument("--yakin", action="store_true",
                   help="ayar.json'daki ilk uyduya --yakin-km'den yakın geçen Fengyun-1C parçalarını say")
    p.add_argument("--yakin-km", type=float, default=10, help="yakınlık eşiği (km)")
    a = p.parse_args(argv)
    if not 0 < a.saat <= 72 or not 0 <= a.en_az < 90 or not 0 < a.gokyuzu_saat <= a.saat:
        p.error("--saat 0..72, --en-az 0..89, --gokyuzu-saat 0..--saat olmalı")
    try:
        bas_dt = (dt.datetime.strptime(a.bas, "%Y-%m-%d %H:%M") if a.bas
                  else dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, second=0, microsecond=0))
    except ValueError:
        p.error('--bas "YYYY-AA-GG SS:DD" biçiminde olmalı, ör. "2026-11-25 18:00"')
    if a.veri_klasoru and not os.path.isdir(a.veri_klasoru):
        p.error(f"klasör yok: {a.veri_klasoru}")
    try:
        ayar = ist.ayar_yukle()
    except ist.AyarHatasi as hata:
        p.exit(2, f"ayar.json: {hata}\n")

    yer = yorunge.istasyon(ayar["konum"])
    ts = yorunge.zaman_olcegi
    bas = ts.utc(bas_dt.year, bas_dt.month, bas_dt.day, bas_dt.hour, bas_dt.minute)
    son = ts.tt_jd(bas.tt + a.saat / 24)
    print(f"{ayar['konum']['ad']}: {bas_dt:%d.%m.%Y %H:%M} UTC ({bas_dt + TSI:%d.%m %H:%M} TSİ) itibarıyla "
          f"{a.saat:g} saat, ufkun {a.en_az}° üstü")

    for grup, intdes, olay in GRUPLAR:
        print(f"\n{olay}")
        katalog = katalog_al(grup, intdes, a.veri_klasoru)
        if katalog:
            print(f"  katalog: {katalog[0]} enkaz parçası kaydedildi, {katalog[1]} tanesi hâlâ yörüngede")
        try:
            parcalar, atlanan = grup_tle_al(grup, a.veri_klasoru)
        except (OSError, RuntimeError) as hata:
            _uyar(f"{grup}: {hata}")
            continue
        gecis, irtifa = grup_gecisleri(parcalar, yer, bas, son, a.en_az)
        if not irtifa:
            print("  yörünge verisi olan parça yok")
            continue
        epok = max(EarthSatellite(s1, s2, ad, ts).epoch.utc_datetime() for ad, s1, s2 in parcalar)
        yas = bas.tt - ts.from_datetime(epok).tt
        print(f"  güncel yörünge verisi olan: {len(irtifa)} parça"
              + (f" ({atlanan} bozuk satır atlandı)" if atlanan else "")
              + f", irtifa ortanca {statistics.median(irtifa):.0f} km ({min(irtifa):.0f}-{max(irtifa):.0f})"
              + f"\n  geçiş: {len(gecis)}   (en yeni TLE: {epok:%d.%m.%Y})")
        if abs(yas) > yorunge.TLE_BAYAT_GUN:
            _uyar(f"{grup}: en yeni TLE başlangıçtan {yas:+.1f} gün uzakta; sonuçlar kayabilir")
        if grup == "fengyun-1c-debris":
            sinir = bas.tt + a.gokyuzu_saat / 24
            ilk = [iz for t, iz in gecis if t.tt < sinir]
            print(f"  ilk {a.gokyuzu_saat:g} saatte başlayan geçiş: {len(ilk)}")
            if a.gokyuzu:
                gokyuzu_ciz([iz for iz in ilk if iz is not None], a.en_az, a.gokyuzu)
                print(f"  çizim: {a.gokyuzu}")
            if a.yakin:
                hedef_ayar = ayar["uydular"][0]
                if a.veri_klasoru and os.path.exists(os.path.join(a.veri_klasoru, f"{hedef_ayar['norad']}.tle")):
                    with open(os.path.join(a.veri_klasoru, f"{hedef_ayar['norad']}.tle"), encoding="utf-8") as f:
                        _, s1, s2 = yorunge._tle_coz(f.read())
                    hedef = EarthSatellite(s1, s2, hedef_ayar["ad"], ts)
                else:
                    hedef = yorunge.uydu_yukle(hedef_ayar, ayar.get("tle_yenile_saat", 12))
                h_irtifa = wgs84.height_of(hedef.at(bas)).km
                yakin = yakin_gecenler(hedef, parcalar, bas, son, a.yakin_km)
                print(f"  {hedef.name} ({h_irtifa:.0f} km) çevresinde {a.yakin_km:g} km'den yakın geçen parça: "
                      f"{len(yakin)}")
                for mesafe, t, ad in yakin[:5]:
                    print(f"    {mesafe:5.1f} km  {(t.utc_datetime() + TSI):%d.%m %H:%M:%S} TSİ  {ad}")


if __name__ == "__main__":
    main()

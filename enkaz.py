"""Büyük enkaz bulutlarının istasyon gökyüzündeki geçişleri.

    .venv\\Scripts\\python enkaz.py                                   # şimdiden itibaren 24 saat, güncel TLE
    .venv\\Scripts\\python enkaz.py --bas "2026-11-25 18:00" \\
        --tle-klasoru belgeler/enkaz_tle_2026-11-25 --gokyuzu cikti/enkaz_gokyuzu.png

Bir "geçiş": parçanın ufkun --en-az derece üstüne çıkması (yükselme olayı). Aralığın başında zaten
gökyüzünde olan parçalar sayılmaz. Konum ayar.json'dan gelir. Saatler UTC verilir, ekrana TSİ de yazılır.
"""
import argparse
import datetime as dt
import os
import statistics
import sys
import time
import urllib.request

import numpy as np
from skyfield.api import EarthSatellite, wgs84

import istasyon as ist
from yer_istasyonu import yorunge

GRUP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={grup}&FORMAT=TLE"
GRUPLAR = [  # (CelesTrak grubu, olay)
    ("fengyun-1c-debris", "Fengyun-1C, uydusavar testi, 11 Ocak 2007"),
    ("cosmos-2251-debris", "Kosmos 2251, Iridium 33 ile çarpışma, 10 Şubat 2009"),
    ("iridium-33-debris", "Iridium 33, Kosmos 2251 ile çarpışma, 10 Şubat 2009"),
    ("cosmos-1408-debris", "Kosmos 1408, uydusavar testi, 15 Kasım 2021"),
]
TSI = dt.timedelta(hours=3)


def tle_listesi_coz(metin):
    """Ad + iki satırlık kayıtlar; sağlama toplamı tutmayan kayıt atlanır. (geçerliler, atlanan sayısı)"""
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
    return gecerli, atlanan


def grup_tle_al(grup, klasor=None, yenile_saat=12):
    """klasor verilirse oradan okur (ağ yok); yoksa veri/tle altında 12 saatlik önbellekle indirir."""
    if klasor:
        yol = os.path.join(klasor, f"{grup}.tle")
    else:
        os.makedirs(yorunge.TLE_KLASORU, exist_ok=True)
        yol = os.path.join(yorunge.TLE_KLASORU, f"grup-{grup}.tle")
        taze = os.path.exists(yol) and time.time() - os.path.getmtime(yol) < yenile_saat * 3600
        if not taze:
            istek = urllib.request.Request(GRUP_URL.format(grup=grup), headers={"User-Agent": "yer-istasyonu/1.0"})
            metin = urllib.request.urlopen(istek, timeout=60).read().decode("utf-8", "replace")
            if tle_listesi_coz(metin)[0]:
                with open(yol + ".yeni", "w", encoding="utf-8") as f:
                    f.write(metin)
                os.replace(yol + ".yeni", yol)
            elif not os.path.exists(yol):
                raise RuntimeError(f"CelesTrak {grup} için TLE vermedi: {metin.strip()[:80]!r}")
            time.sleep(2)    # CelesTrak'a nezaket
    with open(yol, encoding="utf-8", errors="replace") as f:
        return tle_listesi_coz(f.read())


def grup_gecisleri(parcalar, yer, bas, son, en_az):
    """Her parça için (yükseliş zamanı, iz) listesi; iz = (azimut rad, 90-yükseklik) dizileri."""
    ts = yorunge.zaman_olcegi
    sonuc, irtifalar = [], []
    for ad, s1, s2 in parcalar:
        uydu = EarthSatellite(s1, s2, ad, ts)
        irtifalar.append(wgs84.height_of(uydu.at(bas)).km)
        t, olay = uydu.find_events(yer, bas, son, altitude_degrees=en_az)
        aos = None
        for ti, oi in zip(t, olay):
            if oi == 0:
                aos = ti
                sonuc.append([ti, None])
            elif oi == 2 and aos is not None:
                n = max(8, int((ti.tt - aos.tt) * 86400 / 4))
                yuk, az, _ = (uydu - yer).at(ts.tt_jd(np.linspace(aos.tt, ti.tt, n))).altaz()
                sonuc[-1][1] = (az.radians, 90 - yuk.degrees)
                aos = None
    return sonuc, irtifalar


def gokyuzu_ciz(izler, en_az, yol):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(6, 6), dpi=400)
    fig.patch.set_alpha(0)
    ax = fig.add_subplot(projection="polar")
    ax.set_facecolor((0, 0, 0, 0))
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)              # yukarı kuzey, sağ doğu (yukarıdan bakış)
    ax.set_rlim(0, 90 - en_az)
    for az, r in izler:
        ax.plot(az, r, color="#ffa264", lw=0.7, alpha=0.75, solid_capstyle="round")
    halka = np.linspace(0, 2 * np.pi, 400)
    for rr in range(20, 90 - en_az + 1, 20):
        kenar = rr == 90 - en_az
        ax.plot(halka, [rr] * 400, color="#ffffff", lw=0.9 if kenar else 0.5, alpha=0.35 if kenar else 0.14)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["polar"].set_visible(False)
    ax.grid(False)
    plt.subplots_adjust(0, 0, 1, 1)
    os.makedirs(os.path.dirname(os.path.abspath(yol)), exist_ok=True)
    fig.savefig(yol, transparent=True)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Enkaz bulutlarının istasyon gökyüzündeki geçişleri")
    p.add_argument("--bas", help='UTC başlangıç, "YYYY-AA-GG SS:DD" (varsayılan: şimdi)')
    p.add_argument("--saat", type=float, default=24, help="hesap süresi (saat)")
    p.add_argument("--en-az", type=int, default=10, help="ufkun kaç derece üstü sayılsın")
    p.add_argument("--tle-klasoru", help="TLE'leri bu klasörden oku (<grup>.tle); verilmezse CelesTrak")
    p.add_argument("--gokyuzu", help="Fengyun-1C geçişlerinin gökyüzü çizimi (PNG yolu)")
    p.add_argument("--gokyuzu-saat", type=float, default=1, help="çizime girecek ilk kaç saat")
    a = p.parse_args(argv)
    if not 0 < a.saat <= 72 or not 0 <= a.en_az < 90:
        p.error("--saat 0..72, --en-az 0..89 olmalı")

    ayar = ist.ayar_yukle()
    yer = yorunge.istasyon(ayar["konum"])
    ts = yorunge.zaman_olcegi
    bas_dt = (dt.datetime.strptime(a.bas, "%Y-%m-%d %H:%M") if a.bas
              else dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, second=0, microsecond=0))
    bas = ts.utc(bas_dt.year, bas_dt.month, bas_dt.day, bas_dt.hour, bas_dt.minute)
    son = ts.tt_jd(bas.tt + a.saat / 24)
    print(f"{ayar['konum']['ad']}: {bas_dt:%d.%m.%Y %H:%M} UTC ({bas_dt + TSI:%H:%M} TSİ) itibarıyla "
          f"{a.saat:g} saat, ufkun {a.en_az}° üstü")

    for grup, olay in GRUPLAR:
        parcalar, atlanan = grup_tle_al(grup, a.tle_klasoru)
        gecis, irtifa = grup_gecisleri(parcalar, yer, bas, son, a.en_az)
        epok = max(EarthSatellite(s1, s2, ad, ts).epoch.utc_datetime() for ad, s1, s2 in parcalar)
        print(f"\n{olay}\n  yörüngede: {len(parcalar)} parça"
              + (f" ({atlanan} bozuk satır atlandı)" if atlanan else "")
              + f", irtifa ortanca {statistics.median(irtifa):.0f} km ({min(irtifa):.0f}-{max(irtifa):.0f})"
              + f"\n  geçiş: {len(gecis)}   (en yeni TLE: {epok:%d.%m.%Y})")
        if grup == "fengyun-1c-debris":
            sinir = bas.tt + a.gokyuzu_saat / 24
            ilk = [iz for t, iz in gecis if t.tt < sinir]
            print(f"  ilk {a.gokyuzu_saat:g} saatte başlayan geçiş: {len(ilk)}")
            if a.gokyuzu:
                gokyuzu_ciz([iz for iz in ilk if iz is not None], a.en_az, a.gokyuzu)
                print(f"  çizim: {a.gokyuzu}")


if __name__ == "__main__":
    main()

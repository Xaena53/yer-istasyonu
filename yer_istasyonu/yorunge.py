"""Yörünge verisi (TLE) ve istasyon üstünden geçiş hesabı."""
import os
import sys
import time
import urllib.request
from dataclasses import dataclass, field

from skyfield.api import EarthSatellite, load, wgs84

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TLE_KLASORU = os.path.join(KOK, "veri", "tle")
TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=TLE"
TLE_BAYAT_GUN = 3          # bundan eski TLE ile geçiş saatleri dakikalarca kayabilir

zaman_olcegi = load.timescale()


@dataclass
class Gecis:
    uydu: str
    aos: object                  # ufkun üstüne çıkış (skyfield Time)
    tca: object                  # en yüksek nokta
    los: object                  # ufkun altına iniş
    en_yuksek: float             # derece
    az_aos: float
    az_los: float
    yon: str                     # "kuzeyden güneye" / "güneyden kuzeye"
    iz: list = field(default_factory=list)   # [(zaman, yükseklik, azimut, enlem, boylam)]

    @property
    def sure_dk(self):
        return (self.los.tt - self.aos.tt) * 24 * 60


def tle_satiri_gecerli(satir, no):
    """TLE satırı: doğru başlangıç, 69 karakter ve mod-10 sağlama toplamı."""
    if len(satir) != 69 or not satir.startswith(f"{no} ") or not satir[-1].isdigit():
        return False
    toplam = sum(int(c) if c.isdigit() else (1 if c == "-" else 0) for c in satir[:-1])
    return toplam % 10 == int(satir[-1])


def _tle_coz(metin):
    """Ad + iki satır; geçersizse None."""
    satirlar = [s.rstrip() for s in metin.strip().splitlines() if s.strip()]
    if len(satirlar) < 3:
        return None
    ad, s1, s2 = satirlar[:3]
    if not (tle_satiri_gecerli(s1, 1) and tle_satiri_gecerli(s2, 2)):
        return None
    return ad.strip(), s1, s2


def tle_al(norad, yenile_saat=12, cevrimdisi=False, uyar=None):
    """Celestrak'tan TLE indirir; yerel kopya yenile_saat'ten tazeyse onu kullanır.

    İndirme başarısız olursa eski kopyayla devam eder ve uyarır; bozuk kopya hiç kullanılmaz.
    """
    uyar = uyar or (lambda m: print(f"uyarı: {m}", file=sys.stderr))
    os.makedirs(TLE_KLASORU, exist_ok=True)
    yol = os.path.join(TLE_KLASORU, f"{norad}.tle")
    taze = os.path.exists(yol) and time.time() - os.path.getmtime(yol) < yenile_saat * 3600
    if not taze and not cevrimdisi:
        try:
            istek = urllib.request.Request(TLE_URL.format(norad=norad), headers={"User-Agent": "yer-istasyonu/1.0"})
            metin = urllib.request.urlopen(istek, timeout=15).read().decode("utf-8", "replace")
            tle = _tle_coz(metin)
            if tle:
                gecici = yol + ".yeni"
                with open(gecici, "w", encoding="ascii") as f:
                    f.write("\n".join(tle) + "\n")
                os.replace(gecici, yol)        # yarıda kesilirse eski kopya bozulmaz
            else:
                uyar(f"Celestrak {norad} için geçerli TLE vermedi: {metin.strip()[:80]!r}")
        except OSError as hata:
            uyar(f"TLE indirilemedi ({hata}); yerel kopya kullanılıyor")
    if not os.path.exists(yol):
        raise RuntimeError(f"{norad} için TLE yok (internet bağlantısını kontrol et)")
    with open(yol, encoding="ascii", errors="replace") as f:
        tle = _tle_coz(f.read())
    if not tle:
        raise RuntimeError(f"{yol} bozuk; dosyayı sil, program yeniden indirsin")
    return tle


def tle_yasi_gun(uydu, t=None):
    t = zaman_olcegi.now() if t is None else t
    return t.tt - uydu.epoch.tt


def uydu_yukle(uydu_ayar, yenile_saat=12, cevrimdisi=False, uyar=None):
    uyar = uyar or (lambda m: print(f"uyarı: {m}", file=sys.stderr))
    ad, s1, s2 = tle_al(uydu_ayar["norad"], yenile_saat, cevrimdisi, uyar)
    uydu = EarthSatellite(s1, s2, uydu_ayar.get("ad", ad), zaman_olcegi)
    yas = tle_yasi_gun(uydu)
    if yas > TLE_BAYAT_GUN:
        uyar(f"{uydu.name} TLE'si {yas:.1f} günlük; geçiş saatleri kayabilir")
    return uydu


def istasyon(konum):
    return wgs84.latlon(konum["enlem"], konum["boylam"], elevation_m=konum.get("yukseklik_m", 0))


def gecisler(uydu, yer, bas, son, en_az_yukseklik=25.0, adim_sn=20):
    """bas..son (skyfield Time) arasında en yüksek noktası en_az_yukseklik'i aşan geçişler.

    Yalnız aralık içinde başlayıp biten tam geçişler döner (bas anında süren geçiş atlanır).
    """
    t, olay = uydu.find_events(yer, bas, son, altitude_degrees=0.0)
    sonuc, acik = [], {}
    for ti, oi in zip(t, olay):
        if oi == 0:
            acik = {"aos": ti, "tca": []}
        elif oi == 1 and "aos" in acik:
            acik["tca"].append(ti)               # nadiren bir geçişte iki tepe olur
        elif oi == 2 and acik.get("tca"):
            g = _gecis_kur(uydu, yer, acik["aos"], acik["tca"], ti, adim_sn)
            if g.en_yuksek >= en_az_yukseklik:
                sonuc.append(g)
            acik = {}
        elif oi == 2:
            acik = {}
    return sonuc


def _gecis_kur(uydu, yer, aos, tepeler, los, adim_sn):
    fark = uydu - yer
    yukseklikler = [float(fark.at(t).altaz()[0].degrees) for t in tepeler]
    en_yuksek = max(yukseklikler)
    tca = tepeler[yukseklikler.index(en_yuksek)]
    adim = max(2, int((los.tt - aos.tt) * 86400 / adim_sn))
    zamanlar = zaman_olcegi.tt_jd([aos.tt + (los.tt - aos.tt) * i / adim for i in range(adim + 1)])
    yuk, az, _ = fark.at(zamanlar).altaz()
    alt_nokta = wgs84.subpoint_of(uydu.at(zamanlar))
    iz = list(zip(zamanlar, yuk.degrees, az.degrees, alt_nokta.latitude.degrees, alt_nokta.longitude.degrees))
    yon = "kuzeyden güneye" if iz[0][3] > iz[-1][3] else "güneyden kuzeye"
    return Gecis(uydu.name, aos, tca, los, en_yuksek, float(az.degrees[0]), float(az.degrees[-1]), yon, iz)


def pusula(az):
    adlar = ["K", "KKD", "KD", "DKD", "D", "DGD", "GD", "GGD", "G", "GGB", "GB", "BGB", "B", "BKB", "KB", "KKB"]
    return adlar[int((az % 360) / 22.5 + 0.5) % 16]

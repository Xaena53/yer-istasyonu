"""Yörünge verisi (TLE) ve istasyon üstünden geçiş hesabı."""
import os
import time
import urllib.request
from dataclasses import dataclass, field

from skyfield.api import EarthSatellite, load, wgs84

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TLE_KLASORU = os.path.join(KOK, "veri", "tle")
TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=TLE"

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


def tle_al(norad, yenile_saat=12, cevrimdisi=False):
    """Celestrak'tan TLE indirir; yerel kopya yenile_saat'ten tazeyse onu kullanır."""
    os.makedirs(TLE_KLASORU, exist_ok=True)
    yol = os.path.join(TLE_KLASORU, f"{norad}.tle")
    taze = os.path.exists(yol) and time.time() - os.path.getmtime(yol) < yenile_saat * 3600
    if not taze and not cevrimdisi:
        try:
            istek = urllib.request.Request(TLE_URL.format(norad=norad), headers={"User-Agent": "yer-istasyonu/1.0"})
            metin = urllib.request.urlopen(istek, timeout=15).read().decode()
            satirlar = [s.rstrip() for s in metin.strip().splitlines()]
            if len(satirlar) >= 3 and satirlar[1].startswith("1 ") and satirlar[2].startswith("2 "):
                with open(yol, "w") as f:
                    f.write("\n".join(satirlar[:3]) + "\n")
        except OSError:
            pass                   # ağ yoksa eski kopyayla devam
    if not os.path.exists(yol):
        raise RuntimeError(f"{norad} için TLE yok (internet bağlantısını kontrol et)")
    with open(yol) as f:
        ad, s1, s2 = [s.rstrip() for s in f.read().strip().splitlines()[:3]]
    return ad.strip(), s1, s2


def uydu_yukle(uydu_ayar, yenile_saat=12, cevrimdisi=False):
    ad, s1, s2 = tle_al(uydu_ayar["norad"], yenile_saat, cevrimdisi)
    return EarthSatellite(s1, s2, uydu_ayar.get("ad", ad), zaman_olcegi)


def istasyon(konum):
    return wgs84.latlon(konum["enlem"], konum["boylam"], elevation_m=konum.get("yukseklik_m", 0))


def gecisler(uydu, yer, bas, son, en_az_yukseklik=25.0, adim_sn=20):
    """bas..son (skyfield Time) arasında en yüksek noktası en_az_yukseklik'i aşan geçişler."""
    t, olay = uydu.find_events(yer, bas, son, altitude_degrees=0.0)
    sonuc, acik = [], {}
    for ti, oi in zip(t, olay):
        if oi == 0:
            acik = {"aos": ti}
        elif oi == 1 and "aos" in acik:
            acik["tca"] = ti
        elif oi == 2 and "tca" in acik:
            g = _gecis_kur(uydu, yer, acik["aos"], acik["tca"], ti, adim_sn)
            if g.en_yuksek >= en_az_yukseklik:
                sonuc.append(g)
            acik = {}
    return sonuc


def _gecis_kur(uydu, yer, aos, tca, los, adim_sn):
    fark = uydu - yer
    adim = max(2, int((los.tt - aos.tt) * 86400 / adim_sn))
    zamanlar = zaman_olcegi.tt_jd([aos.tt + (los.tt - aos.tt) * i / adim for i in range(adim + 1)])
    yuk, az, _ = fark.at(zamanlar).altaz()
    alt_nokta = wgs84.subpoint_of(uydu.at(zamanlar))
    iz = list(zip(zamanlar, yuk.degrees, az.degrees, alt_nokta.latitude.degrees, alt_nokta.longitude.degrees))
    en_yuksek = float(fark.at(tca).altaz()[0].degrees)
    yon = "kuzeyden güneye" if iz[0][3] > iz[-1][3] else "güneyden kuzeye"
    return Gecis(uydu.name, aos, tca, los, en_yuksek, float(az.degrees[0]), float(az.degrees[-1]), yon, iz)


def pusula(az):
    adlar = ["K", "KKD", "KD", "DKD", "D", "DGD", "GD", "GGD", "G", "GGB", "GB", "BGB", "B", "BKB", "KB", "KKB"]
    return adlar[int((az % 360) / 22.5 + 0.5) % 16]

"""Yer istasyonu testleri (ağ gerekmez: sabit bir TLE ile)."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from skyfield.api import EarthSatellite  # noqa: E402

from yer_istasyonu import gorsel, kayit, yorunge  # noqa: E402

S1 = "1 59051U 24039A   26323.14606593  .00000025  00000+0  31003-4 0  9995"
S2 = "2 59051  98.7252 280.6559 0008142  82.3216 277.8886 14.22443897141294"
KONUM = {"ad": "Eskişehir", "enlem": 39.7767, "boylam": 30.5206, "yukseklik_m": 790}


def test():
    ts = yorunge.zaman_olcegi
    uydu = EarthSatellite(S1, S2, "Meteor-M N2-4", ts)
    bas = ts.utc(2026, 11, 19)
    son = ts.utc(2026, 11, 26)
    liste = yorunge.gecisler(uydu, yorunge.istasyon(KONUM), bas, son, 25)
    assert 10 <= len(liste) <= 40, len(liste)               # güneş eşzamanlı yörünge: günde 2-4 iyi geçiş
    for g in liste:
        assert g.aos.tt < g.tca.tt < g.los.tt
        assert 25 <= g.en_yuksek <= 90
        assert 5 < g.sure_dk < 20
        assert max(p[1] for p in g.iz) <= g.en_yuksek + 0.5
    # bilinen geçiş: 19.11 ~15:00 TR, ~73°
    ogle = [g for g in liste if gorsel.yerel(g.tca).day == 19 and gorsel.yerel(g.tca).hour == 15]
    assert len(ogle) == 1 and 70 < ogle[0].en_yuksek < 76, [(gorsel.yerel(g.tca), g.en_yuksek) for g in liste[:4]]
    ilk = ogle[0]

    komut = kayit.satdump_komutu(ilk, {"pipeline": "meteor_m2-x_lrpt_80k", "frekans_hz": 137900000},
                                 {"kaynak": "rtlsdr", "ornekleme": 1024000, "kazanc": 38}, "kayitlar", 60)
    assert komut[:3] == ["satdump", "live", "meteor_m2-x_lrpt_80k"]
    assert komut[komut.index("--frequency") + 1] == "137900000"
    assert abs(int(komut[komut.index("--timeout") + 1]) - (ilk.sure_dk * 60 + 120)) < 2

    # güneş: Eskişehir'de 21 Haziran öğle yüksek, gece yarısı ufkun altında
    yaz = dt.datetime(2026, 6, 21, 12, 30, tzinfo=gorsel.TR)
    assert 70 < gorsel.gunes_yuksekligi(yaz, 39.78, 30.52) < 75
    assert gorsel.gunes_yuksekligi(yaz.replace(hour=0), 39.78, 30.52) < -20
    assert 1200 < gorsel.gorus_yaricapi_km(830, 25) < 1400
    print("yer istasyonu testi geçti")


if __name__ == "__main__":
    test()

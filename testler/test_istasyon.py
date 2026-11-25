"""Yer istasyonu testleri (ağ gerekmez: sabit bir TLE ile).

    python testler/test_istasyon.py      (ya da pytest)
"""
import copy
import datetime as dt
import os
import sys
import tempfile
import time

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, KOK)
from skyfield.api import EarthSatellite  # noqa: E402

import istasyon  # noqa: E402
from yer_istasyonu import gorsel, kayit, yorunge  # noqa: E402

S1 = "1 59051U 24039A   26323.14606593  .00000025  00000+0  31003-4 0  9995"
S2 = "2 59051  98.7252 280.6559 0008142  82.3216 277.8886 14.22443897141294"
KONUM = {"ad": "Eskişehir", "enlem": 39.7767, "boylam": 30.5206, "yukseklik_m": 790}
UYDU_AYAR = {"ad": "Meteor-M N2-4", "norad": 59051, "pipeline": "meteor_m2-x_lrpt_80k", "frekans_hz": 137900000}
ts = yorunge.zaman_olcegi


def _uydu():
    return EarthSatellite(S1, S2, "Meteor-M N2-4", ts)


def _ayar(**degisen):
    a = {"konum": dict(KONUM), "en_az_yukseklik": 25, "uydular": [dict(UYDU_AYAR)],
         "alici": {"satdump": "satdump", "kaynak": "rtlsdr", "ornekleme": 1024000, "kazanc": 38, "ek": []},
         "kayit_klasoru": "kayitlar", "gecis_oncesi_sn": 60}
    a.update(degisen)
    return a


def test_gecisler():
    liste = yorunge.gecisler(_uydu(), yorunge.istasyon(KONUM), ts.utc(2026, 11, 19), ts.utc(2026, 11, 26), 25)
    assert 10 <= len(liste) <= 40, len(liste)               # güneş eşzamanlı yörünge: günde 2-4 iyi geçiş
    for g in liste:
        assert g.aos.tt < g.tca.tt < g.los.tt
        assert 25 <= g.en_yuksek <= 90
        assert 5 < g.sure_dk < 20
        assert max(p[1] for p in g.iz) <= g.en_yuksek + 0.5
    # bilinen geçiş: 19.11 ~15:00 TR, ~73°
    ogle = [g for g in liste if gorsel.yerel(g.tca).day == 19 and gorsel.yerel(g.tca).hour == 15]
    assert len(ogle) == 1 and 70 < ogle[0].en_yuksek < 76, [(gorsel.yerel(g.tca), g.en_yuksek) for g in liste[:4]]


def test_suren_gecis_atlanir():
    """Aralık bir geçişin ortasında başlarsa o yarım geçiş listeye girmez, sonrakiler girer."""
    yer = yorunge.istasyon(KONUM)
    tam = yorunge.gecisler(_uydu(), yer, ts.utc(2026, 11, 19), ts.utc(2026, 11, 21), 0)
    orta = ts.tt_jd((tam[0].aos.tt + tam[0].los.tt) / 2)
    kirpik = yorunge.gecisler(_uydu(), yer, orta, ts.utc(2026, 11, 21), 0)
    assert len(kirpik) == len(tam) - 1
    assert abs(kirpik[0].aos.tt - tam[1].aos.tt) < 1e-6


def test_tle_sagilama():
    assert yorunge.tle_satiri_gecerli(S1, 1) and yorunge.tle_satiri_gecerli(S2, 2)
    bozuk = S1[:-1] + str((int(S1[-1]) + 1) % 10)
    assert not yorunge.tle_satiri_gecerli(bozuk, 1)
    assert not yorunge.tle_satiri_gecerli(S2, 1)
    assert not yorunge.tle_satiri_gecerli(S1[:40], 1)
    assert yorunge._tle_coz("No GP data found") is None
    assert yorunge._tle_coz(f"METEOR-M2 4\n{S1}\n{S2}\n") == ("METEOR-M2 4", S1, S2)


def test_tle_onbellek():
    """Çevrimdışı: geçerli kopya okunur, bozuk kopya açık bir hatayla reddedilir."""
    eski = yorunge.TLE_KLASORU
    with tempfile.TemporaryDirectory() as d:
        yorunge.TLE_KLASORU = d
        try:
            with open(os.path.join(d, "59051.tle"), "w") as f:
                f.write(f"METEOR-M2 4\n{S1}\n{S2}\n")
            assert yorunge.tle_al(59051, cevrimdisi=True)[1] == S1
            uyarilar = []
            u = yorunge.uydu_yukle(UYDU_AYAR, cevrimdisi=True, uyar=uyarilar.append)
            assert u.name == "Meteor-M N2-4"
            if yorunge.tle_yasi_gun(u) > yorunge.TLE_BAYAT_GUN:
                assert any("günlük" in m for m in uyarilar)
            with open(os.path.join(d, "59051.tle"), "w") as f:
                f.write("<html>hata</html>")
            try:
                yorunge.tle_al(59051, cevrimdisi=True)
                assert False, "bozuk TLE kabul edildi"
            except RuntimeError as h:
                assert "bozuk" in str(h)
            try:
                yorunge.tle_al(12345, cevrimdisi=True)
                assert False, "olmayan TLE kabul edildi"
            except RuntimeError:
                pass
        finally:
            yorunge.TLE_KLASORU = eski


def test_tle_yasi():
    u = _uydu()
    assert abs(yorunge.tle_yasi_gun(u, ts.utc(2026, 11, 20, 3, 30)) - 1.0) < 0.01


def test_satdump_komutu():
    ilk = yorunge.gecisler(_uydu(), yorunge.istasyon(KONUM), ts.utc(2026, 11, 19), ts.utc(2026, 11, 20), 25)[0]
    alici = {"kaynak": "rtlsdr", "ornekleme": 1024000, "kazanc": 38, "ek": ["--bias"]}
    komut = kayit.satdump_komutu(ilk, UYDU_AYAR, alici, "kayitlar", 60)
    assert komut[:3] == ["satdump", "live", "meteor_m2-x_lrpt_80k"]
    assert komut[komut.index("--frequency") + 1] == "137900000"
    assert abs(int(komut[komut.index("--timeout") + 1]) - (ilk.sure_dk * 60 + 120)) < 2
    assert komut[-1] == "--bias"
    gec = kayit.satdump_komutu(ilk, UYDU_AYAR, alici, "kayitlar", 60, sure_sn=300)
    assert gec[gec.index("--timeout") + 1] == "300"


def _simdiki_gecis(aos_sn, los_sn):
    """Şu andan aos_sn/los_sn saniye sonra başlayıp biten sahte bir geçiş."""
    simdi = ts.now()
    aos, los = ts.tt_jd(simdi.tt + aos_sn / 86400), ts.tt_jd(simdi.tt + los_sn / 86400)
    return yorunge.Gecis("Deneme Uydu", aos, aos, los, 60.0, 0.0, 180.0, "kuzeyden güneye")


def test_kayit_satdump_yok():
    with tempfile.TemporaryDirectory() as d:
        a = _ayar(kayit_klasoru=d)
        a["alici"]["satdump"] = "boyle-bir-program-yok-xyz"
        mesajlar = []
        rc = kayit.bekle_ve_kaydet(_simdiki_gecis(-30, 600), UYDU_AYAR, a, yazdir=mesajlar.append)
        assert rc is None and any("bulunamadı" in m for m in mesajlar), mesajlar


def test_kayit_gecis_kacti():
    with tempfile.TemporaryDirectory() as d:
        a = _ayar(kayit_klasoru=d)
        a["alici"]["satdump"] = sys.executable
        mesajlar = []
        rc = kayit.bekle_ve_kaydet(_simdiki_gecis(-900, -100), UYDU_AYAR, a, yazdir=mesajlar.append)
        assert rc is None and any("kaçırıldı" in m for m in mesajlar), mesajlar
        assert os.listdir(d) == []


def test_kayit_calisir_ve_gunluk_yazar():
    """SatDump yerine Python: 'live' dosyası olmadığı için hata koduyla biter; günlük yazılmalı."""
    with tempfile.TemporaryDirectory() as d:
        a = _ayar(kayit_klasoru=d)
        a["alici"]["satdump"] = sys.executable
        mesajlar = []
        rc = kayit.bekle_ve_kaydet(_simdiki_gecis(-120, 300), UYDU_AYAR, a, yazdir=mesajlar.append)
        assert rc not in (None, 0), rc
        klasorler = os.listdir(d)
        assert len(klasorler) == 1
        assert os.path.getsize(os.path.join(d, klasorler[0], "satdump.log")) > 0
        assert any("hata koduyla" in m for m in mesajlar)


def test_ayar_dogrulama():
    istasyon.ayar_dogrula(_ayar())
    hatali = [
        _ayar(en_az_yukseklik=95),
        _ayar(uydular=[]),
        _ayar(konum={"enlem": 39.7, "boylam": 230}),
        _ayar(uydular=[dict(UYDU_AYAR, norad="59051")]),
        _ayar(uydular=[dict(UYDU_AYAR, pipeline="")]),
        _ayar(alici={"ek": "--bias"}),
        _ayar(tle_yenile_saat=0.5),
    ]
    for a in hatali:
        try:
            istasyon.ayar_dogrula(copy.deepcopy(a))
            assert False, f"hatalı ayar kabul edildi: {a}"
        except istasyon.AyarHatasi:
            pass
    asil = istasyon.ayar_yukle()
    assert asil["uydular"][0]["norad"] == 59051


def test_gunes_ve_gorus():
    # Eskişehir'de 21 Haziran öğle yüksek, gece yarısı ufkun altında
    yaz = dt.datetime(2026, 6, 21, 12, 30, tzinfo=gorsel.TR)
    assert 70 < gorsel.gunes_yuksekligi(yaz, 39.78, 30.52) < 75
    assert gorsel.gunes_yuksekligi(yaz.replace(hour=0), 39.78, 30.52) < -20
    assert 1200 < gorsel.gorus_yaricapi_km(830, 25) < 1400
    assert gorsel.haritanin_kutusu(KONUM) == (30.5206 - 20.5, 30.5206 + 21.5, 39.7767 - 18, 39.7767 + 18)


def test_gorseller():
    liste = yorunge.gecisler(_uydu(), yorunge.istasyon(KONUM), ts.utc(2026, 11, 19), ts.utc(2026, 11, 26), 25)
    with tempfile.TemporaryDirectory() as d:
        for yol in (gorsel.gokyuzu(liste[:6], KONUM, os.path.join(d, "g.png")),
                    gorsel.harita(liste[:3], KONUM, os.path.join(d, "h.png")),
                    gorsel.takvim(liste, os.path.join(d, "t.png"), KONUM)):
            assert os.path.getsize(yol) > 10_000
        for f in (lambda: gorsel.gokyuzu([], KONUM, "x.png"), lambda: gorsel.takvim([], "x.png", KONUM)):
            try:
                f()
                assert False
            except ValueError:
                pass


class _SahteYanit:
    def __init__(self, metin):
        self.metin = metin.encode()

    def read(self):
        return self.metin


def _gecici_tle(d, eski_sn=0):
    yol = os.path.join(d, "59051.tle")
    with open(yol, "w") as f:
        f.write(f"METEOR-M2 4\n{S1}\n{S2}\n")
    if eski_sn:
        os.utime(yol, (time.time() - eski_sn, time.time() - eski_sn))
    return yol


def test_tle_indirme_ve_guncellenmedi_yaniti():
    """Geçerli yanıt dosyayı yeniler; 'güncellenmedi' yanıtı eski kopyayı korur ve tekrar sormaz."""
    eski_klasor, eski_ac = yorunge.TLE_KLASORU, yorunge.urllib.request.urlopen
    with tempfile.TemporaryDirectory() as d:
        yorunge.TLE_KLASORU = d
        cagri = []
        try:
            yol = _gecici_tle(d, eski_sn=13 * 3600)
            yorunge.urllib.request.urlopen = lambda *a, **k: (cagri.append(1), _SahteYanit(
                "GP data has not updated since your last successful download."))[1]
            uyarilar = []
            assert yorunge.tle_al(59051, uyar=uyarilar.append)[1] == S1
            assert len(cagri) == 1 and uyarilar
            assert time.time() - os.path.getmtime(yol) < 60          # taze sayıldı
            yorunge.tle_al(59051, uyar=uyarilar.append)
            assert len(cagri) == 1                                   # ikinci kez sorulmadı
            os.utime(yol, (time.time() - 13 * 3600,) * 2)
            # Celestrak satır sonu CRLF; yeni kopya atomik yazılır
            yorunge.urllib.request.urlopen = lambda *a, **k: _SahteYanit(f"METEOR-M2 4\r\n{S1}\r\n{S2}\r\n")
            assert yorunge.tle_al(59051, uyar=uyarilar.append) == ("METEOR-M2 4", S1, S2)
            assert not os.path.exists(yol + ".yeni")

            def kopuk(*a, **k):
                raise OSError("ağ yok")
            os.utime(yol, (time.time() - 13 * 3600,) * 2)
            yorunge.urllib.request.urlopen = kopuk
            uyarilar.clear()
            assert yorunge.tle_al(59051, uyar=uyarilar.append)[1] == S1
            assert any("indirilemedi" in m for m in uyarilar)
        finally:
            yorunge.TLE_KLASORU, yorunge.urllib.request.urlopen = eski_klasor, eski_ac


def test_hepsi_bir_uydu_bozuksa_digerleri_surer():
    eski = yorunge.TLE_KLASORU
    with tempfile.TemporaryDirectory() as d:
        yorunge.TLE_KLASORU = d
        try:
            _gecici_tle(d)
            a = _ayar(uydular=[dict(UYDU_AYAR), dict(UYDU_AYAR, norad=11111, ad="Yok")])
            a["tle_yenile_saat"] = 12
            liste = istasyon.hepsi(a, 2, cevrimdisi=True)
            assert liste and all(g.uydu == "Meteor-M N2-4" for g, _ in liste)
            a["uydular"] = [dict(UYDU_AYAR, norad=11111)]
            try:
                istasyon.hepsi(a, 2, cevrimdisi=True)
                assert False, "hiç TLE yokken hata vermeliydi"
            except RuntimeError:
                pass
        finally:
            yorunge.TLE_KLASORU = eski


def test_kontrol_cokmez():
    eski = yorunge.TLE_KLASORU
    with tempfile.TemporaryDirectory() as d:
        yorunge.TLE_KLASORU = d
        try:
            _gecici_tle(d)
            uydu = dict(UYDU_AYAR)
            del uydu["ad"]                                          # ad isteğe bağlı
            a = istasyon.ayar_dogrula(_ayar(uydular=[uydu], kayit_klasoru=os.path.join(d, "k")))
            a["alici"]["satdump"] = "boyle-bir-program-yok-xyz"
            sorun = istasyon.kontrol(a, cevrimdisi=True)
            assert sorun >= 1                                       # en az SatDump eksik
        finally:
            yorunge.TLE_KLASORU = eski


def test_enkaz_tle_listesi_bozugu_atlar():
    import enkaz
    bozuk = S2[:-1] + str((int(S2[-1]) + 1) % 10)
    metin = "\n".join(["A", S1, S2, "B", S1, bozuk, "C", S1, S2, ""])
    gecerli, atlanan = enkaz.tle_listesi_coz(metin)
    assert [k[0] for k in gecerli] == ["A", "C"]
    assert atlanan > 0
    assert enkaz.tle_listesi_coz("")[0] == []


def test_enkaz_anlik_kayit_ayni_sayilari_verir():
    import enkaz
    klasor = os.path.join(KOK, "belgeler", "enkaz_tle_2026-11-25")
    parcalar, atlanan = enkaz.grup_tle_al("cosmos-1408-debris", klasor)
    assert len(parcalar) == 2 and atlanan == 0
    yer = yorunge.istasyon(KONUM)
    bas = ts.utc(2026, 11, 25, 18)
    gecis, _ = enkaz.grup_gecisleri(parcalar, yer, bas, ts.tt_jd(bas.tt + 1), 10)
    assert len(gecis) == 7
    assert enkaz.katalog_al("cosmos-1408-debris", "1982-092", klasor) == (1806, 3)
    # ISS irtifası (420 km): bir parça kesiyor (~409-430 km), biri tamamen altına inmiş
    assert enkaz.irtifa_kesenler(parcalar, 420) == (1, 1)
    fengyun, _ = enkaz.grup_tle_al("fengyun-1c-debris", klasor)
    assert enkaz.irtifa_kesenler(fengyun, 420) == (7, 4)
    assert enkaz.irtifa_kesenler(fengyun, 680) == (393, 103)     # İMECE irtifası


def test_enkaz_ag_yokken_eski_kopya():
    import urllib.request
    import enkaz
    with tempfile.TemporaryDirectory() as d:
        yol = os.path.join(d, "x.tle")
        with open(yol, "w", encoding="utf-8") as f:
            f.write("\n".join(["A", S1, S2]))
        os.utime(yol, (0, 0))                         # bayat
        eski = urllib.request.urlopen

        def agsiz(*_a, **_k):
            raise OSError("ağ yok")
        urllib.request.urlopen = agsiz
        try:
            enkaz._onbellekli_indir("http://ornek", yol, lambda m: True)   # çökmemeli
        finally:
            urllib.request.urlopen = eski
        with open(yol, encoding="utf-8") as f:
            assert S2 in f.read()


def test_enkaz_yakin_gecis_kendini_bulur():
    import enkaz
    hedef = _uydu()
    bas = ts.utc(2026, 11, 19, 12)
    son = ts.tt_jd(bas.tt + 1 / 24)
    # aynı yörünge = sürekli 0 km; çok uzak bir parça (farklı eğim) bulunmamalı
    uzak = S2.replace("98.7252", "51.6000")
    uzak = uzak[:-1] + str(sum(int(c) if c.isdigit() else (1 if c == "-" else 0) for c in uzak[:-1]) % 10)
    sonuc = enkaz.yakin_gecenler(hedef, [("ayni", S1, S2), ("uzak", S1, uzak)], bas, son, esik_km=1)
    assert [ad for _, _, ad in sonuc] == ["ayni"] and sonuc[0][0] < 0.01


def test_enkaz_satcat_bozuk_yaniti_reddeder():
    import enkaz
    assert enkaz.satcat_coz("GP data has not updated") is None
    assert enkaz.satcat_coz('{"a": 1}') is None
    assert enkaz.satcat_coz('[{"OBJECT_TYPE": "DEB"}]') == [{"OBJECT_TYPE": "DEB"}]


def test_uyku_engelleme():
    assert kayit.uykuyu_engelle(True) in (True, False)
    kayit.uykuyu_engelle(False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    testler = [(ad, f) for ad, f in sorted(globals().items()) if ad.startswith("test_") and callable(f)]
    for ad, f in testler:
        f()
        print(f"  geçti: {ad}")
    print(f"yer istasyonu: {len(testler)} test geçti")

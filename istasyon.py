"""Evde uydu yer istasyonu.

    python istasyon.py gecisler [--gun 3]        önümüzdeki geçişleri listeler
    python istasyon.py gorsel [--gun 7]          gökyüzü, harita ve takvim görsellerini çizer (cikti/)
    python istasyon.py kontrol                   ayar, TLE, SatDump ve disk alanını denetler
    python istasyon.py calis [--kuru]            geçişleri bekler, sırası gelince SatDump ile kaydeder
"""
import argparse
import datetime as dt
import json
import os
import shutil
import sys

from yer_istasyonu import gorsel, kayit, yorunge

KOK = os.path.dirname(os.path.abspath(__file__))
UZAK_GECIS_SN = 3 * 3600      # sıradaki geçiş bundan uzaksa saatte bir TLE tazelenip yeniden hesaplanır
EN_AZ_BOS_GB = 1


class AyarHatasi(Exception):
    pass


def _sayi(d, anahtar, en_az, en_cok, yer):
    v = d.get(anahtar)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not en_az <= v <= en_cok:
        raise AyarHatasi(f"{yer}.{anahtar} {en_az}..{en_cok} arasında bir sayı olmalı (şu an: {v!r})")
    return v


def ayar_dogrula(a):
    k = a.get("konum")
    if not isinstance(k, dict):
        raise AyarHatasi("konum eksik")
    _sayi(k, "enlem", -90, 90, "konum")
    _sayi(k, "boylam", -180, 180, "konum")
    k.setdefault("ad", "İstasyon")
    k.setdefault("yukseklik_m", 0)
    _sayi(k, "yukseklik_m", -500, 9000, "konum")
    a.setdefault("en_az_yukseklik", 25)
    _sayi(a, "en_az_yukseklik", 0, 89, "ayar")
    a.setdefault("tle_yenile_saat", 12)
    _sayi(a, "tle_yenile_saat", 2, 168, "ayar")        # Celestrak 2 saatten sık indirmeyi istemiyor
    a.setdefault("gecis_oncesi_sn", 60)
    _sayi(a, "gecis_oncesi_sn", 0, 600, "ayar")
    if not isinstance(a.get("uydular"), list) or not a["uydular"]:
        raise AyarHatasi("uydular listesi boş")
    for i, u in enumerate(a["uydular"]):
        yer = f"uydular[{i}]"
        if not isinstance(u.get("norad"), int):
            raise AyarHatasi(f"{yer}.norad tam sayı olmalı")
        _sayi(u, "frekans_hz", 1e6, 1e11, yer)
        if not isinstance(u.get("pipeline"), str) or not u["pipeline"]:
            raise AyarHatasi(f"{yer}.pipeline eksik (ör. meteor_m2-x_lrpt_80k)")
    al = a.setdefault("alici", {})
    if not isinstance(al.get("ek", []), list):
        raise AyarHatasi("alici.ek bir liste olmalı, ör. [\"--bias\"]")
    for anahtar, (en_az, en_cok) in {"ornekleme": (2.5e5, 6.1e7), "kazanc": (0, 100)}.items():
        if anahtar in al:
            _sayi(al, anahtar, en_az, en_cok, "alici")
    a.setdefault("kayit_klasoru", "kayitlar")
    return a


def ayar_yukle(yol=None):
    yol = yol or os.path.join(KOK, "ayar.json")
    try:
        with open(yol, encoding="utf-8") as f:
            a = json.load(f)
    except FileNotFoundError:
        raise AyarHatasi(f"{yol} bulunamadı")
    except json.JSONDecodeError as h:
        raise AyarHatasi(f"ayar.json okunamadı: satır {h.lineno}, sütun {h.colno}: {h.msg}")
    ayar_dogrula(a)
    a["kayit_klasoru"] = os.path.join(KOK, a["kayit_klasoru"])
    return a


def hepsi(a, gun, cevrimdisi=False):
    yer = yorunge.istasyon(a["konum"])
    simdi = yorunge.zaman_olcegi.now()
    son = yorunge.zaman_olcegi.tt_jd(simdi.tt + gun)
    liste, hatalar = [], []
    for u in a["uydular"]:
        try:
            uydu = yorunge.uydu_yukle(u, a["tle_yenile_saat"], cevrimdisi)
        except RuntimeError as h:                # bir uydunun TLE'si yoksa diğerleri sürsün
            hatalar.append(str(h))
            print(f"uyarı: {h}", file=sys.stderr)
            continue
        liste += [(g, u) for g in yorunge.gecisler(uydu, yer, simdi, son, a["en_az_yukseklik"])]
    if hatalar and len(hatalar) == len(a["uydular"]):
        raise RuntimeError("; ".join(hatalar))
    return sorted(liste, key=lambda p: p[0].aos.tt)


def gunluk(mesaj):
    print(f"[{dt.datetime.now():%d.%m %H:%M:%S}] {mesaj}", flush=True)


def calis(a, kuru=False, cevrimdisi=False):
    gunluk(f"Yer istasyonu çalışıyor: {a['konum']['ad']}, en az {a['en_az_yukseklik']}°")
    if not kuru:
        if not kayit.satdump_bul(a["alici"]):
            gunluk(f"uyarı: SatDump bulunamadı ({a['alici'].get('satdump', 'satdump')!r}); geçişler kaydedilemez")
        if kayit.uykuyu_engelle(True):
            gunluk("bilgisayarın uykuya geçmesi istasyon açıkken engellendi")
    try:
        _calis_dongusu(a, kuru, cevrimdisi)
    finally:
        if not kuru:
            kayit.uykuyu_engelle(False)


def _calis_dongusu(a, kuru, cevrimdisi):
    duyurulan = None
    while True:
        try:
            duyurulan = _bir_tur(a, kuru, cevrimdisi, duyurulan)
        except Exception as h:                  # ağ, TLE, disk, beklenmedik: istasyon kapanmasın
            gunluk(f"hata: {type(h).__name__}: {h}; 10 dk sonra yeniden denenecek")
            if kuru:
                raise
            kayit.uyu(600)
            continue
        if kuru:
            return


def _bir_tur(a, kuru, cevrimdisi, duyurulan):
    """Döngünün bir turu: sıradaki geçişi bul, uzaksa bekle, yakınsa kaydet. Duyurulan geçişi döner."""
    liste = hepsi(a, 1, cevrimdisi)
    if not liste:
        gunluk("24 saat içinde iyi geçiş yok; 1 saat sonra yeniden bakılacak")
        kayit.uyu(3600)
        return duyurulan
    g, u = liste[0]
    kalan = (kayit.baslangic_zamani(g, a["gecis_oncesi_sn"]) - kayit.simdi()).total_seconds()
    if kalan > UZAK_GECIS_SN and not kuru:
        anahtar = (g.uydu, round(g.aos.tt * 1440))
        if anahtar != duyurulan:
            gunluk(f"sıradaki: {g.uydu} {gorsel.tablo_satiri(g)}")
            duyurulan = anahtar
        kayit.uyu(min(3600, kalan - UZAK_GECIS_SN + 60))
        return duyurulan
    rc = kayit.bekle_ve_kaydet(g, u, a, kuru=kuru, yazdir=gunluk)
    if kuru:
        return duyurulan
    gunluk(f"bitti (çıkış kodu {rc})")
    # kayıt yapılamadıysa aynı geçişi tekrar tekrar denememek için geçiş bitene dek bekle
    kayit.uyu(max(30, (kayit.bitis_zamani(g, a["gecis_oncesi_sn"]) - kayit.simdi()).total_seconds()))
    return duyurulan


def kontrol(a, cevrimdisi=False):
    """Alıcı gelmeden ya da çekim gününden önce her şeyi denetler. Sorun sayısını döner."""
    sorun = 0

    def satir(tamam, mesaj):
        nonlocal sorun
        sorun += not tamam
        print(f"  [{'TAMAM' if tamam else 'SORUN'}] {mesaj}")

    satir(True, f"ayar.json geçerli: {a['konum']['ad']} ({a['konum']['enlem']}, {a['konum']['boylam']})")
    for u in a["uydular"]:
        uyarilar = []
        try:
            uydu = yorunge.uydu_yukle(u, a["tle_yenile_saat"], cevrimdisi, uyar=uyarilar.append)
            yas = yorunge.tle_yasi_gun(uydu)
            satir(yas <= yorunge.TLE_BAYAT_GUN, f"{u.get('ad', uydu.name)} TLE {yas:.1f} günlük")
        except Exception as h:
            satir(False, f"{u.get('ad', u['norad'])}: {h}")
        for m in uyarilar:
            if "günlük" not in m:
                print(f"           {m}")
    program = kayit.satdump_bul(a["alici"])
    satir(bool(program), f"SatDump: {program or 'bulunamadı, ayar.json → alici.satdump'}")
    try:
        os.makedirs(a["kayit_klasoru"], exist_ok=True)
        deneme = os.path.join(a["kayit_klasoru"], ".yazma_denemesi")
        with open(deneme, "w") as f:
            f.write("x")
        os.remove(deneme)
        bos = shutil.disk_usage(a["kayit_klasoru"]).free / 1e9
        satir(bos >= EN_AZ_BOS_GB, f"kayıt klasörü yazılabilir, {bos:.1f} GB boş")
    except OSError as h:
        satir(False, f"kayıt klasörü kullanılamıyor: {h}")
    try:
        liste = hepsi(a, 2, cevrimdisi=True)
        if liste:
            g, _ = liste[0]
            satir(True, f"sıradaki geçiş: {g.uydu} {gorsel.tablo_satiri(g)}")
        else:
            satir(False, "48 saat içinde iyi geçiş yok (en_az_yukseklik çok mu yüksek?)")
    except Exception as h:
        satir(False, f"geçiş hesabı: {h}")
    print("hazır" if not sorun else f"{sorun} sorun var")
    return sorun


def _gun(deger):
    v = float(deger)
    if not 0 < v <= 30:
        raise argparse.ArgumentTypeError("gün 0 ile 30 arasında olmalı")
    return v


def main():
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Evde uydu yer istasyonu")
    p.add_argument("komut", choices=["gecisler", "gorsel", "kontrol", "calis"])
    p.add_argument("--gun", type=_gun, default=None)
    p.add_argument("--kuru", action="store_true", help="kaydetme, yalnız komutu yazdır")
    p.add_argument("--cevrimdisi", action="store_true", help="TLE indirme, yerel kopyayı kullan")
    arg = p.parse_args()
    try:
        a = ayar_yukle()
    except AyarHatasi as h:
        sys.exit(f"ayar hatası: {h}")

    try:
        if arg.komut == "gecisler":
            liste = hepsi(a, arg.gun or 3, arg.cevrimdisi)
            for g, _ in liste:
                print(f"{g.uydu:15} {gorsel.tablo_satiri(g)}")
            if not liste:
                print("bu aralıkta iyi geçiş yok")

        elif arg.komut == "gorsel":
            gun = arg.gun or 7
            liste = [g for g, _ in hepsi(a, gun, arg.cevrimdisi)]
            if not liste:
                sys.exit("bu aralıkta geçiş yok")
            cikti = os.path.join(KOK, "cikti")
            gun1 = [g for g in liste if g.aos.tt - liste[0].aos.tt < 1.0]
            print(gorsel.gokyuzu(liste[:6], a["konum"], os.path.join(cikti, "gokyuzu.png")))
            print(gorsel.harita(gun1, a["konum"], os.path.join(cikti, "harita.png"), en_az_derece=a["en_az_yukseklik"]))
            print(gorsel.takvim(liste, os.path.join(cikti, "takvim.png"), a["konum"], gun_sayisi=max(1, round(gun))))

        elif arg.komut == "kontrol":
            sys.exit(1 if kontrol(a, arg.cevrimdisi) else 0)

        elif arg.komut == "calis":
            calis(a, arg.kuru, arg.cevrimdisi)
    except RuntimeError as h:
        sys.exit(f"hata: {h}")
    except KeyboardInterrupt:
        print("\ndurduruldu")


if __name__ == "__main__":
    main()

"""Evde uydu yer istasyonu.

    python istasyon.py gecisler [--gun 3]        önümüzdeki geçişleri listeler
    python istasyon.py gorsel [--gun 7]          gökyüzü, harita ve takvim görsellerini çizer (cikti/)
    python istasyon.py calis [--kuru]            geçişleri bekler, sırası gelince SatDump ile kaydeder
"""
import argparse
import json
import os
import sys
import time

from yer_istasyonu import gorsel, kayit, yorunge

KOK = os.path.dirname(os.path.abspath(__file__))


def ayar_yukle():
    with open(os.path.join(KOK, "ayar.json"), encoding="utf-8") as f:
        a = json.load(f)
    a["kayit_klasoru"] = os.path.join(KOK, a["kayit_klasoru"])
    return a


def hepsi(a, gun, cevrimdisi=False):
    yer = yorunge.istasyon(a["konum"])
    simdi = yorunge.zaman_olcegi.now()
    son = yorunge.zaman_olcegi.tt_jd(simdi.tt + gun)
    liste = []
    for u in a["uydular"]:
        uydu = yorunge.uydu_yukle(u, a.get("tle_yenile_saat", 12), cevrimdisi)
        liste += [(g, u) for g in yorunge.gecisler(uydu, yer, simdi, son, a["en_az_yukseklik"])]
    return sorted(liste, key=lambda p: p[0].aos.tt)


def main():
    p = argparse.ArgumentParser(description="Evde uydu yer istasyonu")
    p.add_argument("komut", choices=["gecisler", "gorsel", "calis"])
    p.add_argument("--gun", type=float, default=None)
    p.add_argument("--kuru", action="store_true", help="kaydetme, yalnız komutu yazdır")
    p.add_argument("--cevrimdisi", action="store_true", help="TLE indirme, yerel kopyayı kullan")
    arg = p.parse_args()
    a = ayar_yukle()
    sys.stdout.reconfigure(encoding="utf-8")

    if arg.komut == "gecisler":
        for g, _ in hepsi(a, arg.gun or 3, arg.cevrimdisi):
            print(f"{g.uydu:15} {gorsel.tablo_satiri(g)}")

    elif arg.komut == "gorsel":
        liste = [g for g, _ in hepsi(a, arg.gun or 7, arg.cevrimdisi)]
        if not liste:
            sys.exit("bu aralıkta geçiş yok")
        cikti = os.path.join(KOK, "cikti")
        gun1 = [g for g in liste if g.aos.tt - liste[0].aos.tt < 1.0]
        print(gorsel.gokyuzu(liste[:6], a["konum"], os.path.join(cikti, "gokyuzu.png")))
        print(gorsel.harita(gun1, a["konum"], os.path.join(cikti, "harita.png"), en_az_derece=a["en_az_yukseklik"]))
        print(gorsel.takvim(liste, os.path.join(cikti, "takvim.png"), a["konum"]))

    elif arg.komut == "calis":
        print(f"Yer istasyonu çalışıyor: {a['konum']['ad']}, en az {a['en_az_yukseklik']}°")
        while True:
            liste = hepsi(a, 1, arg.cevrimdisi)
            if not liste:
                time.sleep(3600)
                continue
            g, u = liste[0]
            rc = kayit.bekle_ve_kaydet(g, u, a, kuru=arg.kuru)
            if arg.kuru:
                return
            print(f"  bitti (çıkış kodu {rc})")
            time.sleep(30)


if __name__ == "__main__":
    main()

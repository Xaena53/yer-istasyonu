"""Geçiş sırasında SatDump ile kayıt + çözüm (canlı işleme)."""
import datetime as dt
import os
import subprocess
import time


def klasor_adi(gecis, kok):
    t = gecis.aos.utc_datetime().astimezone()
    ad = gecis.uydu.replace(" ", "_").replace("/", "-")
    return os.path.join(kok, f"{t:%Y-%m-%d_%H%M}_{ad}")


def satdump_komutu(gecis, uydu_ayar, alici, kok, pay_sn=60):
    """Geçiş için `satdump live` komutu (liste). Süre: AOS-pay .. LOS+pay."""
    sure = int(gecis.sure_dk * 60 + 2 * pay_sn)
    return [
        alici.get("satdump", "satdump"), "live", uydu_ayar["pipeline"], klasor_adi(gecis, kok),
        "--source", alici.get("kaynak", "rtlsdr"),
        "--samplerate", str(alici.get("ornekleme", 1024000)),
        "--frequency", str(uydu_ayar["frekans_hz"]),
        "--gain", str(alici.get("kazanc", 38)),
        "--timeout", str(sure),
        *alici.get("ek", []),
    ]


def bekle_ve_kaydet(gecis, uydu_ayar, ayar, kuru=False, yazdir=print):
    """Geçişin başlamasına pay_sn kalana dek bekler, SatDump'ı çalıştırır."""
    pay = ayar.get("gecis_oncesi_sn", 60)
    komut = satdump_komutu(gecis, uydu_ayar, ayar["alici"], ayar["kayit_klasoru"], pay)
    baslangic = gecis.aos.utc_datetime() - dt.timedelta(seconds=pay)
    kalan = (baslangic - dt.datetime.now(dt.timezone.utc)).total_seconds()
    yazdir(f"{gecis.uydu}: {baslangic.astimezone():%d.%m %H:%M:%S} kayıt başlayacak "
           f"(en yüksek {gecis.en_yuksek:.0f}°, {gecis.sure_dk:.0f} dk)")
    if kuru:
        yazdir("  komut: " + " ".join(komut))
        return None
    if kalan > 0:
        time.sleep(kalan)
    os.makedirs(komut[3], exist_ok=True)
    with open(os.path.join(komut[3], "satdump.log"), "w", encoding="utf-8") as gunluk:
        return subprocess.run(komut, stdout=gunluk, stderr=subprocess.STDOUT).returncode

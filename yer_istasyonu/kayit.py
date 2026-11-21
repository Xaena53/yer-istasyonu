"""Geçiş sırasında SatDump ile kayıt + çözüm (canlı işleme)."""
import datetime as dt
import os
import shutil
import subprocess
import time

EK_SURE_SN = 120          # SatDump --timeout'a uymazsa bu kadar sonra durdurulur


def simdi():
    return dt.datetime.now(dt.timezone.utc)


def uyu(saniye):
    """Duvar saatine bakarak bekler: bilgisayar uykudan dönünce fazla uyumaz."""
    hedef = time.time() + max(0, saniye)
    while (kalan := hedef - time.time()) > 0:
        time.sleep(min(kalan, 30))


def klasor_adi(gecis, kok):
    t = gecis.aos.utc_datetime().astimezone()
    ad = gecis.uydu.replace(" ", "_").replace("/", "-")
    return os.path.join(kok, f"{t:%Y-%m-%d_%H%M}_{ad}")


def baslangic_zamani(gecis, pay_sn):
    return gecis.aos.utc_datetime() - dt.timedelta(seconds=pay_sn)


def bitis_zamani(gecis, pay_sn):
    return gecis.los.utc_datetime() + dt.timedelta(seconds=pay_sn)


def satdump_komutu(gecis, uydu_ayar, alici, kok, pay_sn=60, sure_sn=None):
    """Geçiş için `satdump live` komutu (liste). Süre: AOS-pay .. LOS+pay (geç başlanırsa sure_sn)."""
    sure = int(sure_sn if sure_sn is not None else gecis.sure_dk * 60 + 2 * pay_sn)
    return [
        alici.get("satdump", "satdump"), "live", uydu_ayar["pipeline"], klasor_adi(gecis, kok),
        "--source", alici.get("kaynak", "rtlsdr"),
        "--samplerate", str(alici.get("ornekleme", 1024000)),
        "--frequency", str(uydu_ayar["frekans_hz"]),
        "--gain", str(alici.get("kazanc", 38)),
        "--timeout", str(sure),
        *alici.get("ek", []),
    ]


def satdump_bul(alici):
    yol = alici.get("satdump", "satdump")
    return shutil.which(yol) or (yol if os.path.isfile(yol) else None)


def _gunluk_sonu(yol, n=8):
    try:
        with open(yol, encoding="utf-8", errors="replace") as f:
            return [s.rstrip() for s in f.readlines()[-n:]]
    except OSError:
        return []


def bekle_ve_kaydet(gecis, uydu_ayar, ayar, kuru=False, yazdir=print):
    """Geçişin başlamasına pay_sn kalana dek bekler, SatDump'ı çalıştırır.

    Dönüş: SatDump çıkış kodu; kayıt yapılamadıysa None. Hata atmaz, istasyon döngüsü sürer.
    """
    pay = ayar.get("gecis_oncesi_sn", 60)
    alici = ayar["alici"]
    baslangic, bitis = baslangic_zamani(gecis, pay), bitis_zamani(gecis, pay)
    yazdir(f"{gecis.uydu}: {baslangic.astimezone():%d.%m %H:%M:%S} kayıt başlayacak "
           f"(en yüksek {gecis.en_yuksek:.0f}°, {gecis.sure_dk:.0f} dk)")
    if kuru:
        yazdir("  komut: " + " ".join(satdump_komutu(gecis, uydu_ayar, alici, ayar["kayit_klasoru"], pay)))
        return None

    uyu((baslangic - simdi()).total_seconds())
    program = satdump_bul(alici)               # beklerken kurulmuş olabilir: kayıt anında bak
    if not program:
        yazdir(f"  SatDump bulunamadı ({alici.get('satdump', 'satdump')!r}); ayar.json → alici.satdump "
               f"tam yolu göstersin. Bu geçiş atlandı.")
        return None
    sure = int((bitis - simdi()).total_seconds())
    if sure < 60:                               # uyku/askı yüzünden geçiş kaçtıysa
        yazdir("  geçiş kaçırıldı (bilgisayar uykuda mıydı?)")
        return None
    komut = satdump_komutu(gecis, uydu_ayar, alici, ayar["kayit_klasoru"], pay, sure_sn=sure)
    komut[0] = program
    klasor = komut[3]
    os.makedirs(klasor, exist_ok=True)
    gunluk_yolu = os.path.join(klasor, "satdump.log")
    try:
        with open(gunluk_yolu, "w", encoding="utf-8") as gunluk:
            rc = subprocess.run(komut, stdout=gunluk, stderr=subprocess.STDOUT,
                                timeout=sure + EK_SURE_SN).returncode
    except subprocess.TimeoutExpired:
        yazdir(f"  SatDump {sure + EK_SURE_SN} sn'de kapanmadı, durduruldu")
        rc = -1
    except OSError as hata:
        yazdir(f"  SatDump çalıştırılamadı: {hata}")
        return None
    if rc != 0:
        yazdir(f"  SatDump hata koduyla bitti ({rc}); günlüğün sonu:")
        for s in _gunluk_sonu(gunluk_yolu):
            yazdir(f"    {s}")
    yazdir(f"  çıktı: {klasor}")
    return rc

"""Geçiş görselleri: gökyüzü (kutupsal), yer izi haritası, haftalık takvim."""
import datetime as dt
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

from .yorunge import KOK, pusula  # noqa: E402

TR = dt.timezone(dt.timedelta(hours=3))
KAGIT, MUREKKEP, SOLUK, CIZGI, VURGU = "#ecedef", "#17181a", "#6b6f76", "#cfd2d6", "#1d4ed8"
KARA, DENIZ = "#dfe1e4", "#ecedef"
plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 13, "text.color": MUREKKEP,
    "axes.edgecolor": CIZGI, "axes.labelcolor": SOLUK, "xtick.color": SOLUK, "ytick.color": SOLUK,
    "figure.facecolor": KAGIT, "axes.facecolor": KAGIT, "savefig.facecolor": KAGIT,
})


GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def yerel(t):
    return t.utc_datetime().astimezone(TR)


def gun_saat(t):
    return f"{GUNLER[t.weekday()]} {t:%H:%M}"


def gunes_yuksekligi(an, enlem, boylam):
    """Güneşin ufuktan yüksekliği (derece), NOAA yaklaşık formülü; birkaç dakikalık doğruluk."""
    u = an.astimezone(dt.timezone.utc)
    g = 2 * math.pi / 365 * (u.timetuple().tm_yday - 1 + (u.hour - 12) / 24)
    denklem = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                        - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    egim = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    dk = u.hour * 60 + u.minute + u.second / 60 + denklem + 4 * boylam
    saat_acisi = math.radians(dk / 4 - 180)
    e = math.radians(enlem)
    sin_y = math.sin(e) * math.sin(egim) + math.cos(e) * math.cos(egim) * math.cos(saat_acisi)
    return math.degrees(math.asin(max(-1, min(1, sin_y))))


def gorus_yaricapi_km(yukseklik_km, en_az_derece):
    """Uydunun en_az_derece'nin üstünde göründüğü alanın yer üstündeki yarıçapı."""
    R, e = 6371.0, math.radians(en_az_derece)
    return R * (math.acos(R * math.cos(e) / (R + yukseklik_km)) - e)


def _kaydet(fig, yol):
    os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
    fig.savefig(yol, dpi=200, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    return yol


def gokyuzu(gecis_listesi, konum, yol, en_iyi=None):
    """Kuzey yukarıda, tepe noktası merkezde; her çizgi bir geçiş."""
    fig = plt.figure(figsize=(8, 10.2))
    ax = fig.add_axes([0.1, 0.25, 0.8, 0.62], projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 90)
    ax.set_rticks([0, 30, 60, 90])
    ax.set_yticklabels(["", "60°", "30°", ""], fontsize=10, color=SOLUK)
    ax.set_rlabel_position(112)
    ax.set_xticks([math.radians(a) for a in range(0, 360, 45)])
    ax.set_xticklabels(["K", "KD", "D", "GD", "G", "GB", "B", "KB"], fontsize=14, fontweight="bold")
    ax.tick_params(axis="x", pad=30)
    ax.grid(color=CIZGI, linewidth=1)
    ax.spines["polar"].set_color(MUREKKEP)
    en_iyi = en_iyi or max(gecis_listesi, key=lambda g: g.en_yuksek)
    sira = sorted(gecis_listesi, key=lambda g: g.aos.tt)
    for g in sorted(gecis_listesi, key=lambda g: g is en_iyi):
        no = sira.index(g) + 1
        teta = [math.radians(p[2]) for p in g.iz]
        r = [90 - max(p[1], 0) for p in g.iz]
        vurgu = g is en_iyi
        ax.plot(teta, r, color=VURGU if vurgu else "#9aa0a8", linewidth=3.2 if vurgu else 1.6, solid_capstyle="round")
        ax.annotate("", xy=(teta[-1], r[-1]), xytext=(teta[-4], r[-4]),
                    arrowprops=dict(arrowstyle="-|>", color=VURGU if vurgu else "#9aa0a8", lw=0))
        ax.plot(teta[0], r[0], marker="o", markersize=17, color=VURGU if vurgu else "#7b818a", clip_on=False, zorder=5)
        ax.text(teta[0], r[0], str(no), fontsize=10, color="white", ha="center", va="center",
                fontweight="bold", zorder=6, clip_on=False)
    for i, g in enumerate(sira):
        vurgu = g is en_iyi
        x, y = 0.1 + (i % 2) * 0.42, 0.155 - (i // 2) * 0.04
        fig.text(x, y, f"{i + 1}", fontsize=12, fontweight="bold", color=VURGU if vurgu else SOLUK)
        fig.text(x + 0.03, y, f"{gun_saat(yerel(g.aos))}  ·  {g.en_yuksek:.0f}°  ·  {pusula(g.az_aos)} → {pusula(g.az_los)}",
                 fontsize=12, color=MUREKKEP if vurgu else SOLUK, fontweight="bold" if vurgu else "normal")
    fig.text(0.07, 0.965, f"{konum['ad']} gökyüzü · {en_iyi.uydu}", fontsize=19, fontweight="bold")
    fig.text(0.07, 0.94, f"Önümüzdeki {len(gecis_listesi)} iyi geçiş. Merkez tam tepe, dış çember ufuk; "
             f"numara, uydunun ufukta belirdiği yer.", fontsize=11.5, color=SOLUK)
    return _kaydet(fig, yol)


def _ulkeler():
    with open(os.path.join(KOK, "veri", "ulkeler.geojson"), encoding="utf-8") as f:
        d = json.load(f)
    for ozellik in d["features"]:
        geo = ozellik["geometry"]
        cokgenler = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        for c in cokgenler:
            yield ozellik["properties"].get("ADMIN"), c[0]


def _gorus_cemberi(enlem, boylam, yaricap_km, n=180):
    """Bir noktanın etrafındaki büyük daire çemberi (yaklaşık, küresel Dünya)."""
    R = 6371.0
    d = yaricap_km / R
    e1, b1 = math.radians(enlem), math.radians(boylam)
    noktalar = []
    for i in range(n + 1):
        y = 2 * math.pi * i / n
        e2 = math.asin(math.sin(e1) * math.cos(d) + math.cos(e1) * math.sin(d) * math.cos(y))
        b2 = b1 + math.atan2(math.sin(y) * math.sin(d) * math.cos(e1), math.cos(d) - math.sin(e1) * math.sin(e2))
        noktalar.append((math.degrees(b2), math.degrees(e2)))
    return noktalar


def harita(gecis_listesi, konum, yol, kutu=(10, 52, 22, 58), en_az_derece=25, uydu_km=830):
    """Geçişlerin yer izi: uydunun altındaki nokta, istasyonun görüş alanı."""
    b0, b1, e0, e1 = kutu
    olcek = 1 / math.cos(math.radians((e0 + e1) / 2))
    fig, ax = plt.subplots(figsize=(11, 11 * (e1 - e0) * olcek / (b1 - b0) * 0.98))
    ax.set_facecolor(DENIZ)
    cokgen, renk = [], []
    for ad, halka in _ulkeler():
        if any(b0 - 10 < x < b1 + 10 and e0 - 10 < y < e1 + 10 for x, y in halka[::5] or halka):
            cokgen.append(halka)
            renk.append("#cfd3d8" if ad == "Turkey" else KARA)
    ax.add_collection(PolyCollection(cokgen, facecolors=renk, edgecolors="#b9bdc3", linewidths=0.5))
    cember = _gorus_cemberi(konum["enlem"], konum["boylam"], gorus_yaricapi_km(uydu_km, en_az_derece))
    ax.plot(*zip(*cember), color=VURGU, linewidth=1, linestyle=(0, (4, 4)))
    en_iyi = max(gecis_listesi, key=lambda g: g.en_yuksek)
    for g in gecis_listesi:
        x = [p[4] for p in g.iz]
        y = [p[3] for p in g.iz]
        vurgu = g is en_iyi
        ax.plot(x, y, color=VURGU if vurgu else "#7b818a", linewidth=3 if vurgu else 1.4)
        ax.annotate("", xy=(x[-1], y[-1]), xytext=(x[-3], y[-3]),
                    arrowprops=dict(arrowstyle="-|>", color=VURGU if vurgu else "#7b818a", lw=0, mutation_scale=16))
        yakin = min(g.iz, key=lambda p: (p[3] - konum["enlem"]) ** 2 + ((p[4] - konum["boylam"]) / olcek) ** 2)
        ax.text(yakin[4] + 0.5, yakin[3] + 0.5, f"{gun_saat(yerel(g.tca))} · {g.en_yuksek:.0f}°", fontsize=10.5,
                bbox=dict(facecolor=KAGIT, edgecolor="none", pad=1.5, alpha=0.85),
                color=VURGU if vurgu else SOLUK, fontweight="bold" if vurgu else "normal")
    ax.plot(konum["boylam"], konum["enlem"], marker="o", markersize=9, color=MUREKKEP)
    ax.text(konum["boylam"] - 0.8, konum["enlem"] - 0.25, konum["ad"], fontsize=13, fontweight="bold", ha="right",
            bbox=dict(facecolor="#cfd3d8", edgecolor="none", pad=1.5))
    ax.set_xlim(b0, b1)
    ax.set_ylim(e0, e1)
    ax.set_aspect(olcek)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(MUREKKEP)
    ax.set_title(f"{gecis_listesi[0].uydu} · önümüzdeki 24 saatin geçişleri", loc="left", fontsize=17, fontweight="bold", pad=26)
    ax.text(0, 1.012, f"Çizgi: uydunun tam altındaki nokta. Kesikli çember: uydu bu alanın üstündeyken "
            f"Eskişehir'den {en_az_derece}°'den yüksekte görünür.",
            transform=ax.transAxes, fontsize=10.5, color=SOLUK)
    return _kaydet(fig, yol)


def takvim(gecis_listesi, yol, konum, gun_sayisi=7):
    """Günler × saat: her nokta bir geçiş, büyüklüğü en yüksek açı."""
    fig, ax = plt.subplots(figsize=(11, 5.6))
    bas = yerel(gecis_listesi[0].aos).replace(hour=0, minute=0, second=0, microsecond=0)
    for g in gecis_listesi:
        t = yerel(g.tca)
        gun = (t - bas).days
        if gun >= gun_sayisi:
            continue
        saat = t.hour + t.minute / 60
        iyi = g.en_yuksek >= 50
        ax.scatter(saat, gun, s=g.en_yuksek * 9, color=VURGU if iyi else "#9aa0a8", alpha=0.9 if iyi else 0.7,
                   edgecolors="none", zorder=3)
        ax.text(saat + 0.12 + (g.en_yuksek * 9) ** 0.5 / 40, gun, f"{g.en_yuksek:.0f}°", va="center",
                fontsize=10, color=VURGU if iyi else SOLUK, fontweight="bold" if iyi else "normal")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 3)])
    ax.set_ylim(gun_sayisi - 0.4, -0.6)
    gunler = [bas + dt.timedelta(days=i) for i in range(gun_sayisi)]
    ax.set_yticks(range(gun_sayisi))
    ax.set_yticklabels([f"{g:%d.%m} {GUNLER[g.weekday()]}" for g in gunler])
    ax.grid(axis="x", color=CIZGI)
    for i, gun0 in enumerate(gunler):                       # güneşin ufkun üstünde olduğu saatler
        dakikalar = [m for m in range(0, 1440, 5)
                     if gunes_yuksekligi(gun0 + dt.timedelta(minutes=m), konum["enlem"], konum["boylam"]) > -0.83]
        if dakikalar:
            ax.fill_betweenx([i - 0.45, i + 0.45], dakikalar[0] / 60, dakikalar[-1] / 60,
                             color="#f1dfb8", alpha=0.6, zorder=0, linewidth=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_title(f"{gecis_listesi[0].uydu} · 7 günlük geçiş takvimi (Türkiye saati)", loc="left",
                 fontsize=16, fontweight="bold", pad=22)
    ax.text(0, 1.015, "Mavi: 50°'nin üstü, en temiz görüntü. Sarı bant: Eskişehir'de gün doğumundan batımına (renkli görüntü gündüz çıkar).",
            transform=ax.transAxes, fontsize=10.5, color=SOLUK)
    return _kaydet(fig, yol)


def tablo_satiri(g):
    return (f"{yerel(g.aos):%d.%m} {gun_saat(yerel(g.aos))}  {g.sure_dk:4.1f} dk  en yüksek {g.en_yuksek:4.0f}°  "
            f"{pusula(g.az_aos):>3} → {pusula(g.az_los):<3}  ({g.yon})")

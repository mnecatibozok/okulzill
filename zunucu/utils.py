#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zil Sistemi — Ortak Yardımcı Fonksiyonlar"""

import os, re, socket, struct, time
from datetime import datetime

SES_UZANTILARI = ('.mp3', '.m4a', '.aac', '.ogg', '.wav', '.flac')


# ── Metin işleme ──────────────────────────────────────────

def parse_first6(html: str) -> dict | None:
    """HTML içinden ilk 6 sıralı saati ezan vakti olarak çıkarır."""
    all_times = re.findall(r'>(\d{2}:\d{2})<', html)
    seen = []
    for t in all_times:
        if t not in seen:
            seen.append(t)
        if len(seen) >= 6:
            break
    if len(seen) >= 6:
        nums = [int(v.replace(':', '')) for v in seen[:6]]
        if nums == sorted(nums):
            keys = ['imsak', 'gunes', 'ogle', 'ikindi', 'aksam', 'yatsi']
            return dict(zip(keys, seen[:6]))
    return None


def slugify_tr(s: str) -> str:
    """Türkçe karakterleri ASCII'ye dönüştürür, URL-güvenli slug üretir."""
    result = s.lower()
    for c_from, c_to in [
        ('\u0130', 'i'), ('\u015e', 's'), ('\u00c7', 'c'), ('\u00d6', 'o'),
        ('\u00dc', 'u'), ('\u011e', 'g'), ('\u0131', 'i'), ('\u015f', 's'),
        ('\u00e7', 'c'), ('\u00f6', 'o'), ('\u00fc', 'u'), ('\u011f', 'g'),
        (' ', '-'),
    ]:
        result = result.replace(c_from, c_to)
    return ''.join(ch for ch in result if ch in 'abcdefghijklmnopqrstuvwxyz0123456789-')


def ascii_upper_tr(s: str) -> str:
    """Türkçe karakterleri büyük ASCII karşılığına dönüştürür (sözlük anahtarı eşleştirme için)."""
    result = s.upper()
    for c_from, c_to in [
        ('\u0130', 'I'), ('\u015e', 'S'), ('\u00c7', 'C'), ('\u00d6', 'O'),
        ('\u00dc', 'U'), ('\u011e', 'G'), ('\u0131', 'I'), ('\u015f', 'S'),
        ('\u00e7', 'C'), ('\u00f6', 'O'), ('\u00fc', 'U'), ('\u011f', 'G'),
    ]:
        result = result.replace(c_from, c_to)
    return result


# ── NTP Saat Kontrolü ─────────────────────────────────────

def ntp_offset_saniye(sunucu: str = 'pool.ntp.org', zaman_asimi: int = 3) -> float | None:
    """
    NTP sunucusundan gerçek zamanı çeker, sistem saatiyle farkı saniye olarak döner.
    Pozitif değer: sistem saati ileri; negatif: sistem saati geri.
    Bağlantı yoksa veya hata olursa None döner.
    """
    try:
        # NTP paketi — 48 byte, LI=0 VN=3 Mode=3 (client)
        paket = bytearray(48)
        paket[0] = 0b00011011  # LI=0, VN=3, Mode=3
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(zaman_asimi)
            gonderim = time.time()
            s.sendto(bytes(paket), (sunucu, 123))
            yanit, _ = s.recvfrom(48)
        alim = time.time()
        if len(yanit) < 48:
            return None
        # NTP zaman damgası: saniye 40-43 (Transmit Timestamp)
        sn_ntp = struct.unpack('!I', yanit[40:44])[0]
        # NTP epoch: 1 Ocak 1900; Unix epoch: 1 Ocak 1970 → fark 70 yıl
        DELTA = 2208988800
        ntp_unix = sn_ntp - DELTA
        # Ağ gecikmesini yarıya böl
        gecikme = (alim - gonderim) / 2
        offset = (gonderim + gecikme) - ntp_unix
        return round(offset, 2)
    except Exception:
        return None


def find_free_port(start: int = 8765, end: int = 8800) -> int:
    """start–end aralığında boş TCP port bulur; bulamazsa OS'tan rastgele alır."""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', port))
                return port
        except OSError:
            continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 0))
        return s.getsockname()[1]


# ── Dosya manifestoları ───────────────────────────────────

def build_manifest(base_dir: str) -> list:
    """zilsesleri/ klasöründeki ses dosyalarının listesini döner."""
    manifest = []
    d = os.path.join(base_dir, 'zilsesleri')
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(SES_UZANTILARI):
                manifest.append({'file': f, 'path': f'zilsesleri/{f}'})
    return manifest


def build_mp3_manifest(base_dir: str) -> dict:
    """mp3/ alt-klasörlerindeki dosyaların klasör→dosya sözlüğünü döner."""
    result = {}
    d = os.path.join(base_dir, 'mp3')
    if not os.path.isdir(d):
        return result
    for folder in sorted(os.listdir(d)):
        fp = os.path.join(d, folder)
        if os.path.isdir(fp):
            files = [
                {'file': f, 'path': f'mp3/{folder}/{f}'}
                for f in sorted(os.listdir(fp))
                if f.lower().endswith(SES_UZANTILARI)
            ]
            if files:
                result[folder] = files
    return result

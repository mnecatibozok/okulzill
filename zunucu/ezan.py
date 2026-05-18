#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zil Sistemi — Ezan Vakitleri (Diyanet / Haberturk / NTV / Aladhan)"""

import json, ssl, urllib.request, urllib.parse, http.client
from datetime import datetime
from utils import parse_first6, slugify_tr, ascii_upper_tr

# İl merkez koordinatları — Aladhan API fallback için
_IL_COORDS: dict[str, tuple[float, float]] = {
    'ADANA': (37, 35.32), 'ADIYAMAN': (37.76, 38.28), 'AFYONKARAHISAR': (38.75, 30.54),
    'AGRI': (39.72, 43.05), 'AKSARAY': (38.37, 34.03), 'AMASYA': (40.65, 35.83),
    'ANKARA': (39.93, 32.86), 'ANTALYA': (36.88, 30.71), 'ARDAHAN': (41.11, 42.7),
    'ARTVIN': (41.18, 41.82), 'AYDIN': (37.85, 27.85), 'BALIKESIR': (39.65, 27.88),
    'BARTIN': (41.64, 32.34), 'BATMAN': (37.89, 41.13), 'BAYBURT': (40.26, 40.22),
    'BILECIK': (40.06, 30.02), 'BINGOL': (38.88, 40.49), 'BITLIS': (38.4, 42.11),
    'BOLU': (40.73, 31.61), 'BURDUR': (37.72, 30.29), 'BURSA': (40.19, 29.06),
    'CANAKKALE': (40.15, 26.41), 'CANKIRI': (40.6, 33.62), 'CORUM': (40.55, 34.96),
    'DENIZLI': (37.77, 29.09), 'DIYARBAKIR': (37.91, 40.24), 'DUZCE': (40.84, 31.16),
    'EDIRNE': (41.68, 26.55), 'ELAZIG': (38.68, 39.23), 'ERZINCAN': (39.75, 39.49),
    'ERZURUM': (39.9, 41.27), 'ESKISEHIR': (39.78, 30.52), 'GAZIANTEP': (37.07, 37.38),
    'GIRESUN': (40.91, 38.39), 'GUMUSHANE': (40.46, 39.48), 'HAKKARI': (37.58, 43.74),
    'HATAY': (36.4, 36.35), 'IGDIR': (39.92, 44.05), 'ISPARTA': (37.76, 30.55),
    'ISTANBUL': (41.01, 28.98), 'IZMIR': (38.42, 27.13),
    'KAHRAMANMARAS': (37.58, 36.94), 'KARABUK': (41.21, 32.63), 'KARAMAN': (37.18, 33.23),
    'KARS': (40.6, 43.1), 'KASTAMONU': (41.39, 33.78), 'KAYSERI': (38.73, 35.48),
    'KIRIKKALE': (39.85, 33.51), 'KIRKLARELI': (41.73, 27.23), 'KIRSEHIR': (39.15, 34.17),
    'KILIS': (36.72, 37.12), 'KOCAELI': (40.77, 29.92), 'KONYA': (37.87, 32.48),
    'KUTAHYA': (39.42, 29.98), 'MALATYA': (38.35, 38.32), 'MANISA': (38.61, 27.43),
    'MARDIN': (37.31, 40.73), 'MERSIN': (36.8, 34.63), 'MUGLA': (37.22, 28.36),
    'MUS': (38.75, 41.51), 'NEVSEHIR': (38.63, 34.71), 'NIGDE': (37.97, 34.68),
    'ORDU': (41, 37.88), 'OSMANIYE': (37.07, 36.25), 'RIZE': (41.02, 40.52),
    'SAKARYA': (40.69, 30.4), 'SAMSUN': (41.29, 36.33), 'SIIRT': (37.93, 41.94),
    'SINOP': (42.03, 35.15), 'SIVAS': (39.75, 37.01), 'SANLIURFA': (37.16, 38.8),
    'SIRNAK': (37.42, 42.46), 'TEKIRDAG': (41, 27.52), 'TOKAT': (40.31, 36.55),
    'TRABZON': (41, 39.72), 'TUNCELI': (39.11, 39.55), 'USAK': (38.67, 29.41),
    'VAN': (38.49, 43.38), 'YALOVA': (40.66, 29.27), 'YOZGAT': (39.82, 34.8),
    'ZONGULDAK': (41.45, 31.8),
}

_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def _today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def _ok(kaynak: str, vakitler: dict) -> dict:
    return {'ok': True, 'kaynak': kaynak, 'tarih': _today(), 'vakitler': vakitler}


def _fail(hata: str) -> dict:
    return {'ok': False, 'hata': hata}


# ── Kaynak 1: Diyanet ─────────────────────────────────────

def _diyanet_fetch(path: str, max_redirects: int = 5) -> tuple[int, str]:
    """Diyanet sitesine HTTPS isteği atar, yönlendirmeleri takip eder."""
    host = 'namazvakitleri.diyanet.gov.tr'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'tr-TR,tr;q=0.9',
        'Accept-Encoding': 'identity',
        'Host': host,
    }
    for _ in range(max_redirects):
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, timeout=15, context=ctx)
        conn.request('GET', path, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode('utf-8', errors='replace')
        conn.close()
        if resp.status in (301, 302, 303, 307, 308):
            location = resp.getheader('Location', '')
            if location.startswith('http'):
                p = urllib.parse.urlparse(location)
                host = p.netloc
                headers['Host'] = host
                path = p.path + ('?' + p.query if p.query else '')
            else:
                path = location
            continue
        return resp.status, body
    return 0, ''


def fetch_diyanet(ilce_kodu: str, il_adi: str = '') -> dict:
    """Diyanet → diyanethaber.com.tr → Aladhan API sırasıyla dener."""
    # Yöntem 1: Diyanet doğrudan
    try:
        status, html = _diyanet_fetch(f'/tr-TR/{ilce_kodu}')
        if status == 200 and len(html) > 1000:
            vakitler = parse_first6(html)
            if vakitler:
                print(f'[EZAN] Diyanet: {vakitler}')
                return _ok('Diyanet', vakitler)
        print(f'[EZAN] Diyanet status={status}, boyut={len(html) if html else 0}')
    except Exception as e:
        print(f'[EZAN] Diyanet hatası: {e}')

    # Yöntem 2: diyanethaber.com.tr
    il_slug = slugify_tr(il_adi)
    if il_slug:
        try:
            url = f'https://www.diyanethaber.com.tr/{il_slug}-namaz-vakitleri'
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
                html2 = r.read().decode('utf-8')
            vakitler2 = parse_first6(html2)
            if vakitler2:
                print(f'[EZAN] Diyanethaber: {vakitler2}')
                return _ok('Diyanet Haber', vakitler2)
        except Exception as e:
            print(f'[EZAN] diyanethaber hatası: {e}')

    # Yöntem 3: Aladhan API (son çare — yaklaşık konum)
    il_key = ascii_upper_tr(il_adi)
    lat, lng = _IL_COORDS.get(il_key, (40.80, 29.43))
    try:
        today_dm = datetime.now().strftime('%d-%m-%Y')
        url3 = (f'https://api.aladhan.com/v1/timings/{today_dm}'
                f'?latitude={lat}&longitude={lng}&method=13&school=1')
        req3 = urllib.request.Request(url3, headers={'User-Agent': 'ZilSistemi/2.0'})
        with urllib.request.urlopen(req3, timeout=10, context=ssl.create_default_context()) as r:
            data = json.loads(r.read().decode('utf-8'))
        t = data.get('data', {}).get('timings', {})
        if t:
            print('[EZAN] Aladhan fallback (yaklaşık)')
            return _ok('Aladhan API (yaklaşık)', {
                'imsak':  t.get('Imsak',   '')[:5],
                'gunes':  t.get('Sunrise', '')[:5],
                'ogle':   t.get('Dhuhr',   '')[:5],
                'ikindi': t.get('Asr',     '')[:5],
                'aksam':  t.get('Maghrib', '')[:5],
                'yatsi':  t.get('Isha',    '')[:5],
            })
    except Exception as e:
        print(f'[EZAN] Aladhan hatası: {e}')

    return _fail('Tüm kaynaklar başarısız')


# ── Kaynak 2: Haberturk ───────────────────────────────────

def fetch_haberturk(il_adi: str = '') -> dict:
    """Haberturk'ten ezan vakitlerini çeker."""
    il_slug = slugify_tr(il_adi)
    if not il_slug:
        return _fail('İl adı boş')
    try:
        url = f'https://www.haberturk.com/namaz-vakitleri/{il_slug}'
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
            html = r.read().decode('utf-8', errors='replace')
        vakitler = parse_first6(html)
        if vakitler:
            print(f'[EZAN] Haberturk: {vakitler}')
            return _ok('Haberturk', vakitler)
    except Exception as e:
        print(f'[EZAN] Haberturk hatası: {e}')
    return _fail('Haberturk başarısız')


# ── Kaynak 3: NTV ─────────────────────────────────────────

def fetch_ntv(il_adi: str = '') -> dict:
    """NTV'den ezan vakitlerini çeker."""
    il_slug = slugify_tr(il_adi)
    if not il_slug:
        return _fail('İl adı boş')
    try:
        url = f'https://www.ntv.com.tr/namaz-vakitleri/{il_slug}'
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
            html = r.read().decode('utf-8', errors='replace')
        vakitler = parse_first6(html)
        if vakitler:
            print(f'[EZAN] NTV: {vakitler}')
            return _ok('NTV', vakitler)
    except Exception as e:
        print(f'[EZAN] NTV hatası: {e}')
    return _fail('NTV başarısız')


# ── Dışa açık seçici ─────────────────────────────────────

def vakit_cek(ilce_kodu: str, il_adi: str = '', kaynak: str = '') -> dict:
    """Kaynak parametresine göre doğru fetch fonksiyonunu çağırır."""
    if kaynak == 'haberturk':
        return fetch_haberturk(il_adi)
    if kaynak == 'ntv':
        return fetch_ntv(il_adi)
    return fetch_diyanet(ilce_kodu, il_adi)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zil Sistemi — Ana Sunucu v2"""

import os, sys, socket, socketserver

# ── Klasör içinden import ────────────────────────────────
# Bu dosya sunucu/ klasöründe. Modüller (utils, ezan, handler)
# aynı klasörde olduğu için sys.path'e ekliyoruz.
_SUNUCU_DIR = os.path.dirname(os.path.abspath(__file__))
if _SUNUCU_DIR not in sys.path:
    sys.path.insert(0, _SUNUCU_DIR)

# ── Kök dizine geç ───────────────────────────────────────
# HTTP sunucusu kök dizinden serve eder:
# HTML, zilsesleri/, mp3/, zil-port.txt hepsi kök dizinde.
_KOK_DIR = os.path.dirname(_SUNUCU_DIR)
os.chdir(_KOK_DIR)

from utils    import find_free_port, build_manifest, build_mp3_manifest
from handler  import ZilHandler

HTML_FILE = 'zil-programi-v1.html'
PORT_FILE = 'zil-port.txt'


def _find_html_file(base_dir: str) -> str | None:
    """HTML dosyasını bulur — tam isim veya 'zil-program' ile başlayan .html."""
    if os.path.exists(os.path.join(base_dir, HTML_FILE)):
        return HTML_FILE
    for f in os.listdir(base_dir):
        fl = f.lower()
        if fl.endswith('.html') and ('zil-program' in fl or 'zil_program' in fl):
            print(f"[ZIL] '{HTML_FILE}' bulunamadı, '{f}' kullanılıyor.")
            return f
    return None


def _yazdir_manifest(manifest: list, mp3_manifest: dict) -> None:
    print(f'[ZIL] zilsesleri/ : {len(manifest)} ses dosyası')
    for item in manifest:
        print(f"[ZIL]   + {item['file']}")
    if not manifest:
        print('[ZIL]   (klasör boş veya yok — zilsesleri/ oluşturun)')
    for folder, files in mp3_manifest.items():
        print(f'[ZIL] mp3/{folder}/ : {len(files)} müzik')


def _yazdir_ag_adresleri(port: int, html_file: str) -> None:
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        print(f'[ZIL] Ağ     : http://{local_ip}:{port}/{html_file}')
        print(f'[ZIL] Kumanda: http://{local_ip}:{port}/kumanda')
    except Exception:
        pass


def main() -> None:
    global HTML_FILE

    print(f'[ZIL] Kök dizin : {_KOK_DIR}')
    print(f'[ZIL] Modüller  : {_SUNUCU_DIR}')

    # HTML dosyasını bul
    html = _find_html_file(_KOK_DIR)
    if not html:
        print(f'[HATA] HTML dosyası bulunamadı! Aranan: {HTML_FILE}')
        print(f'[HATA] Dizin içeriği: {[f for f in os.listdir(_KOK_DIR) if f.endswith(".html")]}')
        input("Devam etmek için Enter'a basın...")
        sys.exit(1)
    HTML_FILE = html
    print(f'[ZIL] Dosya    : {HTML_FILE}')

    # Manifest
    manifest     = build_manifest(_KOK_DIR)
    mp3_manifest = build_mp3_manifest(_KOK_DIR)
    _yazdir_manifest(manifest, mp3_manifest)

    # Port
    port = find_free_port()
    print(f'[ZIL] Port     : {port}')
    try:
        with open(os.path.join(_KOK_DIR, PORT_FILE), 'w') as pf:
            pf.write(str(port))
    except Exception as e:
        print(f'[UYARI] Port dosyası yazılamadı: {e}')

    # Sunucu
    try:
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        with socketserver.ThreadingTCPServer(('0.0.0.0', port), ZilHandler) as httpd:
            print(f'[ZIL] Hazır    : http://localhost:{port}/{HTML_FILE}')
            _yazdir_ag_adresleri(port, HTML_FILE)
            print('[ZIL] Kapatmak için bu pencereyi kapatın veya Ctrl+C')
            httpd.serve_forever()
    except Exception as e:
        print(f'[HATA] Sunucu başlatılamadı: {e}')
        input("Devam etmek için Enter'a basın...")


if __name__ == '__main__':
    main()

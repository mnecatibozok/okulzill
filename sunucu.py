#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zil Sistemi — Yerel HTTP Sunucusu v3 (zil-programi-v9 için)"""

import http.server, socketserver, os, sys, json, socket, urllib.parse

HTML_FILE = "zil-programi-v9.html"
SES_UZANTILARI = ('.mp3', '.m4a', '.aac', '.ogg', '.wav', '.flac')
PORT_FILE = "zil-port.txt"

def find_free_port():
    for port in range(8765, 8800):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def build_manifest(base_dir):
    """zilsesleri/ klasöründeki ses dosyalarını listeler."""
    manifest = []
    d = os.path.join(base_dir, 'zilsesleri')
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(SES_UZANTILARI):
                manifest.append({'file': f, 'path': 'zilsesleri/' + f})
    return manifest

def build_mp3_manifest(base_dir):
    """mp3/ klasörü altındaki alt klasörleri ve parçaları listeler."""
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

class ZilHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # favicon isteklerini ve başarılı yanıtları sessizce geç
        if hasattr(self, 'path') and 'favicon' in self.path:
            return
        if args and len(args) >= 2 and str(args[1]) not in ('200', '304', '206'):
            print(f"[ZIL] {self.path} -> {args[1]}")

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if path == '/ses-manifest.json':
            self._serve_json(build_manifest(os.getcwd()))
            return
        if path == '/mp3-manifest.json':
            self._serve_json(build_mp3_manifest(os.getcwd()))
            return
        if path == '/api/minimize':
            self._serve_json({'ok': True})
            # Minimize: platforma özgü — Windows'ta ctypes ile
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
            except Exception:
                pass
            return
        super().do_GET()

    def do_POST(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if path == '/api/shutdown':
            self._serve_json({'ok': True, 'msg': 'Sunucu kapatılıyor...'})
            print('[ZIL] Kapatma isteği alındı — sunucu durduruluyor.')
            # Kısa gecikmeyle sunucuyu kapat (yanıtın ulaşması için)
            import threading
            threading.Timer(0.5, self.server.shutdown).start()
            return
        self.send_response(404)
        self.end_headers()

    def _serve_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # Tüm yanıtlara CORS ve byte-range desteği ekle
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

def main():
    sd = os.path.dirname(os.path.abspath(sys.argv[0]))
    os.chdir(sd)
    print(f"[ZIL] Dizin  : {sd}")
    print(f"[ZIL] Dosya  : {HTML_FILE}")

    if not os.path.exists(HTML_FILE):
        print(f"[HATA] {HTML_FILE} bulunamadi!")
        input("Devam etmek icin Enter'a basin...")
        sys.exit(1)

    m  = build_manifest(sd)
    mp = build_mp3_manifest(sd)

    print(f"[ZIL] zilsesleri/ : {len(m)} ses dosyasi")
    if m:
        for item in m:
            print(f"[ZIL]   + {item['file']}")
    else:
        print(f"[ZIL]   (klasor bos veya yok — zilsesleri/ olusturun)")

    for folder, files in mp.items():
        print(f"[ZIL] mp3/{folder}/  : {len(files)} muzik")

    port = find_free_port()
    print(f"[ZIL] Port   : {port}")

    try:
        with open(os.path.join(sd, PORT_FILE), 'w') as pf:
            pf.write(str(port))
    except Exception as e:
        print(f"[UYARI] Port dosyasi yazilamadi: {e}")

    try:
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("127.0.0.1", port), ZilHandler) as httpd:
            print(f"[ZIL] Hazir  : http://localhost:{port}/{HTML_FILE}")
            print(f"[ZIL] Kapatmak icin bu pencereyi kapatin veya Ctrl+C")
            httpd.serve_forever()
    except Exception as e:
        print(f"[HATA] Sunucu baslatılamadi: {e}")
        input("Devam etmek icin Enter'a basin...")

if __name__ == "__main__":
    main()

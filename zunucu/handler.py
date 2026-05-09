#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zil Sistemi — HTTP Handler (GET / POST route'ları)"""

import http.server, json, os, shutil, subprocess, threading, time, urllib.parse

from utils     import build_manifest, build_mp3_manifest, ntp_offset_saniye
from ezan      import vakit_cek
from zilsesler import load_anons_ayar, save_anons_ayar

# Kumanda komutu — process içi bellek (poll mekanizması)
_kumanda_cmd  : str   = ''
_kumanda_ts   : float = 0.0
_kumanda_lock : threading.Lock = threading.Lock()

# Kumanda HTML sayfası (inline — ek dosya gerektirmez)
_KUMANDA_HTML = """\
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Zil Kumanda</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: sans-serif; background: #0e1117; color: #fff;
      min-height: 100vh; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 16px; padding: 20px;
    }
    h1 { font-size: 1.2rem; opacity: .7; }
    .btn {
      width: 220px; padding: 20px; border-radius: 16px; border: none;
      font-size: 1.3rem; font-weight: 800; cursor: pointer;
      transition: transform .15s, box-shadow .15s; text-align: center;
    }
    .btn:active { transform: scale(.95); }
    .mars   { background: linear-gradient(135deg,#dc2626,#991b1b); color:#fff; box-shadow: 0 4px 20px rgba(220,38,38,.4); }
    .saygi  { background: linear-gradient(135deg,#7c3aed,#5b21b6); color:#fff; box-shadow: 0 4px 20px rgba(124,58,237,.4); }
    .zil    { background: linear-gradient(135deg,#16a34a,#15803d); color:#fff; box-shadow: 0 4px 20px rgba(22,163,74,.4); }
    .dur    { background: linear-gradient(135deg,#374151,#1f2937); color:#ef4444; border: 2px solid #ef4444; box-shadow: 0 4px 20px rgba(239,68,68,.3); }
    .status { font-size: .8rem; color: #888; text-align: center; }
  </style>
</head>
<body>
  <h1>🔔 Zil Kumanda</h1>
  <button class="btn mars"  onclick="cmd('mars')">🎖 İstiklâl Marşı</button>
  <button class="btn saygi" onclick="cmd('saygi')">🤲 Saygı Duruşu 1dk</button>
  <button class="btn saygi" onclick="cmd('saygi2dk')" style="opacity:.85">🤲 Saygı Duruşu 2dk</button>
  <button class="btn zil"   onclick="cmd('zil')">🔔 Zil Çal</button>
  <button class="btn dur"   onclick="cmd('stop')">⏹ DURDUR</button>
  <div class="status" id="st">Bağlı</div>
  <script>
    async function cmd(key) {
      const st = document.getElementById('st');
      try {
        st.textContent = 'Gönderiliyor...';
        const r = await fetch('/api/kumanda', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cmd: key }),
        });
        const d = await r.json();
        st.textContent = d.ok ? '✅ ' + d.msg : '❌ ' + d.hata;
      } catch (e) {
        st.textContent = '❌ Bağlantı hatası';
      }
      setTimeout(() => { st.textContent = 'Bağlı'; }, 3000);
    }
  </script>
</body>
</html>
"""


class ZilHandler(http.server.SimpleHTTPRequestHandler):

    # ── Loglama ──────────────────────────────────────────

    def log_message(self, fmt, *args):
        if hasattr(self, 'path') and 'favicon' in self.path:
            return
        if args and len(args) >= 2 and str(args[1]) not in ('200', '304', '206'):
            print(f'[ZIL] {self.path} → {args[1]}')

    # ── GET ───────────────────────────────────────────────

    def do_GET(self):
        path   = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        parsed = urllib.parse.urlparse(self.path)

        if path == '/ses-manifest.json':
            return self._serve_json(build_manifest(os.getcwd()))

        if path == '/mp3-manifest.json':
            return self._serve_json(build_mp3_manifest(os.getcwd()))

        if path == '/api/ezan-vakitleri':
            return self._get_ezan(parsed)

        if path == '/api/kumanda-poll':
            return self._get_kumanda_poll()

        if path == '/api/blacklist':
            return self._get_blacklist()

        if path == '/api/ntp-kontrol':
            return self._get_ntp_kontrol()

        if path == '/api/anons-ayar':
            return self._serve_json(load_anons_ayar())

        if path in ('/kumanda', '/kumanda.html'):
            return self._serve_html(_KUMANDA_HTML)

        super().do_GET()

    def _get_ntp_kontrol(self):
        offset = ntp_offset_saniye()
        if offset is None:
            self._serve_json({'ok': False, 'hata': 'NTP sunucusuna ulaşılamadı'})
            return
        uyari = abs(offset) >= 30
        self._serve_json({
            'ok'    : True,
            'offset': offset,
            'uyari' : uyari,
            'mesaj' : f'Sistem saati NTP\'den {offset:+.1f}sn {"ileri" if offset > 0 else "geri"}' if uyari
                      else f'Sistem saati doğru (±{abs(offset):.1f}sn)',
        })

    def _get_ezan(self, parsed):
        qs     = urllib.parse.parse_qs(parsed.query)
        ilce   = qs.get('ilce',   ['9541'])[0]
        il     = qs.get('il',     [''])[0]
        kaynak = qs.get('kaynak', [''])[0]
        print(f'[EZAN] Vakit isteği — il: {il}, ilce: {ilce}, kaynak: {kaynak}')
        self._serve_json(vakit_cek(ilce, il, kaynak))

    def _get_kumanda_poll(self):
        global _kumanda_cmd, _kumanda_ts
        cmd = ''
        with _kumanda_lock:
            if _kumanda_cmd and (time.time() - _kumanda_ts) < 5:
                cmd = _kumanda_cmd
                _kumanda_cmd = ''
        self._serve_json({'cmd': cmd})

    def _get_blacklist(self):
        self._serve_json({'ok': True, 'blacklist': _load_blacklist()})

    # ── POST ──────────────────────────────────────────────

    def do_POST(self):
        path = self.path.split('?')[0]
        print(f'[API] POST → {path}')

        length = int(self.headers.get('Content-Length', 0))
        raw    = self.rfile.read(length) if length else b'{}'
        try:
            body = json.loads(raw.decode('utf-8'))
        except Exception:
            body = {}

        if '/api/move-to-temp' in path:
            return self._post_move_to_temp(body)

        if '/api/restore-from-temp' in path:
            return self._post_restore_from_temp(body)

        if '/api/blacklist' in path:
            return self._post_blacklist(body)

        if '/api/kumanda' in path and '/kumanda-poll' not in path:
            return self._post_kumanda(body)

        if path == '/api/anons-ayar':
            return self._post_anons_ayar(body)

        if '/api/exit' in path:
            return self._post_exit()

        if '/api/shutdown' in path:
            return self._post_shutdown()

        print(f'[API] 404: {path}')
        self._serve_json({'ok': False, 'hata': f'Bilinmeyen endpoint: {path}'})

    def _post_move_to_temp(self, body):
        filepath = body.get('path', '')
        print(f'[MOVE] path: "{filepath}"')
        if not filepath:
            return self._serve_json({'ok': False, 'hata': 'path boş'})

        cwd  = os.path.realpath(os.getcwd())
        full = os.path.realpath(os.path.join(cwd, filepath))

        if not full.startswith(cwd + os.sep):
            print(f'[MOVE] GÜVENLİK: izin verilmeyen yol: {full}')
            return self._serve_json({'ok': False, 'hata': 'Geçersiz yol'})

        print(f'[MOVE] tam yol: "{full}"  — var: {os.path.exists(full)}')

        if not os.path.isfile(full):
            return self._serve_json({'ok': False, 'hata': f'Dosya bulunamadı: {filepath}'})

        temp_dir = os.path.join(cwd, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        fname = os.path.basename(full)
        dest  = os.path.join(temp_dir, fname)
        if os.path.exists(dest):
            base, ext = os.path.splitext(fname)
            n = 1
            while os.path.exists(os.path.join(temp_dir, f'{base}_{n}{ext}')):
                n += 1
            dest = os.path.join(temp_dir, f'{base}_{n}{ext}')

        try:
            shutil.move(full, dest)
            with open(dest + '.origin', 'w', encoding='utf-8') as f:
                f.write(filepath)
            msg = f'{fname} → temp/ taşındı'
            print(f'[MOVE] OK: {msg}')
            self._serve_json({'ok': True, 'msg': msg})
        except Exception as e:
            print(f'[MOVE] HATA: {e}')
            self._serve_json({'ok': False, 'hata': str(e)})

    def _post_restore_from_temp(self, body):
        name = body.get('name', '')
        if not name:
            return self._serve_json({'ok': False, 'hata': 'name boş'})

        cwd      = os.path.realpath(os.getcwd())
        temp_dir = os.path.join(cwd, 'temp')
        src      = None

        if os.path.isdir(temp_dir):
            for f in os.listdir(temp_dir):
                if f.startswith(name) or os.path.splitext(f)[0] == name:
                    src = os.path.join(temp_dir, f)
                    break

        if not src or not os.path.isfile(src):
            return self._serve_json({'ok': False, 'hata': 'temp/ içinde bulunamadı'})

        origin_file   = src + '.origin'
        original_path = None
        if os.path.isfile(origin_file):
            with open(origin_file, 'r', encoding='utf-8') as f:
                original_path = f.read().strip()

        if original_path:
            dest_full = os.path.realpath(os.path.join(cwd, original_path))
            if not dest_full.startswith(cwd + os.sep):
                print(f'[RESTORE] GÜVENLİK: izin verilmeyen hedef: {dest_full}')
                return self._serve_json({'ok': False, 'hata': 'Geçersiz hedef yol'})
            dest_dir  = os.path.dirname(dest_full)
        else:
            dest_dir  = os.path.join(cwd, 'mp3')
            dest_full = os.path.join(dest_dir, os.path.basename(src))

        os.makedirs(dest_dir, exist_ok=True)
        try:
            shutil.move(src, dest_full)
            if os.path.isfile(origin_file):
                os.remove(origin_file)
            self._serve_json({'ok': True, 'msg': f'{name} geri alındı → {os.path.relpath(dest_full, cwd)}'})
        except Exception as e:
            self._serve_json({'ok': False, 'hata': str(e)})

    def _post_blacklist(self, body):
        bl     = _load_blacklist()
        action = body.get('action', 'list')
        name   = body.get('name', '')
        if action == 'add' and name and name not in bl:
            bl.append(name)
        elif action == 'remove' and name:
            bl = [x for x in bl if x != name]
        if action in ('add', 'remove'):
            _save_blacklist(bl)
        self._serve_json({'ok': True, 'blacklist': bl})

    def _post_kumanda(self, body):
        global _kumanda_cmd, _kumanda_ts
        cmd = body.get('cmd', '')
        with _kumanda_lock:
            _kumanda_cmd = cmd
            _kumanda_ts  = time.time()
        print(f'[KUMANDA] {cmd}')
        self._serve_json({'ok': True, 'msg': f'{cmd} komutu alındı', 'cmd': cmd})

    def _post_anons_ayar(self, body):
        try:
            data = save_anons_ayar(body)
            print(f'[ZIL] Anons ayarları kaydedildi: {data}')
            self._serve_json({'ok': True, 'ayar': data})
        except Exception as e:
            self._serve_json({'ok': False, 'hata': str(e)})

    def _post_exit(self):
        self._serve_json({'ok': True, 'msg': 'Sunucu kapatılıyor...'})
        print('[ZIL] Çıkış isteği — sunucu kapatılıyor.')
        def _exit():
            try:
                subprocess.run(
                    ['wmic', 'process', 'where',
                     "commandline like '%ZilSistemi%'",
                     'call', 'terminate'],
                    capture_output=True, timeout=3
                )
            except Exception:
                pass
            self.server.shutdown()
            os._exit(0)
        threading.Timer(0.3, _exit).start()

    def _post_shutdown(self):
        self._serve_json({'ok': True, 'msg': 'Sistem kapatılıyor...'})
        print('[ZIL] Kapatma isteği — sistem kapatılıyor.')
        def _shutdown():
            self.server.shutdown()
            try:
                subprocess.run(
                    ['shutdown', '/s', '/t', '10', '/f', '/c', 'Zil Sistemi otomatik kapatma'],
                    check=False,
                )
            except Exception as e:
                print(f'[HATA] Shutdown: {e}')
        threading.Timer(0.5, _shutdown).start()

    # ── Yanıt yardımcıları ────────────────────────────────

    def _serve_json(self, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type',   'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self, html: str):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type',   'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── CORS ─────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Accept-Ranges',  'bytes')
        self.send_header('Cache-Control',  'no-cache')
        super().end_headers()


# ── Blacklist yardımcıları ────────────────────────────────

def _blacklist_path() -> str:
    return os.path.join(os.getcwd(), 'blacklist.json')

def _load_blacklist() -> list:
    p = _blacklist_path()
    if os.path.exists(p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return json.loads(f.read())
        except Exception:
            pass
    return []

def _save_blacklist(bl: list) -> None:
    with open(_blacklist_path(), 'w', encoding='utf-8') as f:
        f.write(json.dumps(bl, ensure_ascii=False))

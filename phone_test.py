"""같은 와이파이의 안드로이드에서 카메라를 테스트하는 로컬 HTTPS 실행기."""
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
TLS = ROOT / '.local' / 'phone_tls'
APP_PORT = 8502
SETUP_PORT = 8503


def local_ip():
    result = subprocess.run(['/usr/sbin/ipconfig', 'getifaddr', 'en0'], capture_output=True, text=True)
    address = result.stdout.strip()
    if result.returncode or not address:
        raise RuntimeError('와이파이 연결과 en0 주소를 확인해주세요.')
    return address


def prepare_certificate(address):
    openssl = shutil.which('openssl')
    if not openssl:
        raise RuntimeError('OpenSSL을 찾지 못했습니다.')
    TLS.mkdir(parents=True, exist_ok=True)
    TLS.chmod(0o700)

    def run(*args):
        subprocess.run([openssl, *args], cwd=TLS, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ca = TLS / 'root.pem'
    ca_key = TLS / 'root.key'
    valid = ca.exists() and ca_key.exists() and subprocess.run(
        [openssl, 'x509', '-in', str(ca), '-noout', '-checkend', '86400'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    old_mask = os.umask(0o077)
    try:
        if not valid:
            run('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '7',
                '-keyout', 'root.key', '-out', 'root.pem', '-subj', '/CN=Chorok Local Phone Test CA',
                '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
        # IP가 바뀌어도 루트 인증서는 그대로 사용하고 서버 인증서만 갱신합니다.
        run('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-sha256',
            '-keyout', 'server.key', '-out', 'server.csr', '-subj', '/CN=Chorok Phone Test')
        (TLS / 'server.ext').write_text(
            'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n'
            'extendedKeyUsage=serverAuth\n'
            f'subjectAltName=IP:{address},IP:127.0.0.1,DNS:localhost\n')
        run('x509', '-req', '-in', 'server.csr', '-CA', 'root.pem', '-CAkey', 'root.key',
            '-set_serial', '0x'+secrets.token_hex(16), '-days', '6', '-sha256',
            '-extfile', 'server.ext', '-out', 'server.pem')
        (TLS / 'server-chain.pem').write_bytes((TLS / 'server.pem').read_bytes() + ca.read_bytes())
        run('x509', '-in', 'root.pem', '-outform', 'DER', '-out', 'eco-phone-ca.crt')
        run('verify', '-CAfile', 'root.pem', '-verify_ip', address, 'server.pem')
    finally:
        os.umask(old_mask)
    return TLS / 'server-chain.pem', TLS / 'server.key'


def setup_handler(address):
    class Setup(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split('?', 1)[0]
            if path == '/eco-phone-ca.crt':
                data = (TLS / 'eco-phone-ca.crt').read_bytes()
                content_type = 'application/x-x509-ca-cert'
                filename = 'eco-phone-ca.crt'
            elif path == '/':
                data = f'''<!doctype html><html lang="ko"><meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1">
                <title>초록선택 · 폰 연결</title>
                <style>body{{max-width:520px;margin:48px auto;padding:0 24px;font-family:sans-serif;line-height:1.8;color:#263b2c;background:#f5f8f0}}
                a{{display:block;padding:14px;margin:18px 0;background:#386e43;color:white;border-radius:12px;text-decoration:none;text-align:center}}</style>
                <h1>초록선택</h1><p>같은 와이파이에서 카메라 테스트</p>
                <h3>1. 테스트 인증서 받기</h3><a href="/eco-phone-ca.crt">인증서 다운로드</a>
                <h3>2. 안드로이드에 설치</h3>
                <p>설정에서 ‘인증서 설치’를 검색한 뒤 <b>CA 인증서</b>를 선택하고,
                다운로드한 <b>eco-phone-ca.crt</b>를 설치하세요. 인증서 이름은 <b>Chorok Local Phone Test CA</b>입니다.</p>
                <p>이 컴퓨터의 테스트 사이트를 신뢰하는 설정입니다. 테스트가 끝나면 사용자 인증서에서 삭제하세요.
                휴대폰 보안 설정은 직접 확인하고 진행해주세요.</p>
                <h3>3. 서비스 열기</h3><a href="https://{escape(address)}:{APP_PORT}">초록선택 열기</a>
                <p>로그인 후 촬영 시작을 누르고 카메라 권한을 허용하세요.
                인증서 오류가 계속 표시되면 진행하지 말고 설치 상태를 확인하세요.</p></html>'''.encode()
                content_type, filename = 'text/html; charset=utf-8', None
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass
    return Setup


def main():
    address = local_ip()
    with socket.create_connection(('127.0.0.1', 8000), timeout=3):
        pass
    cert, key = prepare_certificate(address)
    setup = ThreadingHTTPServer((address, SETUP_PORT), setup_handler(address))
    threading.Thread(target=setup.serve_forever, daemon=True).start()
    process = None
    try:
        process = subprocess.Popen([
            sys.executable, '-m', 'streamlit', 'run', str(ROOT / 'streamlit_app.py'),
            '--server.address', address, '--server.port', str(APP_PORT),
            '--server.sslCertFile', str(cert), '--server.sslKeyFile', str(key),
            '--browser.serverAddress', address, '--browser.serverPort', str(APP_PORT),
            '--server.headless', 'true', '--browser.gatherUsageStats', 'false',
        ], cwd=ROOT)
        print(f'폰 설정: http://{address}:{SETUP_PORT}', flush=True)
        print(f'폰 접속: https://{address}:{APP_PORT}', flush=True)
        print('종료: Ctrl+C · FastAPI는 127.0.0.1:8000 유지', flush=True)
        while process.poll() is None:
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        setup.shutdown()
        setup.server_close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'폰 테스트 서버를 시작하지 못했습니다: {error}', file=sys.stderr)
        sys.exit(1)

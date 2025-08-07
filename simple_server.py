#!/usr/bin/env python3
"""
Simple HTTP server test for firewall diagnosis
"""
import http.server
import socketserver
import webbrowser
import sys

def test_server(port=8080):
    """Test simple HTTP server"""
    try:
        print(f'[TEST] 간단한 테스트 서버 시작 - 포트 {port}')
        
        class MyHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    html = """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Trading System Test</title>
                        <meta charset="utf-8">
                    </head>
                    <body>
                        <h1>🎉 연결 성공!</h1>
                        <p>방화벽 테스트가 성공했습니다.</p>
                        <p>포트 {port}가 정상적으로 열려있습니다.</p>
                        <h2>거래 시스템 상태</h2>
                        <ul>
                            <li>✅ 네트워크 연결: 정상</li>
                            <li>✅ 포트 {port}: 열림</li>
                            <li>✅ HTTP 서버: 작동중</li>
                        </ul>
                    </body>
                    </html>
                    """.format(port=port)
                    self.wfile.write(html.encode('utf-8'))
                else:
                    super().do_GET()
        
        with socketserver.TCPServer(("127.0.0.1", port), MyHandler) as httpd:
            print(f'[OK] 서버 실행중: http://127.0.0.1:{port}')
            print(f'[OK] 서버 실행중: http://localhost:{port}')
            print('\n브라우저에서 위 주소로 접속해보세요.')
            print('Ctrl+C로 서버를 종료할 수 있습니다.')
            
            # 자동으로 브라우저 열기 시도
            try:
                webbrowser.open(f'http://127.0.0.1:{port}')
            except:
                pass
                
            httpd.serve_forever()
            
    except OSError as e:
        if "Address already in use" in str(e):
            print(f'[ERROR] 포트 {port}가 이미 사용중입니다.')
            return test_server(port + 1)  # 다음 포트 시도
        else:
            print(f'[ERROR] 서버 시작 실패: {e}')
    except KeyboardInterrupt:
        print('\n[EXIT] 서버 종료')
    except Exception as e:
        print(f'[ERROR] 예상치 못한 오류: {e}')

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    test_server(port)
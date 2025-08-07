#!/usr/bin/env python3
"""
로컬 서버 연결 테스트
"""
import socket
import requests
import time

def test_port_connection(host='127.0.0.1', port=8000):
    """포트 연결 테스트"""
    print(f"[TEST] {host}:{port} 포트 연결 테스트...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            print(f"[OK] 포트 {port} 열려있음")
            return True
        else:
            print(f"[FAIL] 포트 {port} 닫혀있음")
            return False
    except Exception as e:
        print(f"[ERROR] 포트 테스트 실패: {e}")
        return False

def test_http_request(url='http://127.0.0.1:8000'):
    """HTTP 요청 테스트"""
    print(f"[TEST] {url} HTTP 요청 테스트...")
    try:
        response = requests.get(url, timeout=5)
        print(f"[OK] HTTP 응답 코드: {response.status_code}")
        print(f"[OK] 응답 내용 길이: {len(response.text)} bytes")
        print(f"[PREVIEW] 응답 내용: {response.text[:200]}...")
        return True
    except requests.exceptions.ConnectionError:
        print("[FAIL] 연결 거부됨 (Connection refused)")
        return False
    except requests.exceptions.Timeout:
        print("[FAIL] 연결 시간 초과")
        return False
    except Exception as e:
        print(f"[ERROR] HTTP 요청 실패: {e}")
        return False

if __name__ == "__main__":
    print("=== 서버 연결 진단 테스트 ===")
    
    # 1. 포트 연결 테스트
    port_ok = test_port_connection()
    
    # 2. HTTP 요청 테스트
    if port_ok:
        http_ok = test_http_request()
        if http_ok:
            print("\n[SUCCESS] 서버가 정상적으로 작동하고 있습니다!")
            print("브라우저에서 http://127.0.0.1:8000 접속 가능해야 합니다.")
        else:
            print("\n[PROBLEM] 포트는 열려있지만 HTTP 응답이 없습니다.")
    else:
        print("\n[PROBLEM] 서버가 실행되지 않았거나 포트가 차단되어 있습니다.")
    
    print("\n=== 진단 완료 ===")
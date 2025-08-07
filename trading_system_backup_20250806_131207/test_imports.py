#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test import for all required libraries
Windows Unicode compatibility version
"""

import sys
import os

# Windows Unicode 지원 설정
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def test_imports():
    try:
        print("Testing library imports...")
        
        import asyncio
        print("[OK] asyncio")
        
        import ccxt
        print("[OK] ccxt")
        
        import fastapi
        print("[OK] fastapi")
        
        import uvicorn
        print("[OK] uvicorn")
        
        import openai
        print("[OK] openai")
        
        import pandas
        print("[OK] pandas")
        
        import numpy
        print("[OK] numpy")
        
        import websockets
        print("[OK] websockets")
        
        import aiohttp
        print("[OK] aiohttp")
        
        from dotenv import load_dotenv
        print("[OK] python-dotenv")
        
        import cachetools
        print("[OK] cachetools")
        
        import feedparser
        print("[OK] feedparser")
        
        print("\n[SUCCESS] 모든 라이브러리가 정상적으로 설치되었습니다!")
        return True
        
    except ImportError as e:
        print(f"\n[ERROR] 라이브러리 import 실패: {e}")
        print("다음 명령어로 수동 설치하세요:")
        print("pip install ccxt fastapi uvicorn openai pandas numpy websockets aiohttp python-dotenv cachetools feedparser")
        return False
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    test_imports()
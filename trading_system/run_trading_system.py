#!/usr/bin/env python3
"""
Bitget Trading System v3.0 - 실행 스크립트
완전 모듈화된 고급 거래 시스템
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from main_trading_system import TradingSystemOrchestrator


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Bitget Trading System v3.0 - 완전 모듈화 버전",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python run_trading_system.py                    # 기본 설정으로 실행
  python run_trading_system.py --config custom.py # 커스텀 설정으로 실행
  python run_trading_system.py --status           # 시스템 상태만 확인
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='설정 파일 경로 (기본: config/config.py)'
    )
    
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='시스템 상태 확인 후 종료'
    )
    
    parser.add_argument(
        '--test-mode', '-t',
        action='store_true',
        help='테스트 모드 (실제 거래 없음)'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='로그 레벨 설정'
    )
    
    return parser.parse_args()


def print_banner():
    """Print system banner"""
    banner = """
================================================================
                                                              
           Bitget Trading System v3.0                     
                                                              
               완전 모듈화된 고급 거래 시스템                    
                                                              
  * 멀티 타임프레임 분석                                        
  * 머신러닝 기반 예측                                          
  * 실시간 뉴스 감성 분석                                       
  * 고급 리스크 관리                                           
  * Kelly Criterion 포지션 사이징                             
  * 실시간 웹 대시보드                                          
                                                              
================================================================
    """
    print(banner)


def check_dependencies():
    """Check if all required dependencies are available"""
    required_modules = [
        'asyncio', 'pandas', 'numpy', 'ccxt', 'fastapi', 
        'aiohttp', 'cachetools', 'logging'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"[ERROR] 다음 모듈이 누락되었습니다: {', '.join(missing_modules)}")
        print("다음 명령으로 설치하세요:")
        print(f"pip install {' '.join(missing_modules)}")
        return False
    
    return True


async def status_check():
    """Quick status check"""
    print("[INFO] 시스템 상태 확인 중...")
    
    try:
        system = TradingSystemOrchestrator()
        await system.initialize()
        
        status = system.get_system_status()
        
        print("\n" + "="*60)
        print("[INFO] 시스템 상태 보고서")
        print("="*60)
        print(f"상태: {status.get('status', 'Unknown')}")
        print(f"가동 시간: {status.get('uptime_formatted', 'N/A')}")
        print(f"거래소 연결: {'OK' if status.get('exchange_connected') else 'FAIL'}")
        print(f"ML 모델: {'OK' if status.get('ml_enabled') else 'DISABLED'}")
        print(f"전체 건강도: {status.get('health_status', 'Unknown')}")
        print(f"활성 포지션: {status.get('active_positions', 0)}개")
        print(f"일일 거래: {status.get('daily_trades', 0)}회")
        print("="*60)
        
        await system.shutdown()
        
    except Exception as e:
        print(f"[ERROR] 상태 확인 실패: {e}")


async def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Print banner
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Set log level
    import logging
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Status check only
    if args.status:
        await status_check()
        return
    
    # Print startup info
    print("[INFO] 시스템 설정:")
    print(f"   설정 파일: {args.config or '기본 설정'}")
    print(f"   테스트 모드: {'ON' if args.test_mode else 'OFF'}")
    print(f"   로그 레벨: {args.log_level}")
    print()
    
    # Create and run trading system
    try:
        system = TradingSystemOrchestrator(args.config)
        
        # Apply test mode if specified
        if args.test_mode:
            system.config.ENABLE_LIVE_TRADING = False
            print("[WARNING] 테스트 모드: 실제 거래가 비활성화됩니다")
        
        print("[INFO] 시스템 시작 중...")
        print("   웹 대시보드: http://localhost:8000")
        print("   중단하려면 Ctrl+C를 누르세요")
        print()
        
        await system.run()
        
    except KeyboardInterrupt:
        print("\n[INFO] 사용자에 의해 시스템이 중단되었습니다")
    except Exception as e:
        print(f"\n[ERROR] 시스템 실행 중 오류 발생: {e}")
        sys.exit(1)
    finally:
        print("[INFO] 시스템 종료 완료")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] 시스템 종료")
    except Exception as e:
        print(f"\n[CRITICAL] 치명적 오류: {e}")
        sys.exit(1)
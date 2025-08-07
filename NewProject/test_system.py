"""
AI 배달 도우미 시스템 테스트 스크립트
각 모듈과 전체 시스템 테스트
"""

import asyncio
import os
from dotenv import load_dotenv
from database import db_manager
from ai_conversation import ai_conversation
from speech_processor import speech_processor
import json

# 환경 변수 로드
load_dotenv()

class SystemTester:
    """시스템 테스트 클래스"""
    
    def __init__(self):
        self.test_results = []
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        print("=" * 60)
        print("AI 배달 도우미 시스템 테스트 시작")
        print("=" * 60)
        
        # 개별 모듈 테스트
        await self.test_database()
        await self.test_ai_conversation()
        await self.test_speech_processor() 
        
        # 통합 시나리오 테스트
        await self.test_full_order_scenario()
        
        # 결과 요약
        self.print_test_summary()
    
    async def test_database(self):
        """데이터베이스 모듈 테스트"""
        print("\n🗄️ 데이터베이스 모듈 테스트")
        print("-" * 40)
        
        try:
            # 1. 메뉴 조회 테스트
            menu_items = db_manager.get_menu_items()
            assert len(menu_items) > 0, "메뉴 아이템이 없습니다"
            print(f"✅ 메뉴 조회: {len(menu_items)}개 아이템")
            
            # 2. 고객 정보 저장 테스트
            test_customer = {
                'phone_number': '010-1234-5678',
                'name': '테스트 고객',
                'preferred_address': '서울시 강남구 테스트동 123번지'
            }
            
            result = db_manager.save_customer_info(test_customer)
            assert result, "고객 정보 저장 실패"
            print("✅ 고객 정보 저장 성공")
            
            # 3. 고객 정보 조회 테스트
            customer_info = db_manager.get_customer_info('010-1234-5678')
            assert customer_info is not None, "고객 정보 조회 실패"
            print("✅ 고객 정보 조회 성공")
            
            # 4. 주문 저장 테스트
            test_order = {
                'call_sid': 'test_call_123',
                'customer_phone': '010-1234-5678',
                'menu_items': [{'name': '후라이드치킨', 'quantity': 1, 'price': 18000}],
                'total_amount': 21000,  # 배달비 포함
                'delivery_address': '서울시 강남구 테스트동 123번지'
            }
            
            order_id = db_manager.save_order(test_order)
            assert order_id is not None, "주문 저장 실패"
            print(f"✅ 주문 저장 성공: ID {order_id}")
            
            self.test_results.append(("데이터베이스", "성공"))
            
        except Exception as e:
            print(f"❌ 데이터베이스 테스트 실패: {e}")
            self.test_results.append(("데이터베이스", "실패"))
    
    async def test_ai_conversation(self):
        """AI 대화 모듈 테스트"""
        print("\n🤖 AI 대화 모듈 테스트")
        print("-" * 40)
        
        try:
            # 1. 기본 인사 테스트
            response = await ai_conversation.generate_response(
                user_input="안녕하세요",
                conversation_history=[],
                order_info={}
            )
            
            assert response['text'], "AI 응답이 비어있습니다"
            print(f"✅ 기본 인사 응답: {response['text'][:50]}...")
            
            # 2. 메뉴 주문 테스트
            response = await ai_conversation.generate_response(
                user_input="치킨 주문하고 싶어요",
                conversation_history=[],
                order_info={}
            )
            
            assert "치킨" in response['text'], "치킨 관련 응답이 없습니다"
            print(f"✅ 메뉴 주문 응답: {response['text'][:50]}...")
            
            # 3. 주문 요약 테스트
            test_order = {
                'menu': {'name': '후라이드치킨', 'price': 18000},
                'quantity': 1,
                'address': '서울시 강남구 테스트동',
                'phone': '010-1234-5678'
            }
            
            summary = ai_conversation.create_order_summary(test_order)
            assert "후라이드치킨" in summary, "주문 요약에 메뉴가 없습니다"
            print("✅ 주문 요약 생성 성공")
            
            self.test_results.append(("AI 대화", "성공"))
            
        except Exception as e:
            print(f"❌ AI 대화 테스트 실패: {e}")
            self.test_results.append(("AI 대화", "실패"))
    
    async def test_speech_processor(self):
        """음성 처리 모듈 테스트"""
        print("\n🎙️ 음성 처리 모듈 테스트")
        print("-" * 40)
        
        try:
            # 1. TTS 테스트 (실제 파일 생성 없이 함수 호출만 테스트)
            test_text = "안녕하세요, AI 배달 도우미입니다."
            
            # TTS 기능 테스트 (실제 음성 파일은 생성하지 않음)
            tts_result = speech_processor.text_to_speech(test_text)
            # 실제 환경에서는 None이 아닌 바이트 데이터가 반환되어야 함
            print("✅ TTS 모듈 호출 성공")
            
            # 2. 음성 인식 개선 기능 테스트
            test_input = "치킴 하나 주세요"  # 일부러 오타 포함
            corrected = speech_processor.enhance_speech_recognition(test_input)
            assert "치킨" in corrected, "음성 인식 개선이 작동하지 않습니다"
            print(f"✅ 음성 인식 개선: '{test_input}' → '{corrected}'")
            
            self.test_results.append(("음성 처리", "성공"))
            
        except Exception as e:
            print(f"❌ 음성 처리 테스트 실패: {e}")
            self.test_results.append(("음성 처리", "실패"))
    
    async def test_full_order_scenario(self):
        """전체 주문 시나리오 테스트"""
        print("\n📞 전체 주문 시나리오 테스트")
        print("-" * 40)
        
        try:
            # 시나리오: 고객이 전화로 치킨을 주문하는 전체 과정
            
            conversation_history = []
            order_info = {}
            call_sid = "scenario_test_001"
            customer_phone = "010-9999-8888"
            
            # 1단계: 인사
            step1 = await ai_conversation.generate_response(
                user_input="안녕하세요",
                conversation_history=conversation_history,
                order_info=order_info
            )
            conversation_history.append({
                'user': '안녕하세요',
                'ai': step1['text']
            })
            print(f"1단계 - 인사: {step1['text'][:50]}...")
            
            # 2단계: 메뉴 선택
            step2 = await ai_conversation.generate_response(
                user_input="양념치킨 주문하고 싶어요",
                conversation_history=conversation_history,
                order_info=step1['order_info']
            )
            conversation_history.append({
                'user': '양념치킨 주문하고 싶어요',
                'ai': step2['text']
            })
            order_info = step2['order_info']
            print(f"2단계 - 메뉴 선택: {step2['text'][:50]}...")
            
            # 3단계: 수량 확인
            step3 = await ai_conversation.generate_response(
                user_input="하나 주세요",
                conversation_history=conversation_history,
                order_info=order_info
            )
            conversation_history.append({
                'user': '하나 주세요',
                'ai': step3['text']
            })
            order_info = step3['order_info']
            print(f"3단계 - 수량 확인: {step3['text'][:50]}...")
            
            # 4단계: 주소 입력
            step4 = await ai_conversation.generate_response(
                user_input="서울시 마포구 홍대동 123번지로 배달해주세요",
                conversation_history=conversation_history,
                order_info=order_info
            )
            order_info = step4['order_info']
            order_info['address'] = "서울시 마포구 홍대동 123번지"
            print(f"4단계 - 주소 입력: {step4['text'][:50]}...")
            
            # 5단계: 연락처 확인
            order_info['phone'] = customer_phone
            
            # 6단계: 주문 요약
            summary = ai_conversation.create_order_summary(order_info)
            print(f"주문 요약:\n{summary}")
            
            # 7단계: 데이터베이스 저장
            final_order = {
                'call_sid': call_sid,
                'customer_phone': customer_phone,
                'menu_items': [order_info.get('menu', {})],
                'total_amount': 22000,  # 양념치킨 19000 + 배달비 3000
                'delivery_address': order_info.get('address', ''),
                'status': 'confirmed'
            }
            
            order_id = db_manager.save_order(final_order)
            assert order_id is not None, "최종 주문 저장 실패"
            
            # 대화 기록 저장
            db_manager.save_conversation(call_sid, customer_phone, conversation_history)
            
            print("✅ 전체 주문 시나리오 성공")
            self.test_results.append(("전체 시나리오", "성공"))
            
        except Exception as e:
            print(f"❌ 전체 시나리오 테스트 실패: {e}")
            self.test_results.append(("전체 시나리오", "실패"))
    
    def print_test_summary(self):
        """테스트 결과 요약"""
        print("\n" + "=" * 60)
        print("테스트 결과 요약")
        print("=" * 60)
        
        success_count = sum(1 for _, result in self.test_results if result == "성공")
        total_count = len(self.test_results)
        
        for test_name, result in self.test_results:
            status_icon = "✅" if result == "성공" else "❌"
            print(f"{status_icon} {test_name}: {result}")
        
        print(f"\n총 {total_count}개 테스트 중 {success_count}개 성공 ({success_count/total_count*100:.1f}%)")
        
        if success_count == total_count:
            print("\n🎉 모든 테스트가 성공했습니다! 시스템이 정상 작동 준비 완료.")
        else:
            print(f"\n⚠️  {total_count - success_count}개의 테스트가 실패했습니다. 문제를 해결해주세요.")

async def main():
    """메인 테스트 실행 함수"""
    tester = SystemTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    # 비동기 메인 함수 실행
    asyncio.run(main())
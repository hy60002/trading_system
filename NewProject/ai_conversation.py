"""
AI 대화 처리 모듈
OpenAI GPT-4를 사용한 자연스러운 배달 주문 대화
"""

import openai
import os
from typing import Dict, List, Optional
from loguru import logger
import json
from datetime import datetime

class AIConversationHandler:
    """AI 대화 처리 클래스"""
    
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.system_prompt = self._create_system_prompt()
        logger.info("AI 대화 핸들러 초기화 완료")
    
    def _create_system_prompt(self) -> str:
        """AI 시스템 프롬프트 생성"""
        return """
당신은 친근하고 도움이 되는 AI 배달 주문 도우미입니다.

역할과 특성:
- 중장년층, 노년층 고객을 주로 상대합니다
- 말투는 존댓말을 사용하고, 친근하고 따뜻합니다
- 천천히, 명확하게 설명합니다
- 복잡한 용어는 사용하지 않습니다
- 고객이 이해할 때까지 반복 설명합니다

주문 처리 과정:
1. 인사 및 주문 의도 파악
2. 메뉴 선택 도움
3. 수량 확인
4. 배달 주소 확인
5. 연락처 확인
6. 주문 내역 최종 확인
7. 배달 시간 안내

응답 규칙:
- 한 번에 하나씩만 질문하세요
- 고객의 답변을 정확히 이해했는지 재확인하세요
- 주문 정보는 반드시 JSON 형태로 정리하세요
- 실수하거나 잘못 이해했을 때는 정중히 사과하고 다시 물어보세요

사용 가능한 메뉴:
- 치킨: 후라이드(18,000원), 양념(19,000원), 간장(20,000원)
- 피자: 페퍼로니(25,000원), 불고기(27,000원), 치즈(23,000원)
- 중식: 짜장면(7,000원), 짬뽕(8,000원), 탕수육(20,000원)
- 한식: 김치찌개(9,000원), 된장찌개(8,000원), 제육볶음(12,000원)

배달비: 3,000원 (30,000원 이상 주문 시 무료)
"""
    
    async def generate_response(
        self, 
        user_input: str, 
        conversation_history: List[Dict], 
        order_info: Dict
    ) -> Dict:
        """
        사용자 입력에 대한 AI 응답 생성
        
        Args:
            user_input: 사용자 입력 텍스트
            conversation_history: 이전 대화 기록
            order_info: 현재 주문 정보
            
        Returns:
            AI 응답 정보 (텍스트, 다음 단계, 업데이트된 주문 정보 등)
        """
        try:
            logger.info(f"AI 응답 생성 시작: {user_input}")
            
            # 대화 컨텍스트 구성
            messages = self._build_conversation_context(
                user_input, conversation_history, order_info
            )
            
            # GPT-4 API 호출
            response = await self._call_gpt4(messages)
            
            # 응답 분석 및 구조화
            structured_response = self._parse_response(response, order_info)
            
            logger.info(f"AI 응답 생성 완료: {structured_response['text'][:50]}...")
            return structured_response
            
        except Exception as e:
            logger.error(f"AI 응답 생성 오류: {e}")
            return self._create_error_response()
    
    def _build_conversation_context(
        self, 
        user_input: str, 
        history: List[Dict], 
        order_info: Dict
    ) -> List[Dict]:
        """대화 컨텍스트 구성"""
        
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # 현재 주문 상태 추가
        if order_info:
            order_status = f"현재 주문 상태: {json.dumps(order_info, ensure_ascii=False)}"
            messages.append({"role": "system", "content": order_status})
        
        # 이전 대화 기록 추가 (최근 5개만)
        for entry in history[-5:]:
            messages.append({"role": "user", "content": entry.get('user', '')})
            messages.append({"role": "assistant", "content": entry.get('ai', '')})
        
        # 현재 사용자 입력
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    async def _call_gpt4(self, messages: List[Dict]) -> str:
        """GPT-4 API 호출"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,  # 자연스러운 응답을 위해
                max_tokens=200,   # 응답 길이 제한
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"GPT-4 API 호출 오류: {e}")
            raise
    
    def _parse_response(self, ai_response: str, current_order: Dict) -> Dict:
        """AI 응답 분석 및 구조화"""
        
        # 주문 정보 추출 및 업데이트
        updated_order = self._extract_order_info(ai_response, current_order)
        
        # 대화 단계 판단
        next_step = self._determine_conversation_step(ai_response, updated_order)
        
        # 응답 구조화
        return {
            'text': ai_response.strip(),
            'order_info': updated_order,
            'next_step': next_step,
            'timestamp': datetime.now().isoformat(),
            'requires_input': self._requires_user_input(ai_response)
        }
    
    def _extract_order_info(self, ai_response: str, current_order: Dict) -> Dict:
        """AI 응답에서 주문 정보 추출"""
        updated_order = current_order.copy()
        
        # 메뉴 추출
        menu_keywords = {
            '후라이드': {'type': 'chicken', 'name': '후라이드치킨', 'price': 18000},
            '양념': {'type': 'chicken', 'name': '양념치킨', 'price': 19000},
            '간장': {'type': 'chicken', 'name': '간장치킨', 'price': 20000},
            '페퍼로니': {'type': 'pizza', 'name': '페퍼로니피자', 'price': 25000},
            '불고기': {'type': 'pizza', 'name': '불고기피자', 'price': 27000},
            '치즈': {'type': 'pizza', 'name': '치즈피자', 'price': 23000},
            '짜장면': {'type': 'chinese', 'name': '짜장면', 'price': 7000},
            '짬뽕': {'type': 'chinese', 'name': '짬뽕', 'price': 8000},
            '탕수육': {'type': 'chinese', 'name': '탕수육', 'price': 20000},
        }
        
        response_lower = ai_response.lower()
        
        for keyword, menu_info in menu_keywords.items():
            if keyword in response_lower or keyword in current_order.get('user_last_input', ''):
                updated_order['menu'] = menu_info
                break
        
        # 수량 추출
        quantity_keywords = {
            '한': 1, '하나': 1, '1': 1,
            '두': 2, '둘': 2, '2': 2,
            '세': 3, '셋': 3, '3': 3,
        }
        
        for keyword, qty in quantity_keywords.items():
            if keyword in response_lower:
                updated_order['quantity'] = qty
                break
        
        return updated_order
    
    def _determine_conversation_step(self, ai_response: str, order_info: Dict) -> str:
        """대화 단계 판단"""
        response_lower = ai_response.lower()
        
        if not order_info.get('menu'):
            return 'menu_selection'
        elif not order_info.get('quantity'):
            return 'quantity_selection'
        elif not order_info.get('address'):
            if '주소' in response_lower or '배달' in response_lower:
                return 'address_input'
        elif not order_info.get('phone'):
            if '전화' in response_lower or '연락처' in response_lower:
                return 'phone_input'
        elif '확인' in response_lower or '맞' in response_lower:
            return 'order_confirmation'
        else:
            return 'general_conversation'
    
    def _requires_user_input(self, ai_response: str) -> bool:
        """사용자 입력이 필요한지 판단"""
        question_indicators = ['?', '어떤', '어디', '몇', '언제', '말씀해', '알려주']
        return any(indicator in ai_response for indicator in question_indicators)
    
    def _create_error_response(self) -> Dict:
        """오류 응답 생성"""
        return {
            'text': '죄송합니다. 잠시 기술적인 문제가 있었습니다. 다시 말씀해주시겠어요?',
            'order_info': {},
            'next_step': 'error_recovery',
            'timestamp': datetime.now().isoformat(),
            'requires_input': True
        }
    
    def create_order_summary(self, order_info: Dict) -> str:
        """주문 요약 생성"""
        if not order_info.get('menu'):
            return "아직 주문 정보가 없습니다."
        
        menu = order_info['menu']
        quantity = order_info.get('quantity', 1)
        total_price = menu['price'] * quantity
        
        delivery_fee = 3000 if total_price < 30000 else 0
        final_total = total_price + delivery_fee
        
        summary = f"""
주문 내역을 확인해드릴게요.

메뉴: {menu['name']} {quantity}개
가격: {total_price:,}원
배달비: {delivery_fee:,}원
총 금액: {final_total:,}원

배달 주소: {order_info.get('address', '확인 중')}
연락처: {order_info.get('phone', '확인 중')}

이대로 주문하시겠어요?
"""
        return summary.strip()

# 전역 인스턴스
ai_conversation = AIConversationHandler()
"""
Telegram Safe Message Formatter
텔레그램 메시지 안전 포맷팅 유틸리티
"""

import re
import logging
from typing import Any, Dict, Optional


class TelegramSafeFormatter:
    """텔레그램 메시지 안전 포맷팅 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # MarkdownV2에서 escape해야 할 특수문자들
        self.markdown_v2_chars = r'_*[]()~`>#+-=|{}.!'
        
        # HTML에서 escape해야 할 특수문자들
        self.html_chars = {'<': '&lt;', '>': '&gt;', '&': '&amp;'}
    
    def escape_markdown_v2(self, text: str) -> str:
        """
        MarkdownV2용 특수문자 escape 처리
        
        Args:
            text: 원본 텍스트
            
        Returns:
            escape 처리된 텍스트
        """
        if not isinstance(text, str):
            text = str(text)
        
        try:
            # 각 특수문자 앞에 백슬래시 추가
            for char in self.markdown_v2_chars:
                text = text.replace(char, f'\\{char}')
            
            return text
            
        except Exception as e:
            self.logger.error(f"MarkdownV2 escape 실패: {e}")
            return str(text)  # 실패 시 원본 반환
    
    def escape_html(self, text: str) -> str:
        """
        HTML용 특수문자 escape 처리
        
        Args:
            text: 원본 텍스트
            
        Returns:
            escape 처리된 텍스트
        """
        if not isinstance(text, str):
            text = str(text)
        
        try:
            for char, escaped in self.html_chars.items():
                text = text.replace(char, escaped)
            
            return text
            
        except Exception as e:
            self.logger.error(f"HTML escape 실패: {e}")
            return str(text)
    
    def safe_format_trading_message(self, template: str, data: Dict[str, Any], 
                                  parse_mode: str = 'HTML') -> str:
        """
        거래 메시지 안전 포맷팅
        
        Args:
            template: 메시지 템플릿
            data: 포맷팅할 데이터
            parse_mode: 파싱 모드 ('HTML' 또는 'MarkdownV2')
            
        Returns:
            안전하게 포맷팅된 메시지
        """
        try:
            # 데이터 안전 처리
            safe_data = {}
            for key, value in data.items():
                if value is None:
                    safe_value = "N/A"
                elif isinstance(value, float):
                    if key in ['price', 'amount', 'profit', 'loss']:
                        safe_value = f"{value:.8f}".rstrip('0').rstrip('.')
                    elif key in ['percentage', 'confidence']:
                        safe_value = f"{value:.2f}%"
                    else:
                        safe_value = f"{value:.4f}"
                elif isinstance(value, (int, bool)):
                    safe_value = str(value)
                else:
                    safe_value = str(value)
                
                # parse_mode에 따른 escape 처리
                if parse_mode == 'MarkdownV2':
                    safe_data[key] = self.escape_markdown_v2(safe_value)
                elif parse_mode == 'HTML':
                    safe_data[key] = self.escape_html(safe_value)
                else:
                    safe_data[key] = safe_value
            
            # 템플릿 포맷팅
            formatted_message = template.format(**safe_data)
            
            # 메시지 길이 제한 (텔레그램 4096자 제한)
            if len(formatted_message) > 4000:
                formatted_message = formatted_message[:3900] + "\\n\\n\\[메시지 잘림\\]"
            
            return formatted_message
            
        except KeyError as e:
            error_msg = f"템플릿 키 오류: {e}"
            self.logger.error(error_msg)
            return f"메시지 포맷팅 오류: {error_msg}"
            
        except Exception as e:
            error_msg = f"메시지 포맷팅 실패: {e}"
            self.logger.error(error_msg)
            return "메시지 전송 오류가 발생했습니다."
    
    def create_safe_trading_alert(self, symbol: str, action: str, price: float, 
                                confidence: float, reason: str = "") -> str:
        """
        안전한 거래 알림 메시지 생성
        
        Args:
            symbol: 거래 심볼
            action: 거래 액션 (BUY/SELL)
            price: 가격
            confidence: 신뢰도
            reason: 거래 이유
            
        Returns:
            안전하게 포맷팅된 알림 메시지
        """
        template = """
🚨 <b>거래 신호</b>

📊 심볼: <code>{symbol}</code>
🔄 액션: <b>{action}</b>
💰 가격: <code>{price}</code>
📈 신뢰도: <b>{confidence}</b>

{reason_section}

⏰ 시간: {timestamp}
        """.strip()
        
        data = {
            'symbol': symbol,
            'action': action,
            'price': price,
            'confidence': confidence,
            'reason_section': f"💡 이유: {reason}" if reason else "",
            'timestamp': self._get_current_time()
        }
        
        return self.safe_format_trading_message(template, data, 'HTML')
    
    def create_safe_error_message(self, component: str, error_msg: str, 
                                severity: str = "WARNING") -> str:
        """
        안전한 오류 메시지 생성
        
        Args:
            component: 오류 발생 컴포넌트
            error_msg: 오류 메시지
            severity: 심각도
            
        Returns:
            안전하게 포맷팅된 오류 메시지
        """
        severity_emoji = {
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '🚨'
        }
        
        template = """
{emoji} <b>{severity}</b>

🔧 구성요소: <code>{component}</code>
📝 오류: <pre>{error_msg}</pre>

⏰ 시간: {timestamp}
        """.strip()
        
        data = {
            'emoji': severity_emoji.get(severity, '❓'),
            'severity': severity,
            'component': component,
            'error_msg': error_msg[:500],  # 오류 메시지 길이 제한
            'timestamp': self._get_current_time()
        }
        
        return self.safe_format_trading_message(template, data, 'HTML')
    
    def _get_current_time(self) -> str:
        """현재 시간 문자열 반환"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 전역 인스턴스
telegram_formatter = TelegramSafeFormatter()
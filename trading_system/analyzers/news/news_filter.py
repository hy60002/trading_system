"""
News Filter Module
뉴스 필터링 및 신뢰도 평가 전담 모듈
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple

# Import handling for both direct and package imports
try:
    from ...config.config import TradingConfig
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config.config import TradingConfig


class NewsFilter:
    """뉴스 필터링 및 신뢰도 평가 전담 클래스"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 긴급 키워드와 심각도 가중치 (사용자 히스토리에서 과민반응 문제 해결)
        self.emergency_keywords = {
            # Critical (2.5) - 실제 긴급상황만 (기존 3.0에서 낮춤)
            'hack': 2.5, 'exploit': 2.5, 'bankruptcy': 2.5, 'fraud': 2.5,
            'scam': 2.5, 'theft': 2.5, 'attack': 2.5,
            '해킹': 2.5, '파산': 2.5, '사기': 2.5,
            
            # High (1.5) - 중요하지만 과민반응 방지 (기존 2.0에서 낮춤)
            'investigation': 1.5, 'lawsuit': 1.5, 'ban': 1.5, 'default': 1.5,
            'collapse': 1.5, '규제': 1.5, '수사': 1.5,
            
            # Medium (0.8) - 일반적인 시장 이벤트 (기존 1.0에서 낮춤)  
            'crash': 0.8, 'urgent': 0.8, 'breaking': 0.8, 'emergency': 0.8,
            '폭락': 0.8, '긴급': 0.8,
            
            # Low (0.3) - 과민반응 방지를 위해 새로 추가
            'drop': 0.3, 'fall': 0.3, 'decline': 0.3, 'pullback': 0.3,
            'correction': 0.3, '하락': 0.3, '조정': 0.3
        }
        
        # 신뢰할 수 없는 키워드 (스팸/과장 뉴스 필터링)
        self.suspicious_keywords = [
            'pump', 'guaranteed', 'moon', '100x', 'insider', 'leaked',
            'exclusive tip', 'buy now', 'don\'t miss', 'last chance',
            'secret', 'hidden', 'explosive', 'massive gains'
        ]
        
        # 뉴스 쿨다운 관리 (동일한 이벤트의 반복 보고 방지)
        self._news_cooldown = {}
        self.cooldown_duration = 1800  # 30분 쿨다운
        
    def filter_reliable_news(self, news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """신뢰할 만한 뉴스만 필터링"""
        if not news_items:
            return []
        
        reliable_news = []
        
        for item in news_items:
            # 기본 필터링
            if not self._is_valid_news_item(item):
                continue
            
            # 스팸/과장 뉴스 필터링
            if self._is_suspicious_news(item):
                self.logger.debug(f"의심스러운 뉴스 필터링: {item.get('title', '')[:50]}")
                continue
            
            # 신뢰도 임계값 확인
            reliability = item.get('source_reliability', 0.5)
            if reliability < self.config.MIN_NEWS_CONFIDENCE:
                continue
            
            # 중복/쿨다운 확인
            if self._is_in_cooldown(item):
                continue
            
            reliable_news.append(item)
        
        # 신뢰도 순으로 정렬
        reliable_news.sort(key=lambda x: x.get('source_reliability', 0.5), reverse=True)
        
        self.logger.info(f"뉴스 필터링 완료: {len(news_items)} → {len(reliable_news)}")
        return reliable_news
    
    def check_emergency_keywords(self, news_items: List[Dict[str, Any]]) -> Tuple[bool, float]:
        """
        긴급 키워드 확인 (과민반응 방지 개선)
        Returns: (has_emergency, severity_score)
        """
        if not news_items:
            return False, 0.0
        
        max_severity = 0.0
        emergency_count = 0
        total_weight = 0.0
        
        for item in news_items:
            content = (item.get('title', '') + ' ' + item.get('description', '')).lower()
            source_weight = item.get('source_weight', 0.5)
            source_reliability = item.get('source_reliability', 0.5)
            
            # 키워드 매칭 및 심각도 계산
            item_severity = 0.0
            keyword_count = 0
            
            for keyword, severity in self.emergency_keywords.items():
                if keyword in content:
                    item_severity = max(item_severity, severity)
                    keyword_count += 1
            
            if item_severity > 0:
                # 소스 신뢰도와 가중치를 고려한 심각도 조정
                adjusted_severity = item_severity * source_reliability * source_weight
                
                # 키워드가 너무 많으면 스팸일 가능성 (심각도 감소)
                if keyword_count > 3:
                    adjusted_severity *= 0.5
                
                max_severity = max(max_severity, adjusted_severity)
                emergency_count += 1
                total_weight += source_weight
        
        # 긴급 상황 판단 기준 강화 (과민반응 방지)
        # 1. 최소 심각도 임계값: 1.2 (기존보다 높임)
        # 2. 신뢰할 만한 소스에서의 보고 필요
        is_emergency = (
            max_severity >= 1.2 and  # 임계값 상향 조정
            emergency_count >= 1 and
            total_weight >= 0.7  # 신뢰할 만한 소스 필요
        )
        
        if is_emergency:
            self.logger.warning(f"긴급 상황 감지 - 심각도: {max_severity:.2f}, 뉴스 수: {emergency_count}")
        else:
            self.logger.info(f"긴급 키워드 확인 - 심각도: {max_severity:.2f} (임계값 미달)")
        
        return is_emergency, max_severity
    
    def _is_valid_news_item(self, item: Dict[str, Any]) -> bool:
        """뉴스 아이템의 기본 유효성 검사"""
        title = item.get('title', '').strip()
        if not title or len(title) < 10:
            return False
        
        # 너무 오래된 뉴스 제외 (24시간)
        timestamp = item.get('timestamp', time.time())
        if time.time() - timestamp > 86400:  # 24시간
            return False
        
        return True
    
    def _is_suspicious_news(self, item: Dict[str, Any]) -> bool:
        """스팸/과장 뉴스인지 확인"""
        content = (item.get('title', '') + ' ' + item.get('description', '')).lower()
        
        # 의심스러운 키워드 확인
        suspicious_count = sum(1 for keyword in self.suspicious_keywords if keyword in content)
        
        # 의심스러운 키워드가 2개 이상이면 스팸으로 간주
        if suspicious_count >= 2:
            return True
        
        # 제목에 과도한 특수문자/이모지
        title = item.get('title', '')
        special_chars = sum(1 for c in title if c in '!?🚀💰🔥⚡')
        if len(title) > 0 and special_chars / len(title) > 0.1:
            return True
        
        return False
    
    def _is_in_cooldown(self, item: Dict[str, Any]) -> bool:
        """쿨다운 상태인지 확인 (동일 이벤트 반복 방지)"""
        title = item.get('title', '').lower()
        
        # 제목의 핵심 키워드로 쿨다운 키 생성
        cooldown_key = self._generate_cooldown_key(title)
        
        current_time = time.time()
        last_time = self._news_cooldown.get(cooldown_key, 0)
        
        if current_time - last_time < self.cooldown_duration:
            return True
        
        # 쿨다운 업데이트
        self._news_cooldown[cooldown_key] = current_time
        
        # 오래된 쿨다운 정리
        self._cleanup_old_cooldowns()
        
        return False
    
    def _generate_cooldown_key(self, title: str) -> str:
        """쿨다운 키 생성 (제목의 핵심 단어들)"""
        # 핵심 키워드 추출 (간단한 방식)
        words = title.split()
        
        # 중요한 단어들만 선택 (길이 4자 이상)
        key_words = [word for word in words if len(word) >= 4][:3]  # 최대 3개
        
        return '_'.join(sorted(key_words))
    
    def _cleanup_old_cooldowns(self):
        """오래된 쿨다운 항목 정리"""
        current_time = time.time()
        
        # 1시간 이상 된 쿨다운 제거
        cutoff_time = current_time - 3600
        
        keys_to_remove = [
            key for key, timestamp in self._news_cooldown.items()
            if timestamp < cutoff_time
        ]
        
        for key in keys_to_remove:
            del self._news_cooldown[key]
    
    def get_filter_stats(self) -> Dict[str, Any]:
        """필터링 통계 반환"""
        return {
            'emergency_keywords_count': len(self.emergency_keywords),
            'suspicious_keywords_count': len(self.suspicious_keywords),
            'active_cooldowns': len(self._news_cooldown),
            'cooldown_duration_minutes': self.cooldown_duration // 60,
            'min_news_confidence': self.config.MIN_NEWS_CONFIDENCE
        }
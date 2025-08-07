"""
Safe Data Handler
안전한 데이터 접근 및 기본값 처리 유틸리티
"""

import logging
from typing import Any, Dict, Optional, Union, List


class SafeDataHandler:
    """안전한 데이터 접근을 위한 헬퍼 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @staticmethod
    def safe_get(data: Dict[str, Any], key: str, default: Any = None, 
                 expected_type: type = None) -> Any:
        """
        딕셔너리에서 안전하게 값 추출
        
        Args:
            data: 데이터 딕셔너리
            key: 추출할 키
            default: 기본값
            expected_type: 기대되는 타입
            
        Returns:
            안전하게 추출된 값 또는 기본값
        """
        try:
            if not isinstance(data, dict):
                return default
            
            value = data.get(key, default)
            
            # 타입 검증
            if expected_type and value is not None:
                if not isinstance(value, expected_type):
                    try:
                        value = expected_type(value)
                    except (ValueError, TypeError):
                        logging.warning(f"타입 변환 실패: {key}={value}, 기본값 사용: {default}")
                        return default
            
            return value
            
        except Exception as e:
            logging.error(f"safe_get 오류: key={key}, error={e}")
            return default
    
    @staticmethod
    def ensure_analysis_result_keys(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        분석 결과에 필수 키들이 존재하도록 보장
        
        Args:
            result: 분석 결과 딕셔너리
            
        Returns:
            필수 키가 보장된 분석 결과
        """
        if not isinstance(result, dict):
            result = {}
        
        # 필수 키와 기본값 정의
        required_keys = {
            'avg_confidence': 0.5,  # 중립적 신뢰도
            'confidence': 0.5,
            'sentiment_score': 0.0,
            'impact_score': 0.0,
            'prediction': 0.0,
            'accuracy': 0.5,
            'total_predictions': 0,
            'success_rate': 0.5,
            'analysis_status': 'completed',
            'error_message': None,
            'timestamp': None
        }
        
        # 누락된 키 추가
        for key, default_value in required_keys.items():
            if key not in result:
                result[key] = default_value
                logging.debug(f"누락된 키 추가: {key} = {default_value}")
        
        return result
    
    @staticmethod
    def safe_confidence_extract(data: Union[Dict, List, Any], 
                               fallback_confidence: float = 0.5) -> float:
        """
        다양한 데이터 구조에서 신뢰도 값 안전 추출
        
        Args:
            data: 신뢰도가 포함될 수 있는 데이터
            fallback_confidence: 추출 실패 시 사용할 기본 신뢰도
            
        Returns:
            추출된 신뢰도 (0.0 ~ 1.0)
        """
        try:
            confidence = fallback_confidence
            
            if isinstance(data, dict):
                # 가능한 키들 시도
                confidence_keys = ['avg_confidence', 'confidence', 'conf', 'score']
                for key in confidence_keys:
                    if key in data and data[key] is not None:
                        confidence = float(data[key])
                        break
                        
            elif isinstance(data, (list, tuple)) and len(data) > 0:
                # 리스트인 경우 첫 번째 항목에서 시도
                confidence = SafeDataHandler.safe_confidence_extract(data[0], fallback_confidence)
                
            elif isinstance(data, (int, float)):
                confidence = float(data)
            
            # 0.0 ~ 1.0 범위로 클램핑
            confidence = max(0.0, min(1.0, confidence))
            
            return confidence
            
        except (ValueError, TypeError, KeyError) as e:
            logging.warning(f"신뢰도 추출 실패: {e}, 기본값 사용: {fallback_confidence}")
            return fallback_confidence


# 전역 인스턴스
safe_handler = SafeDataHandler()
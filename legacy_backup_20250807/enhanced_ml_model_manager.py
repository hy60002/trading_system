"""
Enhanced ML Model Manager - Additional Features from trading_system2  
trading_system2의 향상된 ML 예측 기능을 기존 시스템에 추가
"""

import asyncio
import logging
from functools import lru_cache
from typing import Dict, Any, List
import hashlib
import time


class EnhancedMLModelManager:
    """
    trading_system2에서 가져온 향상된 ML 모델 매니저
    기존 복합적인 ML 시스템에 추가적인 안전성과 단순성을 제공
    """
    
    def __init__(self, models: dict):
        self.models = models
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 성능 최적화: 캐시 및 배치 처리
        self._prediction_cache = {}
        self._cache_ttl = {}
        self._cache_timeout = 300  # 5분 캐시
        
        # 배치 처리 통계
        self._batch_stats = {
            'total_batches': 0,
            'successful_batches': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
    @lru_cache(maxsize=128)
    def _get_cached_prediction(self, symbol: str, data_hash: str) -> Dict[str, Any]:
        """LRU 캐시를 활용한 예측 결과 캐싱"""
        return self._internal_predict(symbol)
    
    def _internal_predict(self, symbol: str) -> Dict[str, Any]:
        """내부 예측 로직"""
        model = self.models.get(symbol)
        if model is None:
            return {"prediction": "neutral", "confidence": 0.0}
            
        result = model.predict() if hasattr(model, 'predict') else {}
        confidence = result.get("confidence") or result.get("avg_confidence", 0.0)
        
        return {
            "prediction": result.get("prediction", "neutral"),
            "confidence": float(confidence) if confidence else 0.0,
            "source": "enhanced_ml_manager"
        }

    def get_predictions(self, symbol: str) -> Dict[str, Any]:
        """
        향상된 예측 기능 - 캐싱 지원
        """
        try:
            # 캐시 키 생성 (데이터 해시 기반)
            current_time = int(time.time())
            cache_key = f"{symbol}:{current_time // 60}"  # 1분 단위 캐시
            data_hash = hashlib.md5(cache_key.encode()).hexdigest()[:8]
            
            # 캐시된 결과 확인
            if symbol in self._prediction_cache and current_time < self._cache_ttl.get(symbol, 0):
                self._batch_stats['cache_hits'] += 1
                self.logger.debug(f"🎯 {symbol} 캐시 히트: {data_hash}")
                return self._prediction_cache[symbol]
            
            # 캐시 미스 - 새로운 예측 수행
            self._batch_stats['cache_misses'] += 1
            self.logger.debug(f"🔄 {symbol} 캐시 미스, 새 예측 수행: {data_hash}")
            
            model = self.models.get(symbol)
            if model is None:
                self.logger.warning(f"⚠️ {symbol} 모델 없음, neutral 기본값 반환")
                return {"prediction": "neutral", "confidence": 0.0}
                
            # 모델 예측 실행
            result = model.predict() if hasattr(model, 'predict') else {}
            
            # confidence 점수 정규화
            confidence = result.get("confidence") or result.get("avg_confidence", 0.0)
            
            prediction_result = {
                "prediction": result.get("prediction", "neutral"),
                "confidence": float(confidence) if confidence else 0.0,
                "source": "enhanced_ml_manager",
                "cached": False,
                "timestamp": current_time
            }
            
            # 캐시에 저장
            self._prediction_cache[symbol] = prediction_result
            self._cache_ttl[symbol] = current_time + self._cache_timeout
            
            self.logger.debug(f"📊 {symbol} 예측 완료 (캐시 저장): {prediction_result}")
            return prediction_result
            
        except Exception as e:
            self.logger.error(f"❌ {symbol} 예측 오류: {e}", exc_info=True)
            return {"prediction": "neutral", "confidence": 0.0, "error": str(e)}
    
    async def batch_predictions(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        배치 ML 예측 - 병렬 처리로 성능 향상
        """
        if not symbols:
            return {}
        
        try:
            self._batch_stats['total_batches'] += 1
            start_time = time.time()
            
            self.logger.info(f"🚀 배치 예측 시작: {len(symbols)}개 심볼")
            
            # 비동기 병렬 처리
            tasks = [self._async_predict(symbol) for symbol in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 정리
            batch_result = {}
            success_count = 0
            
            for symbol, result in zip(symbols, results):
                if isinstance(result, Exception):
                    self.logger.error(f"❌ {symbol} 배치 예측 실패: {result}")
                    batch_result[symbol] = {"prediction": "neutral", "confidence": 0.0, "error": str(result)}
                else:
                    batch_result[symbol] = result
                    success_count += 1
            
            processing_time = time.time() - start_time
            success_rate = success_count / len(symbols) * 100
            
            if success_count == len(symbols):
                self._batch_stats['successful_batches'] += 1
            
            self.logger.info(f"✅ 배치 예측 완료: {success_count}/{len(symbols)} 성공 ({success_rate:.1f}%, {processing_time:.2f}초)")
            
            return batch_result
            
        except Exception as e:
            self.logger.error(f"❌ 배치 예측 오류: {e}", exc_info=True)
            return {symbol: {"prediction": "neutral", "confidence": 0.0, "error": str(e)} for symbol in symbols}
    
    async def _async_predict(self, symbol: str) -> Dict[str, Any]:
        """비동기 예측 래퍼"""
        return self.get_predictions(symbol)
            
    def get_simple_prediction(self, symbol: str) -> str:
        """
        단순화된 예측 결과 - 복잡한 시스템에서 빠른 결정이 필요할 때 사용
        """
        try:
            result = self.get_predictions(symbol)
            return result.get("prediction", "neutral")
        except:
            return "neutral"
            
    def is_model_available(self, symbol: str) -> bool:
        """
        모델 사용 가능 여부 확인 유틸리티
        """
        return symbol in self.models and self.models[symbol] is not None
        
    def get_available_models(self) -> list:
        """
        사용 가능한 모든 모델 심볼 리스트 반환
        """
        return [symbol for symbol, model in self.models.items() if model is not None]
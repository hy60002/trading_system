"""
Multi-Timeframe Analyzer
Enhanced multi-timeframe analysis with caching and fixed coroutine handling
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict
from cachetools import TTLCache

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..indicators.technical import EnhancedTechnicalIndicators
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from indicators.technical import EnhancedTechnicalIndicators


class MultiTimeframeAnalyzer:
    """Enhanced multi-timeframe analysis with caching and fixed coroutine handling"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._analysis_cache = TTLCache(maxsize=100, ttl=300)
    
    async def analyze_all_timeframes(self, exchange, symbol: str, strategies: Dict) -> Dict:
        """Analyze all timeframes for a symbol with parallel processing"""
        # Check cache first
        cache_key = f"mtf_analysis:{symbol}"
        cached_result = self._analysis_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        results = {}
        timeframes = self.config.TIMEFRAME_WEIGHTS.get(symbol, self.config.TIMEFRAME_WEIGHTS["BTCUSDT"])
        
        # Parallel timeframe analysis
        tasks = []
        for tf_key, weight in timeframes.items():
            task = self._analyze_timeframe(exchange, symbol, tf_key, weight, strategies)
            tasks.append(task)
        
        # Wait for all analyses to complete
        tf_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, (tf_key, weight) in enumerate(timeframes.items()):
            if isinstance(tf_results[i], Exception):
                self.logger.error(f"{symbol} {tf_key} 분석 오류: {tf_results[i]}")
                results[tf_key] = self._get_default_result(weight)
            else:
                results[tf_key] = tf_results[i]
        
        # Combine results
        combined_result = self._combine_timeframe_results(results, symbol)
        
        # Cache the result
        self._analysis_cache[cache_key] = combined_result
        
        return combined_result
    
    async def _analyze_timeframe(self, exchange, symbol: str, timeframe: str, 
                                weight: float, strategies: Dict) -> Dict:
        """Analyze single timeframe with fixed coroutine handling"""
        try:
            # Fetch OHLCV data
            df = await exchange.fetch_ohlcv_with_cache(symbol, timeframe)
            
            if df is None or len(df) < 100:
                return self._get_default_result(weight)
            
            # Calculate indicators
            indicators = EnhancedTechnicalIndicators.calculate_all_indicators(df)
            
            # Get strategy for symbol
            strategy = strategies.get(symbol)
            if not strategy:
                return self._get_default_result(weight)
            
            # Analyze - Fixed: properly await the coroutine
            if asyncio.iscoroutinefunction(strategy.analyze):
                tf_result = await strategy.analyze(symbol, df, indicators)
            else:
                tf_result = strategy.analyze(symbol, df, indicators)
                
            tf_result['weight'] = weight
            tf_result['timeframe'] = timeframe
            
            return tf_result
            
        except Exception as e:
            self.logger.error(f"타임프레임 분석 오류: {e}")
            return self._get_default_result(weight)
    
    def _combine_timeframe_results(self, results: Dict, symbol: str) -> Dict:
        """Combine timeframe results with enhanced logic"""
        if not results:
            return self._get_default_combined_result()
        
        # Calculate weighted scores
        total_weight = 0
        weighted_score = 0
        weighted_confidence = 0
        directions = defaultdict(float)
        timeframe_scores = {}
        
        for tf, result in results.items():
            weight = result.get('weight', 0)
            total_weight += weight
            
            weighted_score += result['score'] * weight
            weighted_confidence += result.get('confidence', 50) * weight
            directions[result['direction']] += weight
            timeframe_scores[tf] = result['score']
        
        if total_weight == 0:
            return self._get_default_combined_result()
        
        # Normalize
        final_score = weighted_score / total_weight
        final_confidence = weighted_confidence / total_weight
        
        # Determine direction based on symbol-specific thresholds
        agreement_threshold = self.config.ENTRY_CONDITIONS[symbol]['timeframe_agreement']
        
        direction = 'neutral'
        alignment_score = 0
        
        for dir_name, dir_weight in directions.items():
            dir_ratio = dir_weight / total_weight
            if dir_ratio >= agreement_threshold:
                direction = dir_name
                alignment_score = dir_ratio
                break
        
        # Check for divergence
        divergence = self._check_divergence(timeframe_scores)
        
        # Adjust confidence based on alignment and divergence
        if alignment_score < agreement_threshold:
            final_confidence *= 0.7
        if divergence:
            final_confidence *= 0.8
        
        is_aligned = alignment_score >= agreement_threshold and not divergence
        
        return {
            'direction': direction,
            'score': final_score,
            'confidence': final_confidence,
            'alignment_score': alignment_score,
            'timeframe_results': results,
            'is_aligned': is_aligned,
            'divergence': divergence,
            'timeframe_scores': timeframe_scores
        }
    
    def _check_divergence(self, timeframe_scores: Dict) -> bool:
        """Check for significant divergence between timeframes"""
        if len(timeframe_scores) < 2:
            return False
        
        scores = list(timeframe_scores.values())
        
        # Check if any timeframe strongly disagrees
        positive_scores = [s for s in scores if s > 0.3]
        negative_scores = [s for s in scores if s < -0.3]
        
        # Divergence if we have both strong positive and negative signals
        return len(positive_scores) > 0 and len(negative_scores) > 0
    
    def _get_default_result(self, weight: float) -> Dict:
        """Default result for a timeframe"""
        return {
            'direction': 'neutral',
            'score': 0,
            'confidence': 50,
            'weight': weight,
            'components': {}
        }
    
    def _get_default_combined_result(self) -> Dict:
        """Default combined result"""
        return {
            'direction': 'neutral',
            'score': 0,
            'confidence': 50,
            'alignment_score': 0,
            'timeframe_results': {},
            'is_aligned': False,
            'divergence': False,
            'timeframe_scores': {}
        }
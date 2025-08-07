"""
Advanced Trading Engine
Main trading strategy engine with all components integrated
"""

import asyncio
import logging
import time
import traceback
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..database.db_manager import EnhancedDatabaseManager
    from ..exchange.bitget_manager import EnhancedBitgetExchangeManager
    from ..managers.position_manager import PositionManager
    from ..managers.risk_manager import RiskManager
    from ..managers.ml_model_manager import EnhancedMLModelManager
    from ..managers.capital_tracker import CapitalTracker
    from ..notifications.notification_manager import NotificationManager
    from ..analyzers.multi_timeframe import MultiTimeframeAnalyzer
    from ..analyzers.performance import PerformanceAnalyzer
    from ..analyzers.news_sentiment import EnhancedNewsSentimentAnalyzer
    from ..analyzers.market_regime import MarketRegimeAnalyzer
    from ..analyzers.pattern_recognition import PatternRecognitionSystem
    from ..analyzers.gpt_analyzer import GPTAnalyzer
    from ..indicators.technical import EnhancedTechnicalIndicators
    from ..strategies.btc_strategy import BTCTradingStrategy
    from ..strategies.eth_strategy import ETHTradingStrategy
    from ..utils.safe_data_handler import safe_handler
    from ..utils.balance_safe_handler import balance_handler
    from ..utils.telegram_safe_formatter import telegram_formatter
    from ..utils.websocket_resilient_manager import ws_manager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from exchange.bitget_manager import EnhancedBitgetExchangeManager
    from managers.position_manager import PositionManager
    from managers.risk_manager import RiskManager
    from managers.ml_model_manager import EnhancedMLModelManager
    from managers.capital_tracker import CapitalTracker
    from notifications.notification_manager import NotificationManager
    from analyzers.multi_timeframe import MultiTimeframeAnalyzer
    from analyzers.performance import PerformanceAnalyzer
    from analyzers.news_sentiment import EnhancedNewsSentimentAnalyzer
    from analyzers.market_regime import MarketRegimeAnalyzer
    from analyzers.pattern_recognition import PatternRecognitionSystem
    from utils.safe_data_handler import safe_handler
    from utils.balance_safe_handler import balance_handler
    from utils.telegram_safe_formatter import telegram_formatter
    from utils.websocket_resilient_manager import ws_manager
    from analyzers.gpt_analyzer import GPTAnalyzer
    from indicators.technical import EnhancedTechnicalIndicators
    from strategies.btc_strategy import BTCTradingStrategy
    from strategies.eth_strategy import ETHTradingStrategy


class AdvancedTradingEngine:
    """Main trading strategy engine with all components integrated"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.db = EnhancedDatabaseManager(config.DATABASE_PATH)
        self.exchange = EnhancedBitgetExchangeManager(config)
        self.notifier = NotificationManager(config)
        self.position_manager = PositionManager(config, self.exchange, self.db, self.notifier)
        self.risk_manager = RiskManager(config, self.db)
        self.capital_tracker = CapitalTracker(config, self.db, self.notifier, self.exchange)
        self.performance_analyzer = PerformanceAnalyzer(self.db)
        
        # Analysis components
        self.multi_tf_analyzer = MultiTimeframeAnalyzer(config)
        self.regime_analyzer = MarketRegimeAnalyzer()
        self.pattern_recognizer = PatternRecognitionSystem()
        self.news_analyzer = EnhancedNewsSentimentAnalyzer(config, self.db)
        self.gpt_analyzer = GPTAnalyzer(config, self.logger)
        
        # ML models
        self.ml_manager = EnhancedMLModelManager(config, self.db)
        
        # Trading strategies by symbol (only BTC and ETH now)
        self.strategies = {
            'BTCUSDT': BTCTradingStrategy(config),
            'ETHUSDT': ETHTradingStrategy(config)
        }
        
        # State tracking
        self.last_analysis_time = {}
        self.is_running = True
        self.startup_time = datetime.now()
        self._analysis_lock = asyncio.Lock()
        
        # Track prediction results for ML learning
        self.pending_predictions = {}
    
    async def initialize(self):
        """Initialize all components"""
        self.logger.info("="*60)
        self.logger.info("고급 Bitget 거래 시스템 v3.0 초기화 중")
        self.logger.info("="*60)
        
        try:
            # 1. Initialize database first
            self.db.initialize_database()
            self.logger.info("✅ 데이터베이스 초기화 완료")
            
            # 2. Initialize exchange (critical for all trading operations)
            await self.exchange.initialize()
            self.logger.info("✅ 거래소 연결 초기화 완료")
            
            # 3. Initialize notification system (needed for all alerts)
            await self.notifier.initialize()
            self.logger.info("✅ 알림 시스템 초기화 완료")
            
            # 4. Initialize position manager (needed for trading)
            await self.position_manager.initialize()
            self.logger.info("✅ 포지션 매니저 초기화 완료")
            
            # 5. Initialize capital tracking system
            await self.capital_tracker.initialize()
            self.logger.info("✅ 자본 추적 시스템 초기화 완료")
            
            # 6. Initialize ML models (if enabled)
            if self.config.ENABLE_ML_MODELS:
                await self.ml_manager.initialize()
                self.logger.info("✅ ML 모델 매니저 초기화 완료")
            
            # 7. Initialize news sentiment analyzer
            await self.news_analyzer.initialize()
            self.logger.info("✅ 뉴스 감정 분석기 초기화 완료")
            
            # Check balance - BalanceSafeHandler 적용
            balance = await self.exchange.get_balance()  # 이미 safe_handler가 적용됨
            usdt_balance = balance.get('balances', {}).get('USDT', {}).get('free', 0)
            
            self.logger.info(f"✅ 시스템 초기화 성공")
            self.logger.info(f"💰 USDT 잔액: ${usdt_balance:,.2f}")
            self.logger.info(f"📊 거래 심볼: {', '.join(self.config.SYMBOLS)}")
            self.logger.info(f"⚙️ 포트폴리오 할당: BTC 70%, ETH 20%, XRP 10%")
            self.logger.info(f"🤖 ML 모델: {'활성화' if self.config.ENABLE_ML_MODELS else '비활성화'}")
            self.logger.info(f"📡 WebSocket: {'연결됨' if self.exchange.ws_connected else '연결 안됨'}")
            self.logger.info(f"📈 손절: 5% | 익절: 10%")
            self.logger.info(f"🎯 Kelly 기준: 25% 안전 마진으로 활성화")
            
            # Log system configuration
            self.db.log_system_event('INFO', 'System', '거래 시스템 시작', {
                'balance': usdt_balance,
                'symbols': self.config.SYMBOLS,
                'ml_enabled': self.config.ENABLE_ML_MODELS,
                'websocket': self.exchange.ws_connected,
                'version': '3.0'
            })
            
            # Initialize positions tracking
            await self.position_manager.manage_positions()
            
            # Send startup notification AFTER exchange initialization
            await asyncio.sleep(2)  # Wait for WebSocket connection
            await self.notifier.send_notification(
                f"🚀 거래 시스템 시작 v3.0\n"
                f"💰 잔액: ${usdt_balance:,.2f}\n"
                f"🤖 ML: {'ON' if self.config.ENABLE_ML_MODELS else 'OFF'}\n"
                f"📡 WS: {'ON' if self.exchange.ws_connected else 'OFF'}\n"
                f"🎯 Kelly: ON ({int(self.config.KELLY_FRACTION * 100)}% 안전)",
                priority='high'
            )
            
        except Exception as e:
            self.logger.critical(f"시스템 초기화 실패: {e}")
            await self.notifier.send_error_notification(
                "시스템 초기화 실패",
                str(e),
                "메인"
            )
            raise
    
    async def analyze_and_trade(self, symbol: str):
        """Main analysis and trading logic for a symbol"""
        async with self._analysis_lock:
            try:
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"{symbol} 분석 중 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Check if we should analyze this symbol
                if not self._should_analyze_symbol(symbol):
                    self.logger.info(f"{symbol} 건너뜀 - 최근 분석됨")
                    return
                
                # Update analysis time
                self.last_analysis_time[symbol] = datetime.now()
                
                # Risk checks first
                risk_check = await self.risk_manager.check_risk_limits(symbol)
                if not risk_check['can_trade']:
                    self.logger.warning(f"{symbol} 리스크 한도 초과: {risk_check['checks']}")
                    await self.notifier.send_risk_alert('risk_limit_exceeded', {
                        'symbol': symbol,
                        'message': f"리스크 한도로 {symbol} 거래 불가",
                        'failed_checks': [k for k, v in risk_check['checks'].items() if not v]
                    })
                    return
                
                # Multi-timeframe analysis
                self.logger.info(f"{symbol} 멀티 타임프레임 분석 수행 중...")
                multi_tf_result = await self.multi_tf_analyzer.analyze_all_timeframes(
                    self.exchange, symbol, self.strategies
                )
                
                self.logger.info(
                    f"멀티 TF 결과: 방향={multi_tf_result['direction']}, "
                    f"점수={multi_tf_result['score']:.3f}, "
                    f"정렬={multi_tf_result['alignment_score']:.2f}, "
                    f"발산={multi_tf_result.get('divergence', False)}"
                )
                
                # Check entry conditions
                entry_conditions = self.config.ENTRY_CONDITIONS[symbol]
                
                # For ETH and XRP, check BTC correlation
                if entry_conditions.get('btc_correlation_check', False):
                    btc_result = await self._get_btc_direction()
                    if btc_result['direction'] != multi_tf_result['direction']:
                        self.logger.info(f"{symbol} 방향이 BTC와 충돌, 건너뜀")
                        return
                
                # Check alignment threshold
                if not multi_tf_result['is_aligned']:
                    self.logger.info(f"{symbol} 타임프레임 정렬 안됨 (정렬: {multi_tf_result['alignment_score']:.2f})")
                    return
                
                # Get primary timeframe data for detailed analysis
                primary_tf = self._get_primary_timeframe(symbol)
                df = await self.exchange.fetch_ohlcv_with_cache(symbol, primary_tf)
                
                if df is None or len(df) < 200:
                    self.logger.warning(f"{symbol} 데이터 부족")
                    return
                
                # Calculate comprehensive indicators
                self.logger.info(f"기술적 지표 계산 중...")
                indicators = EnhancedTechnicalIndicators.calculate_all_indicators(df)
                
                # Market regime analysis
                self.logger.info(f"시장 체제 분석 중...")
                regime_info = self.regime_analyzer.analyze_regime(df, indicators)
                self.logger.info(
                    f"시장 체제: {regime_info['regime']} "
                    f"(신뢰도: {regime_info['confidence']:.1f}%)"
                )
                
                # Pattern recognition
                self.logger.info(f"차트 패턴 감지 중...")
                patterns = self.pattern_recognizer.identify_patterns(df, indicators)
                if patterns:
                    pattern_names = list(patterns.keys())
                    self.logger.info(f"감지된 패턴: {', '.join(pattern_names)}")
                
                # News sentiment analysis  
                self.logger.info(f"뉴스 감성 분석 중...")
                news_sentiment = await self.news_analyzer.analyze_sentiment(symbol)
                news_sentiment = safe_handler.ensure_analysis_result_keys(news_sentiment)
                self.logger.info(
                    f"뉴스 감성: {safe_handler.safe_get(news_sentiment, 'sentiment', 0.0):+.2f} "
                    f"({safe_handler.safe_get(news_sentiment, 'impact', 'low')} 영향, "
                    f"신뢰도: {safe_handler.safe_get(news_sentiment, 'avg_confidence', 0.5):.2f})"
                )
                
                # Check for emergency news
                if news_sentiment.get('has_emergency', False):
                    await self._handle_emergency(symbol, news_sentiment)
                    return
                
                # ML predictions if available
                ml_predictions = {}
                if self.config.ENABLE_ML_MODELS:
                    self.logger.info(f"ML 예측 가져오는 중...")
                    features = self._extract_ml_features(df, indicators, regime_info)
                    ml_predictions = await self.ml_manager.get_predictions(symbol, features)
                    
                    if ml_predictions.get('ensemble'):
                        self.logger.info(
                            f"ML 예측: {ml_predictions['ensemble']['direction']} "
                            f"(신뢰도: {ml_predictions['ensemble']['confidence']:.2f})"
                        )
                
                # Generate final trading signal with ML/News weighting
                trading_signal = self._generate_comprehensive_signal(
                    symbol, multi_tf_result, regime_info, patterns, 
                    news_sentiment, ml_predictions, indicators
                )
                
                # Log comprehensive signal
                self.logger.info(
                    f"\n{'='*40}\n"
                    f"{symbol} 거래 신호 요약\n"
                    f"{'='*40}\n"
                    f"방향: {trading_signal['direction']}\n"
                    f"점수: {trading_signal['score']:.3f}\n"
                    f"신뢰도: {trading_signal['confidence']:.1f}%\n"
                    f"ML 가중치: {trading_signal['ml_weight']:.1%}\n"
                    f"뉴스 가중치: {trading_signal['news_weight']:.1%}\n"
                    f"거래 여부: {trading_signal['should_trade']}\n"
                    f"예상 변동: {trading_signal['expected_move']:.2f}%\n"
                    f"{'='*40}"
                )
                
                # Save prediction for tracking
                prediction_id = await self._save_prediction(
                    symbol, df, trading_signal, indicators, regime_info, news_sentiment, ml_predictions
                )
                
                # Execute trade if conditions met
                if trading_signal['should_trade']:
                    await self._execute_trade(symbol, trading_signal, df['close'].iloc[-1])
                else:
                    self.logger.info(f"{symbol} 거래 신호 없음")
                
                # Always manage existing positions
                await self.position_manager.manage_positions()
                
                # Update performance metrics
                await self.performance_analyzer.update_daily_performance()
                
                self.logger.info(f"{symbol} 분석 완료")
                
            except Exception as e:
                self.logger.error(f"{symbol} 분석 오류: {e}")
                self.db.log_system_event('ERROR', 'TradingEngine', 
                                       f"{symbol} 분석 오류", 
                                       {'error': str(e), 'traceback': traceback.format_exc()})
                await self.notifier.send_error_notification(
                    f"{symbol} 분석 실패",
                    str(e),
                    "TradingEngine"
                )
    
    def _should_analyze_symbol(self, symbol: str) -> bool:
        """Check if enough time has passed since last analysis"""
        if symbol not in self.last_analysis_time:
            return True
        
        # Minimum time between analyses (in minutes)
        min_interval = {
            'BTCUSDT': 5,
            'ETHUSDT': 10,
            'XRPUSDT': 15
        }
        
        time_since_last = (datetime.now() - self.last_analysis_time[symbol]).seconds / 60
        return time_since_last >= min_interval.get(symbol, 10)
    
    def _get_primary_timeframe(self, symbol: str) -> str:
        """Get primary timeframe for analysis"""
        timeframes = self.config.TIMEFRAME_WEIGHTS.get(symbol, {})
        if not timeframes:
            return '4h'
        
        # Return timeframe with highest weight
        return max(timeframes.items(), key=lambda x: x[1])[0]
    
    async def _get_btc_direction(self) -> Dict:
        """Get BTC direction for correlation check"""
        # Quick BTC analysis with caching
        btc_result = await self.multi_tf_analyzer.analyze_all_timeframes(
            self.exchange, 'BTCUSDT', self.strategies
        )
        return btc_result
    
    def _extract_ml_features(self, df: pd.DataFrame, indicators: Dict, 
                           regime_info: Dict) -> Dict[str, float]:
        """Extract features for ML models"""
        features = {}
        
        # Price-based features
        features['returns_1'] = df['close'].pct_change(1).iloc[-1]
        features['returns_5'] = df['close'].pct_change(5).iloc[-1]
        features['returns_20'] = df['close'].pct_change(20).iloc[-1]
        
        # Volume features
        features['volume_ratio'] = indicators['volume_ratio'].iloc[-1]
        features['volume_ma_ratio'] = df['volume'].iloc[-1] / indicators['volume_sma'].iloc[-1]
        
        # Volatility features
        features['atr_ratio'] = indicators['atr_percent'].iloc[-1] / 100
        features['bb_position'] = indicators['price_position'].iloc[-1]
        
        # Technical indicators
        features['rsi'] = (indicators['rsi'].iloc[-1] - 50) / 50  # Normalize
        features['macd_signal'] = np.sign(indicators['macd'].iloc[-1] - indicators['macd_signal'].iloc[-1])
        features['adx'] = indicators['adx'].iloc[-1] / 100
        
        # Trend features
        features['price_ma_ratio'] = df['close'].iloc[-1] / indicators['sma_50'].iloc[-1]
        features['trend_strength'] = indicators['trend_strength'].iloc[-1]
        
        # Volume flow
        try:
            if 'obv' in indicators and len(indicators['obv']) > 20:
                obv_values = indicators['obv'].iloc[-20:].values
                if len(obv_values) >= 20:
                    features['obv_slope'] = np.polyfit(range(20), obv_values, 1)[0]
                else:
                    features['obv_slope'] = 0
            else:
                features['obv_slope'] = 0
        except Exception as e:
            features['obv_slope'] = 0
        
        # Volatility ratio
        features['volatility_ratio'] = indicators['volatility_ratio'].iloc[-1]
        
        # Regime features
        regime_mapping = {
            'trending_up': 1,
            'trending_down': -1,
            'ranging': 0,
            'volatile': 0
        }
        features['regime'] = regime_mapping.get(regime_info['regime'], 0)
        
        return features
    
    def _generate_comprehensive_signal(self, symbol: str, multi_tf: Dict, regime: Dict,
                                     patterns: Dict, news: Dict, ml_predictions: Dict,
                                     indicators: Dict) -> Dict:
        """Generate final trading signal with ML/News weighting"""
        # Initialize component weights
        base_weights = {
            'technical': 0.60,  # 60% for technical analysis (multi-tf + regime + patterns)
            'ml': self.config.ML_WEIGHT,  # 80% of remaining 40%
            'news': self.config.NEWS_WEIGHT  # 20% of remaining 40%
        }
        
        # Adjust weights if ML is disabled
        if not ml_predictions or not ml_predictions.get('ensemble'):
            base_weights['technical'] = 0.80
            base_weights['ml'] = 0
            base_weights['news'] = 0.20
        
        # Calculate technical components
        technical_score = self._calculate_technical_score(
            symbol, multi_tf, regime, patterns, indicators
        )
        
        # ML score
        ml_score = 0
        ml_confidence = 0
        if ml_predictions and 'ensemble' in ml_predictions:
            ensemble = ml_predictions['ensemble']
            ml_score = ensemble['prediction']
            ml_confidence = ensemble['confidence']
        
        # News score with confidence weighting - SafeDataHandler 적용
        news = safe_handler.ensure_analysis_result_keys(news)
        news_score = safe_handler.safe_get(news, 'sentiment', 0.0) * safe_handler.safe_get(news, 'avg_confidence', 0.5)
        if news['impact'] == 'high':
            news_score *= 1.5
        elif news['impact'] == 'low':
            news_score *= 0.5
        
        # Calculate weighted final score
        if base_weights['ml'] > 0:
            # Separate technical and AI components
            ai_component = (
                ml_score * base_weights['ml'] + 
                news_score * base_weights['news']
            ) / (base_weights['ml'] + base_weights['news'])
            
            final_score = (
                technical_score * base_weights['technical'] +
                ai_component * (1 - base_weights['technical'])
            )
        else:
            # No ML, just technical and news
            final_score = (
                technical_score * base_weights['technical'] +
                news_score * base_weights['news']
            )
        
        # Calculate confidence
        confidence = self._calculate_signal_confidence(
            multi_tf, regime, patterns, news, ml_predictions, ml_confidence
        )
        
        # Determine if we should trade
        entry_conditions = self.config.ENTRY_CONDITIONS[symbol]
        
        # Apply regime-specific adjustments
        regime_params = regime['parameters']
        adjusted_threshold = entry_conditions['signal_threshold'] * regime_params.get('signal_threshold_multiplier', 1.0)
        
        should_trade = (
            abs(final_score) >= adjusted_threshold and
            confidence >= entry_conditions['confidence_required'] and
            multi_tf['is_aligned']
        )
        
        # Special conditions for XRP
        if symbol == 'XRPUSDT' and entry_conditions.get('extreme_rsi_only', False):
            rsi = indicators['rsi'].iloc[-1]
            if not (rsi < 25 or rsi > 75):
                should_trade = False
        
        # Determine direction
        if final_score > adjusted_threshold:
            direction = 'long'
        elif final_score < -adjusted_threshold:
            direction = 'short'
        else:
            direction = 'neutral'
            should_trade = False
        
        # Calculate expected move based on volatility and confidence
        base_move = abs(final_score) * 0.05
        volatility_adj = 1 + (indicators['atr_percent'].iloc[-1] / 100 - 0.02)
        expected_move = base_move * volatility_adj * (confidence / 100)
        
        # Apply regime position size adjustment
        position_size_multiplier = regime_params.get('position_size_multiplier', 1.0)
        
        return {
            'should_trade': should_trade,
            'direction': direction,
            'score': final_score,
            'confidence': confidence,
            'expected_move': expected_move,
            'components': {
                'technical': technical_score,
                'ml': ml_score,
                'news': news_score
            },
            'weights': base_weights,
            'ml_weight': base_weights.get('ml', 0),
            'news_weight': base_weights.get('news', 0),
            'stop_loss': self.config.FALLBACK_STOP_LOSS[symbol],
            'take_profit': self.config.FALLBACK_TAKE_PROFIT[symbol],
            'position_size_multiplier': position_size_multiplier,
            'regime': regime['regime'],
            'alignment_score': multi_tf['alignment_score']
        }
    
    def _calculate_technical_score(self, symbol: str, multi_tf: Dict, regime: Dict,
                                  patterns: Dict, indicators: Dict) -> float:
        """Calculate combined technical analysis score"""
        # Multi-timeframe score
        if multi_tf['is_aligned']:
            tf_score = multi_tf['score'] * multi_tf['alignment_score']
        else:
            tf_score = multi_tf['score'] * 0.5
        
        # Regime score
        regime_score = 0
        if regime['regime'] == 'trending_up' and multi_tf['direction'] == 'long':
            regime_score = 0.8
        elif regime['regime'] == 'trending_down' and multi_tf['direction'] == 'short':
            regime_score = 0.8
        elif regime['regime'] == 'ranging':
            # Mean reversion in ranging markets
            rsi = indicators['rsi'].iloc[-1]
            if rsi < 30:
                regime_score = 0.6
            elif rsi > 70:
                regime_score = -0.6
        
        # Pattern score
        pattern_score = self._calculate_pattern_score(patterns, multi_tf['direction'])
        
        # Weight components
        weights = {
            'multi_timeframe': 0.50,
            'regime': 0.30,
            'patterns': 0.20
        }
        
        total_score = (
            tf_score * weights['multi_timeframe'] +
            regime_score * weights['regime'] +
            pattern_score * weights['patterns']
        )
        
        return np.clip(total_score, -1, 1)
    
    def _calculate_pattern_score(self, patterns: Dict, preferred_direction: str) -> float:
        """Calculate score from detected patterns"""
        if not patterns:
            return 0
        
        score = 0
        pattern_count = 0
        
        for pattern_name, pattern_info in patterns.items():
            if not pattern_info.get('detected', False):
                continue
            
            pattern_count += 1
            expected_move = pattern_info.get('expected_move', 0)
            pattern_confidence = pattern_info.get('confidence', 0.5)
            
            # Check if pattern aligns with preferred direction
            if expected_move > 0 and preferred_direction == 'long':
                score += expected_move * pattern_confidence
            elif expected_move < 0 and preferred_direction == 'short':
                score += abs(expected_move) * pattern_confidence
            else:
                # Pattern conflicts with direction
                score -= abs(expected_move) * pattern_confidence * 0.5
        
        # Normalize by pattern count
        if pattern_count > 0:
            score /= pattern_count
        
        return np.clip(score, -1, 1)
    
    def _calculate_signal_confidence(self, multi_tf: Dict, regime: Dict, patterns: Dict,
                                   news: Dict, ml: Dict, ml_confidence: float) -> float:
        """Calculate overall signal confidence"""
        # Base confidence from multi-timeframe analysis
        base_confidence = multi_tf.get('confidence', 50)
        
        # Regime confidence contribution
        regime_confidence = regime.get('confidence', 50)
        
        # ML confidence if available
        if ml_confidence > 0:
            ml_conf_score = ml_confidence * 100
        else:
            ml_conf_score = 50
        
        # News confidence - SafeDataHandler 적용
        news_conf_score = safe_handler.safe_get(news, 'avg_confidence', 0.5) * 100
        
        # Calculate weighted confidence
        if self.config.ENABLE_ML_MODELS and ml_confidence > 0:
            confidence_weights = {
                'base': 0.3,
                'regime': 0.2,
                'ml': 0.3,
                'news': 0.1,
                'alignment': 0.1
            }
        else:
            confidence_weights = {
                'base': 0.4,
                'regime': 0.3,
                'ml': 0,
                'news': 0.2,
                'alignment': 0.1
            }
        
        weighted_confidence = (
            base_confidence * confidence_weights['base'] +
            regime_confidence * confidence_weights['regime'] +
            ml_conf_score * confidence_weights['ml'] +
            news_conf_score * confidence_weights['news'] +
            multi_tf['alignment_score'] * 100 * confidence_weights['alignment']
        )
        
        # Adjust for component agreement
        components = []
        if multi_tf['score'] != 0:
            components.append(multi_tf['score'])
        if ml and ml.get('ensemble'):
            components.append(ml['ensemble']['prediction'])
        if news['sentiment'] != 0:
            components.append(news['sentiment'])
        
        if len(components) >= 2:
            # Check if all components agree on direction
            all_positive = all(c > 0 for c in components)
            all_negative = all(c < 0 for c in components)
            
            if all_positive or all_negative:
                weighted_confidence *= 1.2
            else:
                weighted_confidence *= 0.9
        
        # Penalty for high volatility
        if regime['regime'] == 'volatile':
            weighted_confidence *= 0.85
        
        # Penalty for news uncertainty
        if news.get('urgency') == 'immediate' and abs(news['sentiment']) < 0.3:
            weighted_confidence *= 0.8
        
        return min(95, max(20, weighted_confidence))
    
    async def _save_prediction(self, symbol: str, df: pd.DataFrame, signal: Dict, 
                             indicators: Dict, regime: Dict, news: Dict, 
                             ml_predictions: Dict) -> int:
        """Save prediction for performance tracking"""
        current_price = df['close'].iloc[-1]
        
        # Extract key indicator values
        indicator_snapshot = {
            'rsi': float(indicators['rsi'].iloc[-1]),
            'macd': float(indicators['macd'].iloc[-1]),
            'macd_signal': float(indicators['macd_signal'].iloc[-1]),
            'adx': float(indicators['adx'].iloc[-1]),
            'atr_percent': float(indicators['atr_percent'].iloc[-1]),
            'bb_position': float(indicators['price_position'].iloc[-1]),
            'volume_ratio': float(indicators['volume_ratio'].iloc[-1])
        }
        
        prediction_data = {
            'symbol': symbol,
            'timeframe': self._get_primary_timeframe(symbol),
            'price': current_price,
            'prediction': signal['expected_move'],
            'confidence': signal['confidence'],
            'direction': signal['direction'],
            'model_predictions': ml_predictions.get('ensemble', {}),
            'technical_score': signal['score'],
            'news_sentiment': news['sentiment'],
            'multi_tf_score': signal['alignment_score'],
            'regime': regime['regime'],
            'indicators': indicator_snapshot
        }
        
        prediction_id = self.db.save_prediction_with_indicators(prediction_data)
        
        # Store ML prediction IDs for later result tracking
        if ml_predictions and 'prediction_ids' in ml_predictions:
            self.pending_predictions[symbol] = {
                'prediction_id': prediction_id,
                'ml_prediction_ids': ml_predictions['prediction_ids'],
                'timestamp': datetime.now(),
                'price': current_price
            }
        
        return prediction_id
    
    async def _execute_trade(self, symbol: str, signal: Dict, current_price: float):
        """Execute trade with comprehensive checks"""
        try:
            # Double-check risk limits
            risk_check = await self.risk_manager.check_risk_limits(symbol)
            if not risk_check['can_trade']:
                self.logger.warning(f"실행 시점에 {symbol} 리스크 체크 실패")
                return
            
            # Get available capital - BalanceSafeHandler 적용
            balance = await self.exchange.get_balance()
            
            # Debug: Print balance structure to understand the issue
            self.logger.info(f"🔍 Balance structure debug: {balance}")
            
            # 정규화된 잔고에서 USDT 추출
            total_capital = balance.get('balances', {}).get('USDT', {}).get('free', 0)
            
            # 대체 방법으로 available_balance 사용
            if total_capital == 0:
                total_capital = balance.get('available_balance', 0)
            
            self.logger.info(f"💰 Extracted USDT balance: ${total_capital:.2f}")
            
            if total_capital <= 100:  # Minimum capital requirement
                self.logger.warning(f"USDT 잔액 부족: ${total_capital:.2f}")
                await self.notifier.send_notification(
                    f"⚠️ 낮은 잔액 경고: ${total_capital:.2f}",
                    priority='high'
                )
                return
            
            # Get open positions
            open_positions = self.db.get_open_positions()
            
            # 🚨 Enhanced: Real-time capital tracker check
            await self.capital_tracker.force_update()  # Get latest data
            
            # Calculate estimated position cost
            estimated_position_size = total_capital * 0.05  # Initial estimate
            can_open, reason, details = self.capital_tracker.can_open_position(symbol, estimated_position_size)
            
            if not can_open:
                self.logger.warning(
                    f"⛔ {symbol} 거래 중단 - 자본 할당 제한\n"
                    f"   사유: {reason}\n"
                    f"   현재 할당: {details['current_allocation']:.1%}\n"
                    f"   예상 할당: {details['new_allocation']:.1%}\n"
                    f"   사용 가능: ${details['available_capital']:.2f}"
                )
                await self.notifier.send_notification(
                    f"🛑 **{symbol} 거래 중단**\n\n"
                    f"**사유**: {reason}\n"
                    f"**현재 할당**: {details['current_allocation']:.1%}\n"
                    f"**예상 할당**: {details['new_allocation']:.1%}\n"
                    f"**가용 자본**: ${details['available_capital']:.2f}",
                    priority='high'
                )
                return

            # 🔥 ENHANCED: Calculate allocation with comprehensive logging
            self.logger.info(f"🔍 {symbol} 자본 할당 계산 시작...")
            self.logger.info(f"   총 자본: ${total_capital:.2f}")
            self.logger.info(f"   현재 포지션 수: {len(open_positions)}")
            
            # Debug: Log position data
            for i, pos in enumerate(open_positions):
                self.logger.debug(f"   포지션 {i+1}: {pos.get('symbol')} qty={pos.get('quantity')} price={pos.get('entry_price')}")
            
            allocated_capital = self.risk_manager.calculate_position_allocation(
                symbol, total_capital, open_positions
            )
            
            # 🔥 CRITICAL FIX: Enhanced checks for None allocated_capital
            self.logger.info(f"💰 {symbol} 할당 계산 결과: {allocated_capital}")
            
            if allocated_capital is None:
                self.logger.error(f"❌ {symbol} allocated_capital이 None을 반환했습니다")
                return
                
            if allocated_capital <= 0:
                self.logger.error(f"❌ {symbol} allocated_capital이 0 이하입니다: {allocated_capital}")
                return
            
            self.logger.info(f"💰 {symbol} 할당된 자본: ${allocated_capital:.2f}")
            
            # Double-check with capital tracker
            final_check_can_open, final_reason, final_details = self.capital_tracker.can_open_position(symbol, allocated_capital)
            if not final_check_can_open:
                self.logger.warning(f"⛔ {symbol} 최종 자본 검증 실패: {final_reason}")
                available_capital = final_details.get('available_capital', 0)
                if available_capital > 0:
                    allocated_capital = min(allocated_capital, available_capital)
                else:
                    self.logger.error(f"❌ {symbol} 사용 가능한 자본 없음")
                    return
            
            # Apply signal's position size multiplier
            multiplier = signal.get('position_size_multiplier', 1.0)
            if multiplier is None:
                multiplier = 1.0
            allocated_capital = float(allocated_capital) * float(multiplier)
            
            # Bitget minimum position value (lowered for testing with small capital)
            min_position_value = 5  # Further reduced to allow small capital testing
            if allocated_capital <= min_position_value:
                self.logger.warning(f"{symbol} 할당 자본 너무 작음: ${allocated_capital:.2f} (최소: ${min_position_value})")
                # Instead of returning, try to use minimum viable amount
                if allocated_capital > 1:  # At least $1
                    allocated_capital = max(allocated_capital, min_position_value)
                    self.logger.info(f"{symbol} 최소 거래 금액으로 조정: ${allocated_capital:.2f}")
                else:
                    return
            
            # Log pre-trade state
            self.db.log_system_event('INFO', 'TradeExecution', 
                                   f"{symbol} 포지션 개시 시도",
                                   {
                                       'signal': signal,
                                       'allocated_capital': allocated_capital,
                                       'current_price': current_price,
                                       'kelly_fraction': self.db.get_kelly_fraction(symbol)
                                   })
            
            # Open position
            result = await self.position_manager.open_position(
                symbol, signal, allocated_capital
            )
            
            if result:
                # Send success notification with capital tracking info
                position_data = result['position_data']
                capital_status = self.capital_tracker.get_current_status()
                
                await self.notifier.send_trade_notification(
                    symbol,
                    f"open_{signal['direction']}",
                    {
                        'price': current_price,
                        'quantity': position_data['quantity'],
                        'signal_strength': signal['score'],
                        'confidence': signal['confidence'],
                        'regime': signal['regime'],
                        'allocated_capital': allocated_capital,
                        'leverage': position_data.get('leverage', 1),
                        'current_balance': capital_status.get('total_balance', 0),
                        'total_allocation': capital_status.get('allocation_percentage', 0),
                        'ml_weight': f"{signal['ml_weight']:.0%}",
                        'news_weight': f"{signal['news_weight']:.0%}",
                        'reason': f"Signal: {signal['score']:.2f}, Confidence: {signal['confidence']:.0f}%"
                    }
                )
                
                self.logger.info(f"✅ {symbol} 거래 실행 성공")
                
                # Log successful trade
                self.db.log_system_event('INFO', 'TradeExecution',
                                       f"{symbol} 포지션 개시",
                                       {'result': result})
            else:
                self.logger.warning(f"{symbol} 거래 실행 실패")
                
        except Exception as e:
            self.logger.error(f"{symbol} 거래 실행 오류: {e}")
            self.db.log_system_event('ERROR', 'TradeExecution',
                                   f"{symbol} 거래 실행 실패",
                                   {'error': str(e), 'traceback': traceback.format_exc()})
            await self.notifier.send_error_notification(
                f"{symbol} 거래 실행 실패",
                str(e),
                "TradeExecution"
            )
    
    async def _handle_emergency(self, symbol: str, news_sentiment: Dict):
        """Handle emergency news situation"""
        self.logger.warning(f"🚨 {symbol} 긴급 상황")
        
        # Log emergency
        self.db.log_system_event('CRITICAL', 'Emergency',
                               f"{symbol} 긴급 상황 감지",
                               {'news': news_sentiment})
        
        # Get all positions for the symbol
        positions = self.db.get_open_positions(symbol)
        
        if positions:
            self.logger.info(f"{symbol} {len(positions)}개 포지션 마감 중")
            
            # Close all positions
            for position in positions:
                try:
                    await self.position_manager._close_position(
                        position, '긴급_뉴스', position.get('current_price', 0)
                    )
                except Exception as e:
                    self.logger.error(f"포지션 {position['id']} 마감 실패: {e}")
        
        # Send emergency notification
        await self.notifier.send_notification(
            f"🚨 **긴급: {symbol}**\n\n"
            f"뉴스: {news_sentiment.get('latest_news', '알 수 없음')}\n"
            f"감성: {news_sentiment.get('sentiment', 0):.2f}\n"
            f"영향: {news_sentiment.get('impact', '알 수 없음')}\n\n"
            f"조치: 모든 포지션 마감됨",
            priority='emergency'
        )
    
    async def update_ml_predictions(self):
        """Update ML predictions with actual results"""
        current_time = datetime.now()
        
        for symbol, pending in list(self.pending_predictions.items()):
            # Check if enough time has passed (at least 1 hour)
            time_elapsed = (current_time - pending['timestamp']).seconds / 3600
            
            if time_elapsed >= 1:
                # Get current price
                current_price = self.exchange.get_current_price(symbol)
                if not current_price:
                    continue
                
                # Calculate actual change
                actual_change = (current_price - pending['price']) / pending['price']
                
                # Update each ML prediction
                for model_name, pred_id in pending['ml_prediction_ids'].items():
                    self.ml_manager.update_prediction_result(pred_id, actual_change)
                
                # Remove from pending
                del self.pending_predictions[symbol]
                
                self.logger.info(f"{symbol} ML 예측 업데이트 - 실제: {actual_change:.3f}")
    
    async def run_trading_cycle(self):
        """Run one complete trading cycle"""
        cycle_start = datetime.now()
        self.logger.info("\n" + "="*60)
        self.logger.info(f"거래 사이클 시작 - {cycle_start}")
        
        try:
            # Update ML predictions with results
            await self.update_ml_predictions()
            
            # Analyze each symbol
            for symbol in self.config.SYMBOLS:
                try:
                    await self.analyze_and_trade(symbol)
                    
                    # Small delay between symbols to avoid rate limits
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    self.logger.error(f"{symbol} 거래 사이클 오류: {e}")
                    await self.notifier.send_error_notification(
                        f"{symbol} 거래 사이클 오류",
                        str(e),
                        "TradingCycle"
                    )
            
            # After analyzing all symbols, manage positions
            self.logger.info("\n모든 포지션 관리 중...")
            await self.position_manager.manage_positions()
            
            # Update performance metrics
            await self.performance_analyzer.update_daily_performance()
            
            # Log cycle completion
            cycle_duration = (datetime.now() - cycle_start).seconds
            self.logger.info(f"거래 사이클 완료 - 소요 시간: {cycle_duration}초")
            
            # Send performance update if it's been an hour
            if hasattr(self, '_last_report_time'):
                time_since_report = (datetime.now() - self._last_report_time).seconds / 3600
                if time_since_report >= 1:
                    await self._send_performance_update()
                    self._last_report_time = datetime.now()
            else:
                self._last_report_time = datetime.now()
                
        except Exception as e:
            self.logger.critical(f"거래 사이클 중 심각한 오류: {e}")
            await self.notifier.send_error_notification(
                "거래 사이클 심각한 오류",
                str(e),
                "TradingCycle"
            )
    
    async def _send_performance_update(self):
        """Send hourly performance update"""
        try:
            # Get current stats
            daily_perf = self.db.get_daily_performance()
            open_positions = self.db.get_open_positions()
            
            # Format update
            update = f"""
📊 **시간별 업데이트**

오픈 포지션: {len(open_positions)}개
일일 손익: {daily_perf['total_pnl_percent']:+.2f}%
일일 거래: {daily_perf['total_trades']}회
승률: {daily_perf['win_rate']:.1%}
Kelly 평균: {daily_perf['kelly_fraction']:.3f}
"""
            
            # Add position details if any
            if open_positions:
                update += "\n**현재 포지션:**\n"
                for pos in open_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    pnl = self.position_manager._calculate_pnl(
                        pos, pos.get('current_price', pos['entry_price'])
                    )
                    update += f"• {symbol} {side.upper()}: {pnl['pnl_percent']:+.2f}%\n"
            
            await self.notifier.send_notification(update, priority='normal')
            
        except Exception as e:
            self.logger.error(f"성과 업데이트 전송 실패: {e}")
    
    def get_system_status(self) -> Dict:
        """Get enhanced comprehensive system status with health metrics"""
        uptime = datetime.now() - self.startup_time
        
        # Calculate health scores
        exchange_health = self._calculate_exchange_health()
        ml_health = self._calculate_ml_health() 
        news_health = self._calculate_news_health()
        overall_health = (exchange_health + ml_health + news_health) / 3
        
        return {
            'status': 'running' if self.is_running else 'stopped',
            'uptime_hours': uptime.total_seconds() / 3600,
            'uptime_formatted': str(uptime).split('.')[0],  # Human readable uptime
            'exchange_connected': self.exchange.ws_connected,
            'exchange_health': exchange_health,
            'ml_enabled': self.config.ENABLE_ML_MODELS,
            'ml_health': ml_health,
            'news_health': news_health,
            'overall_health': overall_health,
            'health_status': self._get_health_status_text(overall_health),
            'last_analysis': {
                symbol: analysis_time.isoformat() if isinstance(analysis_time, datetime) else str(analysis_time)
                for symbol, analysis_time in self.last_analysis_time.items()
            },
            'active_positions': len(self.db.get_open_positions()),
            'daily_trades': self._get_daily_trade_count(),
            'error_rate': self._calculate_error_rate(),
            'performance_metrics': self._get_performance_summary(),
            'version': '3.0'
        }
        
    def _calculate_exchange_health(self) -> float:
        """Calculate exchange connection health score"""
        health = 0.0
        
        # WebSocket connection
        if self.exchange.ws_connected:
            health += 0.4
            
        # Recent price updates
        if hasattr(self.exchange, 'price_data') and self.exchange.price_data:
            recent_updates = sum(1 for data in self.exchange.price_data.values() 
                               if data.get('timestamp', 0) > time.time() - 300)  # 5 minutes
            health += min(0.3, recent_updates * 0.1)
            
        # API response health
        if not hasattr(self, '_recent_api_errors'):
            self._recent_api_errors = 0
        health += max(0.0, 0.3 - (self._recent_api_errors * 0.1))
        
        return min(1.0, health)
        
    def _calculate_ml_health(self) -> float:
        """Calculate ML system health score"""
        if not self.config.ENABLE_ML_MODELS:
            return 1.0  # Not applicable
            
        health = 0.5  # Base score
        
        try:
            # Check model performance
            performances = []
            for model_name in ['random_forest', 'gradient_boost', 'neural_network', 'xgboost']:
                perf = self.db.get_ml_model_performance(model_name)
                if perf and perf['total_predictions'] > 0:
                    performances.append(perf)
                    
            if performances:
                avg_accuracy = np.mean([p.get('accuracy', 0.5) for p in performances])
                health += min(0.3, (avg_accuracy - 0.5) * 0.6)
                
            # Check if models are trained
            if hasattr(self.ml_manager, '_is_trained') and self.ml_manager._is_trained:
                health += 0.2
                
        except Exception:
            health = 0.3  # Degraded performance
            
        return min(1.0, health)
        
    def _calculate_news_health(self) -> float:
        """Calculate news system health score"""
        health = 0.5  # Base score
        
        try:
            # Check if news analyzer is working
            if hasattr(self, 'news_analyzer'):
                health += 0.2
                
            # Check recent news fetch
            if not hasattr(self, '_recent_news_time'):
                self._recent_news_time = time.time()
            
            time_since_news = time.time() - self._recent_news_time
            if time_since_news < 3600:  # Within 1 hour
                health += 0.3
            elif time_since_news < 7200:  # Within 2 hours
                health += 0.1
                
        except Exception:
            health = 0.3  # Degraded performance
            
        return min(1.0, health)
        
    def _get_health_status_text(self, health_score: float) -> str:
        """Convert health score to text status"""
        if health_score >= 0.8:
            return "Excellent"
        elif health_score >= 0.6:
            return "Good"
        elif health_score >= 0.4:
            return "Fair"
        elif health_score >= 0.2:
            return "Poor"
        else:
            return "Critical"
    
    def _get_daily_trade_count(self) -> int:
        """Get number of trades today"""
        try:
            today = datetime.now().date()
            trades = self.db.execute_query(
                "SELECT COUNT(*) as count FROM trades WHERE DATE(timestamp) = ?",
                (today,)
            )
            return trades[0]['count'] if trades else 0
        except Exception:
            return 0
    
    def _calculate_error_rate(self) -> float:
        """Calculate recent error rate"""
        if not hasattr(self, '_recent_api_errors'):
            self._recent_api_errors = 0
        if not hasattr(self, '_total_api_calls'):
            self._total_api_calls = 1
        
        return self._recent_api_errors / max(1, self._total_api_calls)
    
    def _get_performance_summary(self) -> Dict:
        """Get performance summary"""
        try:
            daily_perf = self.db.get_daily_performance()
            return {
                'daily_pnl_percent': daily_perf.get('total_pnl_percent', 0.0),
                'win_rate': daily_perf.get('win_rate', 0.0),
                'total_trades': daily_perf.get('total_trades', 0),
                'kelly_fraction': daily_perf.get('kelly_fraction', 0.0)
            }
        except Exception:
            return {
                'daily_pnl_percent': 0.0,
                'win_rate': 0.0,
                'total_trades': 0,
                'kelly_fraction': 0.0
            }
    
    async def shutdown(self):
        """Gracefully shutdown the trading engine"""
        self.logger.info("🔄 거래 엔진 종료 중...")
        self.is_running = False
        
        try:
            # Send shutdown notification first
            if hasattr(self, 'notifier'):
                try:
                    await self.notifier.send_notification(
                        "🛑 **거래 시스템 종료**\n\n"
                        f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"가동 시간: {(datetime.now() - self.startup_time).total_seconds():.0f}초",
                        priority='high'
                    )
                except Exception as e:
                    self.logger.warning(f"종료 알림 전송 실패: {e}")
            
            # 1. Stop all background tasks first
            self.logger.info("📋 백그라운드 작업 중지 중...")
            
            # Stop ML model verification tasks
            if hasattr(self, 'ml_manager') and hasattr(self.ml_manager, 'verification_task'):
                if self.ml_manager.verification_task and not self.ml_manager.verification_task.done():
                    self.ml_manager.verification_task.cancel()
                    try:
                        await asyncio.wait_for(self.ml_manager.verification_task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
            
            # Stop news analyzer verification tasks
            if hasattr(self, 'news_analyzer') and hasattr(self.news_analyzer, 'verification_task'):
                if self.news_analyzer.verification_task and not self.news_analyzer.verification_task.done():
                    self.news_analyzer.verification_task.cancel()
                    try:
                        await asyncio.wait_for(self.news_analyzer.verification_task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
            
            # 2. Shutdown capital tracker (has background tasks)
            if hasattr(self, 'capital_tracker'):
                await self.capital_tracker.shutdown()
                self.logger.info("✅ 자본 추적 시스템 종료됨")
            
            # 3. Close any remaining positions (if configured to do so)
            if hasattr(self, 'position_manager') and hasattr(self, 'db'):
                try:
                    open_positions = self.db.get_open_positions()
                    if open_positions:
                        self.logger.info(f"⚠️ {len(open_positions)}개 열린 포지션 발견 (수동 정리 필요)")
                        # Note: 실제 포지션 자동 정리는 안전상 비활성화
                        # for position in open_positions:
                        #     await self.exchange.close_position(position['symbol'], '시스템 종료')
                except Exception as e:
                    self.logger.warning(f"포지션 확인 중 오류: {e}")
            
            # 4. Stop exchange WebSocket connections
            if hasattr(self, 'exchange'):
                # Cancel WebSocket task
                if hasattr(self.exchange, 'ws_task') and self.exchange.ws_task:
                    self.exchange.ws_task.cancel()
                    try:
                        await asyncio.wait_for(self.exchange.ws_task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                
                # Cancel WebSocket health monitor task
                if hasattr(self.exchange, 'ws_health_task') and self.exchange.ws_health_task:
                    self.exchange.ws_health_task.cancel()
                    try:
                        await asyncio.wait_for(self.exchange.ws_health_task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                
                self.logger.info("✅ 거래소 연결 종료됨")
            
            # 5. Shutdown notification system (last, as other components may send final messages)
            if hasattr(self, 'notifier'):
                await self.notifier.shutdown()
                self.logger.info("✅ 알림 시스템 종료됨")
            
            # 6. Close database connections
            if hasattr(self, 'db'):
                # Log final system event
                try:
                    self.db.log_system_event('INFO', 'System', '거래 시스템 정상 종료', {
                        'uptime_seconds': (datetime.now() - self.startup_time).total_seconds(),
                        'shutdown_time': datetime.now().isoformat()
                    })
                except Exception as e:
                    self.logger.warning(f"최종 로그 기록 실패: {e}")
                
                # Close DB connections if method exists
                if hasattr(self.db, 'close'):
                    self.db.close()
                self.logger.info("✅ 데이터베이스 연결 종료됨")
            
            self.logger.info("✅ 거래 엔진 종료 완료")
            
        except Exception as e:
            self.logger.error(f"❌ 거래 엔진 종료 중 오류: {e}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status"""
        try:
            capital_status = self.capital_tracker.get_current_status() if hasattr(self, 'capital_tracker') else {}
            
            return {
                'is_running': self.is_running,
                'startup_time': self.startup_time.isoformat(),
                'uptime_seconds': (datetime.now() - self.startup_time).total_seconds(),
                'symbols': self.config.SYMBOLS,
                'capital_tracking': capital_status,
                'ml_models_enabled': self.config.ENABLE_ML_MODELS,
                'websocket_connected': getattr(self.exchange, 'ws_connected', False),
                'total_positions': len(self.db.get_open_positions()) if hasattr(self, 'db') else 0,
                'performance': self._get_performance_summary()
            }
        except Exception as e:
            self.logger.error(f"시스템 상태 조회 오류: {e}")
            return {'error': str(e)}
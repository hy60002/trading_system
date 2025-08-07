"""
Enhanced ML Model Manager
Machine learning model management with real-time learning and performance tracking
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any

# Import modular ML system
from .ml_models.model_manager import ModelManager

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..database.db_manager import EnhancedDatabaseManager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager


class EnhancedMLModelManager:
    """Machine learning model management with real-time learning and performance tracking"""
    
    def __init__(self, config: TradingConfig, db: EnhancedDatabaseManager):
        self.config = config
        self.db = db
        self.logger = logging.getLogger(__name__)
        
        # 🔍 Prediction verification system (backward compatibility)
        self.pending_predictions = {}  # 검증 대기 중인 예측들
        self.verification_task = None
        self._is_trained = False
        
        # Initialize the new modular model manager
        self.model_manager = ModelManager(config, db)
        
        if hasattr(config, 'ENABLE_ML_MODELS') and config.ENABLE_ML_MODELS:
            # The new ModelManager handles initialization internally
            pass
    
    async def initialize(self):
        """Initialize ML models (async compatibility)"""
        try:
            # Initialize the new model manager
            success = await self.model_manager.initialize()
            
            if success:
                self._is_trained = any(model.is_trained for model in self.model_manager.models.values())
                
                # Start prediction verification task for backward compatibility
                self.verification_task = asyncio.create_task(self._prediction_verification_loop())
                self.logger.info("🔍 ML 예측 검증 시스템 시작")
                
                return True
            else:
                self.logger.error("모델 매니저 초기화 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"ML 모델 초기화 오류: {e}")
            return False
    
    # === Backward Compatibility Interface ===
    
    @property 
    def models(self):
        """Backward compatibility: Access to models dict"""
        return {name: model.model for name, model in self.model_manager.models.items() if model.model}
    
    @property
    def feature_names(self):
        """Backward compatibility: Access to feature names"""
        # Get feature names from any trained model
        for model in self.model_manager.models.values():
            if model.feature_names:
                return model.feature_names
        return []
    
    @property
    def model_performance(self):
        """Backward compatibility: Access to model performance"""
        performance = {}
        for name, model in self.model_manager.models.items():
            if model.is_trained:
                performance[name] = model.performance_metrics
        return performance
    
    async def predict(self, features: Dict[str, Any], symbol: str = None) -> Dict[str, Any]:
        """Make ensemble prediction using the new system"""
        try:
            result = await self.model_manager.predict(features, symbol)
            
            # Store for verification (backward compatibility)
            if result['success'] and symbol:
                prediction_id = f"{symbol}_{datetime.now().timestamp()}"
                self.pending_predictions[prediction_id] = {
                    'symbol': symbol,
                    'features': features,
                    'prediction': result['prediction'],
                    'confidence': result['confidence'],
                    'timestamp': datetime.now(),
                    'verified': False
                }
            
            return result
            
        except Exception as e:
            self.logger.error(f"예측 실패: {e}")
            return {
                'success': False,
                'prediction': 0.0,
                'confidence': 0.1,
                'error': str(e)
            }
    
    async def train_models(self, training_data: pd.DataFrame, target_column: str = 'target') -> Dict[str, Any]:
        """Train all models using the new system"""
        try:
            result = await self.model_manager.train_models(training_data, target_column)
            
            if result['success']:
                self._is_trained = True
                self.logger.info(f"✅ 모델 훈련 완료 - {result['trained_models']}/{result['total_models']} 성공")
            
            return result
            
        except Exception as e:
            self.logger.error(f"모델 훈련 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_model_summary(self) -> Dict[str, Any]:
        """Get comprehensive model summary"""
        return self.model_manager.get_model_summary()
    
    def get_prediction_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get prediction history"""
        return self.model_manager.get_prediction_history(limit)
    
    def get_feature_importance(self, model_name: str = None) -> Dict[str, float]:
        """Get feature importance from specific model or ensemble"""
        try:
            if model_name and model_name in self.model_manager.models:
                model = self.model_manager.models[model_name]
                if hasattr(model, 'get_feature_importance'):
                    return model.get_feature_importance()
            
            # Return combined feature importance from all models
            combined_importance = {}
            total_weight = 0
            
            for name, model in self.model_manager.models.items():
                if model.is_trained and hasattr(model, 'get_feature_importance'):
                    importance = model.get_feature_importance()
                    weight = self.model_manager.ensemble_weights.get(name, 0.25)
                    
                    for feature, value in importance.items():
                        if isinstance(value, (int, float)):  # Skip non-numeric values
                            if feature not in combined_importance:
                                combined_importance[feature] = 0
                            combined_importance[feature] += value * weight
                    
                    total_weight += weight
            
            # Normalize by total weight
            if total_weight > 0:
                for feature in combined_importance:
                    combined_importance[feature] /= total_weight
            
            # Sort by importance
            return dict(sorted(combined_importance.items(), key=lambda x: x[1], reverse=True))
            
        except Exception as e:
            self.logger.error(f"특성 중요도 계산 실패: {e}")
            return {}
    
    async def cleanup(self):
        """Cleanup ML manager"""
        try:
            # Cancel verification task
            if self.verification_task:
                self.verification_task.cancel()
                try:
                    await self.verification_task
                except asyncio.CancelledError:
                    pass
            
            # Cleanup the model manager
            await self.model_manager.cleanup()
            
            self.logger.info("ML 매니저 정리 완료")
            
        except Exception as e:
            self.logger.error(f"ML 매니저 정리 중 오류: {e}")
    
    # === Backward Compatibility Methods ===
    
    async def _prediction_verification_loop(self):
        """Prediction verification loop for backward compatibility"""
        while True:
            try:
                await asyncio.sleep(300)  # 5분마다 검증
                
                # Clean old predictions
                current_time = datetime.now()
                to_remove = []
                
                for pred_id, pred_data in self.pending_predictions.items():
                    if (current_time - pred_data['timestamp']).total_seconds() > 3600:  # 1시간 후 제거
                        to_remove.append(pred_id)
                
                for pred_id in to_remove:
                    del self.pending_predictions[pred_id]
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"예측 검증 루프 오류: {e}")
                await asyncio.sleep(60)
    
    def save_models(self):
        """Save all models (backward compatibility)"""
        try:
            for model in self.model_manager.models.values():
                if model.is_trained:
                    model.save_model()
            self.logger.info("모든 모델 저장 완료")
        except Exception as e:
            self.logger.error(f"모델 저장 실패: {e}")
    
    def is_trained(self) -> bool:
        """Check if any model is trained"""
        return self._is_trained and any(model.is_trained for model in self.model_manager.models.values())
    
    # Legacy methods for compatibility
    def _create_features(self, market_data: Dict[str, Any]) -> np.ndarray:
        """Create features from market data (legacy compatibility)"""
        # This method is now handled by individual models in prepare_features
        features = []
        feature_names = [
            'returns_1', 'returns_5', 'returns_20',
            'volume_ratio', 'atr_ratio', 'bb_position',
            'rsi', 'macd_signal', 'adx', 'obv_slope',
            'price_ma_ratio', 'volume_ma_ratio',
            'trend_strength', 'volatility_ratio'
        ]
        
        for name in feature_names:
            features.append(market_data.get(name, 0.0))
        
        return np.array(features).reshape(1, -1)
    
    def get_ensemble_prediction(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Get ensemble prediction (sync version for backward compatibility)"""
        try:
            # Convert to async call
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.model_manager.predict(features))
                    return future.result()
            else:
                return asyncio.run(self.model_manager.predict(features))
        except Exception as e:
            self.logger.error(f"동기 예측 실패: {e}")
            return {
                'success': False,
                'prediction': 0.0,
                'confidence': 0.1,
                'error': str(e)
            }
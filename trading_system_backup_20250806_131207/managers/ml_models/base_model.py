"""
Base Model Class
모든 ML 모델의 기본 클래스
"""

import logging
import numpy as np
import pandas as pd
import joblib
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# ML libraries
try:
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Import handling for both direct and package imports
try:
    from ...config.config import TradingConfig
    from ...database.db_manager import EnhancedDatabaseManager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager


class BaseModel(ABC):
    """모든 ML 모델의 기본 클래스"""
    
    def __init__(self, model_name: str, config: TradingConfig, db: EnhancedDatabaseManager):
        self.model_name = model_name
        self.config = config
        self.db = db
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{model_name}")
        
        # 모델 상태
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.last_train_time = None
        
        # 성능 추적
        self.performance_metrics = {
            'mse': float('inf'),
            'mae': float('inf'),
            'r2': -float('inf'),
            'accuracy': 0.0,
            'prediction_count': 0,
            'last_update': None
        }
        
        # 특성 정보
        self.feature_names = []
        self.feature_importance = {}
        
        # 모델 파일 경로
        self.model_dir = "models"
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
        
        self.model_path = os.path.join(self.model_dir, f"{self.model_name}_model.pkl")
        self.scaler_path = os.path.join(self.model_dir, f"{self.model_name}_scaler.pkl")
    
    @abstractmethod
    def _create_model(self) -> Any:
        """모델 생성 (각 모델에서 구현)"""
        pass
    
    @abstractmethod
    def get_model_params(self) -> Dict[str, Any]:
        """모델 파라미터 반환 (각 모델에서 구현)"""
        pass
    
    def initialize(self) -> bool:
        """모델 초기화"""
        try:
            if ML_AVAILABLE:
                # 저장된 모델 로드 시도
                if self.load_model():
                    self.logger.info(f"✅ {self.model_name} 모델 로드 완료")
                    return True
                else:
                    # 새 모델 생성
                    self.model = self._create_model()
                    self.scaler = StandardScaler()
                    self.logger.info(f"🆕 {self.model_name} 새 모델 생성 완료")
                    return True
            else:
                self.logger.warning(f"❌ ML 라이브러리 없음 - {self.model_name} 모델 비활성화")
                return False
        except Exception as e:
            self.logger.error(f"❌ {self.model_name} 모델 초기화 실패: {e}")
            return False
    
    def prepare_features(self, data: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """특성 준비 및 전처리"""
        try:
            # 기본 특성들
            features = []
            feature_names = []
            
            # 기술적 지표들
            if 'rsi' in data.columns:
                features.append(data['rsi'].values)
                feature_names.append('rsi')
            
            if 'macd' in data.columns:
                features.append(data['macd'].values)
                feature_names.append('macd')
            
            if 'bb_position' in data.columns:
                features.append(data['bb_position'].values)
                feature_names.append('bb_position')
            
            if 'volume' in data.columns:
                features.append(data['volume'].values)
                feature_names.append('volume')
            
            # 가격 기반 특성
            if 'close' in data.columns:
                close_prices = data['close'].values
                if len(close_prices) > 1:
                    price_change = np.diff(close_prices, prepend=close_prices[0])
                    features.append(price_change)
                    feature_names.append('price_change')
            
            # 특성 배열 생성
            if features:
                X = np.column_stack(features)
                self.feature_names = feature_names
                return X, feature_names
            else:
                # 최소한의 특성이라도 생성
                X = np.random.random((len(data), 1))
                feature_names = ['dummy_feature']
                self.feature_names = feature_names
                return X, feature_names
                
        except Exception as e:
            self.logger.error(f"특성 준비 실패: {e}")
            # 더미 데이터 반환
            X = np.random.random((len(data), 1))
            feature_names = ['dummy_feature']
            return X, feature_names
    
    def train(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """모델 훈련"""
        try:
            if not ML_AVAILABLE or self.model is None:
                return {'success': False, 'error': 'Model not available'}
            
            # 데이터 검증
            if len(X) < 10:
                return {'success': False, 'error': 'Insufficient training data'}
            
            # 데이터 스케일링
            X_scaled = self.scaler.fit_transform(X)
            
            # 모델 훈련
            self.model.fit(X_scaled, y)
            self.is_trained = True
            self.last_train_time = datetime.now()
            
            # 성능 평가
            y_pred = self.model.predict(X_scaled)
            metrics = self._calculate_metrics(y, y_pred)
            self.performance_metrics.update(metrics)
            self.performance_metrics['last_update'] = datetime.now()
            
            # 특성 중요도 계산 (가능한 경우)
            if hasattr(self.model, 'feature_importances_'):
                self.feature_importance = dict(zip(
                    self.feature_names, 
                    self.model.feature_importances_
                ))
            
            self.logger.info(f"✅ {self.model_name} 훈련 완료 - R²: {metrics['r2']:.3f}")
            return {'success': True, 'metrics': metrics}
            
        except Exception as e:
            self.logger.error(f"모델 훈련 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict(self, X: np.ndarray) -> Dict[str, Any]:
        """예측 수행"""
        try:
            if not self.is_trained or self.model is None:
                return {'success': False, 'error': 'Model not trained'}
            
            # 데이터 스케일링
            X_scaled = self.scaler.transform(X)
            
            # 예측
            prediction = self.model.predict(X_scaled)
            
            # 신뢰도 계산 (가능한 경우)
            confidence = self._calculate_prediction_confidence(X_scaled)
            
            # 예측 카운트 증가
            self.performance_metrics['prediction_count'] += 1
            
            return {
                'success': True,
                'prediction': float(prediction[0]) if len(prediction) == 1 else prediction.tolist(),
                'confidence': confidence,
                'model_name': self.model_name
            }
            
        except Exception as e:
            self.logger.error(f"예측 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """성능 메트릭 계산"""
        try:
            metrics = {
                'mse': mean_squared_error(y_true, y_pred),
                'mae': mean_absolute_error(y_true, y_pred),
                'r2': r2_score(y_true, y_pred)
            }
            
            # 정확도 계산 (분류 문제로 간주)
            threshold = 0.01  # 1% 이내면 정확한 예측으로 간주
            accurate_predictions = np.abs(y_true - y_pred) <= threshold
            metrics['accuracy'] = np.mean(accurate_predictions)
            
            return metrics
        except Exception as e:
            self.logger.debug(f"메트릭 계산 실패: {e}")
            return {'mse': float('inf'), 'mae': float('inf'), 'r2': -1.0, 'accuracy': 0.0}
    
    def _calculate_prediction_confidence(self, X_scaled: np.ndarray) -> float:
        """예측 신뢰도 계산"""
        try:
            # 기본적인 신뢰도 계산 (모델 성능 기반)
            r2_score = self.performance_metrics.get('r2', -1.0)
            base_confidence = max(0.0, min(1.0, (r2_score + 1.0) / 2.0))  # -1~1을 0~1로 변환
            
            return base_confidence
        except Exception:
            return 0.5  # 기본 신뢰도
    
    def save_model(self) -> bool:
        """모델 저장"""
        try:
            if self.model is not None:
                joblib.dump(self.model, self.model_path)
            
            if self.scaler is not None:
                joblib.dump(self.scaler, self.scaler_path)
            
            self.logger.info(f"✅ {self.model_name} 모델 저장 완료")
            return True
        except Exception as e:
            self.logger.error(f"모델 저장 실패: {e}")
            return False
    
    def load_model(self) -> bool:
        """모델 로드"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.is_trained = True
                self.last_train_time = datetime.fromtimestamp(os.path.getmtime(self.model_path))
                return True
            return False
        except Exception as e:
            self.logger.debug(f"모델 로드 실패: {e}")
            return False
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 반환"""
        return {
            'model_name': self.model_name,
            'is_trained': self.is_trained,
            'last_train_time': self.last_train_time,
            'metrics': self.performance_metrics.copy(),
            'feature_count': len(self.feature_names),
            'feature_names': self.feature_names.copy(),
            'feature_importance': self.feature_importance.copy() if self.feature_importance else {}
        }
    
    def should_retrain(self) -> bool:
        """재훈련이 필요한지 확인"""
        if not self.is_trained:
            return True
        
        if self.last_train_time is None:
            return True
        
        # 설정된 재훈련 주기 확인
        hours_since_train = (datetime.now() - self.last_train_time).total_seconds() / 3600
        retrain_hours = getattr(self.config, 'ML_RETRAIN_HOURS', 24)
        
        return hours_since_train >= retrain_hours
    
    def reset_model(self):
        """모델 초기화"""
        self.model = self._create_model()
        self.scaler = StandardScaler()
        self.is_trained = False
        self.last_train_time = None
        self.performance_metrics = {
            'mse': float('inf'),
            'mae': float('inf'), 
            'r2': -float('inf'),
            'accuracy': 0.0,
            'prediction_count': 0,
            'last_update': None
        }
        self.feature_importance = {}
        self.logger.info(f"🔄 {self.model_name} 모델 초기화 완료")
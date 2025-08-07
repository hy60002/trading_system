"""
Model Manager
모든 ML 모델을 통합 관리하는 매니저 클래스
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any

from .base_model import BaseModel
from .ensemble_model import EnsembleModel
from .neural_model import NeuralModel
from .tree_model import TreeModel

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


class ModelManager:
    """ML 모델들을 통합 관리하는 매니저"""
    
    def __init__(self, config: TradingConfig, db: EnhancedDatabaseManager):
        self.config = config
        self.db = db
        self.logger = logging.getLogger(__name__)
        
        # 모델 인스턴스들
        self.models: Dict[str, BaseModel] = {}
        
        # 앙상블 가중치
        self.ensemble_weights = {
            'random_forest': 0.3,
            'gradient_boosting': 0.25,
            'xgboost': 0.25,
            'neural_network': 0.2
        }
        
        # 성능 추적
        self.model_performance = {}
        self.prediction_history = []
        
        # 재훈련 스케줄러
        self.retrain_task = None
        
    async def initialize(self) -> bool:
        """모델 매니저 초기화"""
        try:
            # 기본 모델들 생성
            await self._create_default_models()
            
            # 모델들 초기화
            initialized_models = []
            for name, model in self.models.items():
                if model.initialize():
                    initialized_models.append(name)
                    self.logger.info(f"✅ {name} 모델 초기화 완료")
                else:
                    self.logger.warning(f"⚠️ {name} 모델 초기화 실패")
            
            if initialized_models:
                # 재훈련 스케줄러 시작
                self.retrain_task = asyncio.create_task(self._retrain_scheduler())
                self.logger.info(f"🚀 모델 매니저 초기화 완료 - {len(initialized_models)}개 모델 활성화")
                return True
            else:
                self.logger.error("❌ 사용 가능한 모델이 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"모델 매니저 초기화 실패: {e}")
            return False
    
    async def _create_default_models(self):
        """기본 모델들 생성"""
        try:
            # 앙상블 모델들
            self.models['random_forest'] = EnsembleModel(
                'random_forest', self.config, self.db, 'random_forest'
            )
            self.models['gradient_boosting'] = EnsembleModel(
                'gradient_boosting', self.config, self.db, 'gradient_boosting'
            )
            
            # 트리 모델들
            self.models['xgboost'] = TreeModel(
                'xgboost', self.config, self.db, 'xgboost'
            )
            
            # 신경망 모델
            self.models['neural_network'] = NeuralModel(
                'neural_network', self.config, self.db, (100, 50)
            )
            
            self.logger.info(f"기본 모델 {len(self.models)}개 생성 완료")
            
        except Exception as e:
            self.logger.error(f"기본 모델 생성 실패: {e}")
    
    async def predict(self, features: Dict[str, Any], symbol: str = None) -> Dict[str, Any]:
        """앙상블 예측 수행"""
        try:
            # 특성 데이터 준비
            feature_df = pd.DataFrame([features])
            
            # 개별 모델 예측들
            predictions = {}
            confidences = {}
            successful_models = []
            
            for name, model in self.models.items():
                if model.is_trained:
                    try:
                        # 특성 준비
                        X, feature_names = model.prepare_features(feature_df)
                        
                        # 예측 수행
                        result = model.predict(X)
                        
                        if result['success']:
                            predictions[name] = result['prediction']
                            confidences[name] = result['confidence']
                            successful_models.append(name)
                            
                    except Exception as e:
                        self.logger.debug(f"{name} 모델 예측 실패: {e}")
                        continue
            
            if not successful_models:
                # 모델이 없으면 기술적 분석 기반 예측 사용
                return self._get_technical_analysis_prediction(features, symbol)
            
            # 앙상블 예측 계산
            ensemble_prediction = self._calculate_ensemble_prediction(
                predictions, confidences, successful_models
            )
            
            # 예측 히스토리 저장
            prediction_record = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'individual_predictions': predictions,
                'ensemble_prediction': ensemble_prediction['prediction'],
                'confidence': ensemble_prediction['confidence'],
                'models_used': successful_models
            }
            self.prediction_history.append(prediction_record)
            
            # 히스토리 크기 제한
            if len(self.prediction_history) > 1000:
                self.prediction_history = self.prediction_history[-1000:]
            
            return {
                'success': True,
                'prediction': ensemble_prediction['prediction'],
                'confidence': ensemble_prediction['confidence'],
                'individual_predictions': predictions,
                'models_used': successful_models,
                'ensemble_weights': {k: v for k, v in self.ensemble_weights.items() if k in successful_models}
            }
            
        except Exception as e:
            self.logger.error(f"앙상블 예측 실패: {e}")
            return self._get_default_prediction()
    
    def _calculate_ensemble_prediction(self, predictions: Dict[str, float], 
                                     confidences: Dict[str, float], 
                                     successful_models: List[str]) -> Dict[str, float]:
        """앙상블 예측 계산"""
        try:
            # 가중 평균 계산
            weighted_sum = 0.0
            weight_sum = 0.0
            
            for model_name in successful_models:
                if model_name in predictions and model_name in self.ensemble_weights:
                    # 신뢰도를 고려한 가중치
                    base_weight = self.ensemble_weights[model_name]
                    confidence_weight = confidences.get(model_name, 0.5)
                    
                    # 성능 기반 가중치 조정
                    performance_weight = self._get_performance_weight(model_name)
                    
                    final_weight = base_weight * confidence_weight * performance_weight
                    
                    weighted_sum += predictions[model_name] * final_weight
                    weight_sum += final_weight
            
            if weight_sum > 0:
                ensemble_pred = weighted_sum / weight_sum
                
                # 앙상블 신뢰도 계산
                avg_confidence = np.mean([confidences[name] for name in successful_models])
                model_agreement = self._calculate_model_agreement(predictions, successful_models)
                
                ensemble_confidence = 0.7 * avg_confidence + 0.3 * model_agreement
                
                return {
                    'prediction': float(ensemble_pred),
                    'confidence': min(1.0, max(0.0, ensemble_confidence))
                }
            else:
                # 가중치 합이 0이면 단순 평균
                simple_avg = np.mean(list(predictions.values()))
                avg_confidence = np.mean(list(confidences.values()))
                
                return {
                    'prediction': float(simple_avg),
                    'confidence': float(avg_confidence)
                }
                
        except Exception as e:
            self.logger.error(f"앙상블 계산 실패: {e}")
            return {'prediction': 0.0, 'confidence': 0.1}
    
    def _get_performance_weight(self, model_name: str) -> float:
        """모델 성능 기반 가중치 계산"""
        try:
            model = self.models.get(model_name)
            if not model or not model.is_trained:
                return 0.5
            
            # R² 스코어를 기반으로 가중치 계산
            r2_score = model.performance_metrics.get('r2', -1.0)
            
            # -1~1 범위를 0~1로 변환
            performance_weight = max(0.1, min(1.0, (r2_score + 1.0) / 2.0))
            
            return performance_weight
            
        except Exception:
            return 0.5
    
    def _calculate_model_agreement(self, predictions: Dict[str, float], 
                                 successful_models: List[str]) -> float:
        """모델 간 예측 일치도 계산"""
        try:
            if len(successful_models) < 2:
                return 1.0
            
            pred_values = [predictions[name] for name in successful_models]
            
            # 표준편차를 이용한 일치도 (낮을수록 일치도 높음)
            std_dev = np.std(pred_values)
            
            # 표준편차를 0~1 신뢰도로 변환
            agreement = max(0.0, 1.0 - min(1.0, std_dev))
            
            return agreement
            
        except Exception:
            return 0.5
    
    async def train_models(self, training_data: pd.DataFrame, 
                          target_column: str = 'target') -> Dict[str, Any]:
        """모든 모델 훈련"""
        try:
            if len(training_data) < 20:
                return {'success': False, 'error': 'Insufficient training data'}
            
            # 타겟 변수 분리
            y = training_data[target_column].values
            feature_data = training_data.drop(columns=[target_column])
            
            training_results = {}
            successful_trainings = 0
            
            for name, model in self.models.items():
                try:
                    self.logger.info(f"🔄 {name} 모델 훈련 시작...")
                    
                    # 특성 준비
                    X, feature_names = model.prepare_features(feature_data)
                    
                    # 모델 훈련
                    result = model.train(X, y)
                    training_results[name] = result
                    
                    if result['success']:
                        successful_trainings += 1
                        self.logger.info(f"✅ {name} 모델 훈련 완료")
                        
                        # 모델 저장
                        model.save_model()
                    else:
                        self.logger.warning(f"⚠️ {name} 모델 훈련 실패: {result.get('error', 'Unknown')}")
                        
                except Exception as e:
                    self.logger.error(f"{name} 모델 훈련 중 오류: {e}")
                    training_results[name] = {'success': False, 'error': str(e)}
            
            # 앙상블 가중치 업데이트
            self._update_ensemble_weights()
            
            return {
                'success': successful_trainings > 0,
                'trained_models': successful_trainings,
                'total_models': len(self.models),
                'training_results': training_results
            }
            
        except Exception as e:
            self.logger.error(f"모델 훈련 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def _update_ensemble_weights(self):
        """성능 기반 앙상블 가중치 업데이트"""
        try:
            total_performance = 0.0
            model_performances = {}
            
            # 각 모델의 성능 점수 계산
            for name, model in self.models.items():
                if model.is_trained:
                    r2_score = model.performance_metrics.get('r2', -1.0)
                    # R² 점수를 0~1 범위로 정규화
                    performance_score = max(0.1, (r2_score + 1.0) / 2.0)
                    model_performances[name] = performance_score
                    total_performance += performance_score
            
            # 가중치 정규화
            if total_performance > 0:
                for name in model_performances:
                    if name in self.ensemble_weights:
                        self.ensemble_weights[name] = model_performances[name] / total_performance
                
                self.logger.info(f"앙상블 가중치 업데이트: {self.ensemble_weights}")
            
        except Exception as e:
            self.logger.debug(f"가중치 업데이트 실패: {e}")
    
    async def _retrain_scheduler(self):
        """주기적 재훈련 스케줄러"""
        while True:
            try:
                await asyncio.sleep(3600)  # 1시간마다 확인
                
                # 재훈련이 필요한 모델들 확인
                models_to_retrain = []
                for name, model in self.models.items():
                    if model.should_retrain():
                        models_to_retrain.append(name)
                
                if models_to_retrain:
                    self.logger.info(f"🔄 재훈련 필요한 모델들: {models_to_retrain}")
                    # 실제 재훈련은 별도 데이터가 필요하므로 로그만 기록
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"재훈련 스케줄러 오류: {e}")
                await asyncio.sleep(300)  # 5분 후 재시도
    
    def _get_technical_analysis_prediction(self, features: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """기술적 분석 기반 예측 - ML 모델이 없을 때 사용"""
        try:
            # RSI 기반 예측
            rsi = features.get('rsi_14', 50.0)
            bb_position = features.get('bb_position', 0.5)
            macd_signal = features.get('macd_signal', 0.0)
            
            # 기술적 지표 기반 신호 생성
            signals = []
            
            # RSI 신호
            if rsi > 70:
                signals.append(-0.5)  # 과매수 = 매도 신호
            elif rsi < 30:
                signals.append(0.5)   # 과매도 = 매수 신호
            else:
                signals.append(0.0)   # 중립
                
            # 볼린저 밴드 신호
            if bb_position > 0.8:
                signals.append(-0.3)  # 상단 근처 = 매도 신호
            elif bb_position < 0.2:
                signals.append(0.3)   # 하단 근처 = 매수 신호
            else:
                signals.append(0.0)
                
            # MACD 신호
            if macd_signal > 0:
                signals.append(0.2)   # 상승 = 매수 신호
            else:
                signals.append(-0.2)  # 하락 = 매도 신호
            
            # 평균 신호 계산
            prediction = np.mean(signals) if signals else 0.0
            confidence = min(0.8, abs(prediction) + 0.4)  # 기술적 분석의 기본 신뢰도
            
            return {
                'success': True,
                'prediction': float(prediction),
                'confidence': float(confidence),
                'individual_predictions': {
                    'rsi': signals[0] if len(signals) > 0 else 0.0,
                    'bb': signals[1] if len(signals) > 1 else 0.0,
                    'macd': signals[2] if len(signals) > 2 else 0.0
                },
                'models_used': ['technical_analysis'],
                'features_used': ['rsi_14', 'bb_position', 'macd_signal']
            }
            
        except Exception as e:
            self.logger.error(f"기술적 분석 예측 실패: {e}")
            return self._get_default_prediction()

    def _get_default_prediction(self) -> Dict[str, Any]:
        """최후의 기본 예측값 반환"""
        return {
            'success': True,  # 매매 시스템 중단 방지
            'prediction': 0.0,  # 중립 예측
            'confidence': 0.3,  # 낮은 신뢰도
            'individual_predictions': {},
            'models_used': ['fallback'],
            'error': 'Using fallback prediction - all methods failed'
        }
    
    def get_model_summary(self) -> Dict[str, Any]:
        """모든 모델의 요약 정보"""
        summary = {
            'total_models': len(self.models),
            'trained_models': sum(1 for m in self.models.values() if m.is_trained),
            'ensemble_weights': self.ensemble_weights.copy(),
            'models': {}
        }
        
        for name, model in self.models.items():
            summary['models'][name] = model.get_performance_summary()
        
        return summary
    
    def get_prediction_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """예측 히스토리 반환"""
        return self.prediction_history[-limit:] if self.prediction_history else []
    
    async def cleanup(self):
        """매니저 정리"""
        try:
            if self.retrain_task:
                self.retrain_task.cancel()
                try:
                    await self.retrain_task
                except asyncio.CancelledError:
                    pass
            
            # 모든 모델 저장
            for model in self.models.values():
                if model.is_trained:
                    model.save_model()
            
            self.logger.info("모델 매니저 정리 완료")
            
        except Exception as e:
            self.logger.error(f"매니저 정리 중 오류: {e}")
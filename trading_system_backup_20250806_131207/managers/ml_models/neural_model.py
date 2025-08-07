"""
Neural Model
신경망 모델 (MLP, Deep Learning 등)
"""

import numpy as np
from typing import Dict, Any, Tuple
from .base_model import BaseModel

try:
    from sklearn.neural_network import MLPRegressor
    from sklearn.model_selection import validation_curve
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class NeuralModel(BaseModel):
    """신경망 기반 모델 클래스"""
    
    def __init__(self, model_name: str, config, db, hidden_layers: Tuple[int, ...] = (100, 50)):
        super().__init__(model_name, config, db)
        self.hidden_layers = hidden_layers
        self.training_history = []
        
    def _create_model(self):
        """신경망 모델 생성"""
        if not ML_AVAILABLE:
            return None
            
        return MLPRegressor(
            hidden_layer_sizes=self.hidden_layers,
            activation='relu',
            solver='adam',
            alpha=0.001,
            learning_rate='adaptive',
            learning_rate_init=0.001,
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=10,
            random_state=42
        )
    
    def get_model_params(self) -> Dict[str, Any]:
        """모델 파라미터 반환"""
        return {
            'model_type': 'neural_network',
            'hidden_layers': self.hidden_layers,
            'sklearn_params': self.model.get_params() if self.model else {},
            'training_iterations': getattr(self.model, 'n_iter_', 0) if self.model else 0
        }
    
    def train(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """신경망 모델 훈련"""
        try:
            # 기본 훈련 수행
            result = super().train(X, y)
            
            if result['success'] and self.model:
                # 훈련 히스토리 저장
                training_info = {
                    'n_iter': getattr(self.model, 'n_iter_', 0),
                    'loss': getattr(self.model, 'loss_', float('inf')),
                    'validation_scores': getattr(self.model, 'validation_scores_', []),
                    'training_time': result.get('training_time', 0)
                }
                self.training_history.append(training_info)
                
                # 수렴 여부 확인
                if hasattr(self.model, 'n_iter_') and hasattr(self.model, 'max_iter'):
                    converged = self.model.n_iter_ < self.model.max_iter
                    result['converged'] = converged
                    
                    if not converged:
                        self.logger.warning(f"⚠️ {self.model_name} 모델이 수렴하지 않았습니다")
                
                result['training_info'] = training_info
            
            return result
            
        except Exception as e:
            self.logger.error(f"신경망 훈련 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def optimize_architecture(self, X, y, max_layers: int = 3, max_neurons: int = 200) -> Dict[str, Any]:
        """신경망 구조 최적화"""
        try:
            if not ML_AVAILABLE or len(X) < 100:  # 충분한 데이터 필요
                return {'success': False, 'error': 'Insufficient data for architecture optimization'}
            
            best_score = float('inf')
            best_architecture = self.hidden_layers
            
            # 다양한 구조 테스트
            architectures_to_test = [
                (50,),
                (100,),
                (100, 50),
                (100, 100),
                (200, 100),
                (100, 50, 25),
                (200, 100, 50)
            ]
            
            results = []
            
            for architecture in architectures_to_test:
                try:
                    # 임시 모델 생성
                    temp_model = MLPRegressor(
                        hidden_layer_sizes=architecture,
                        activation='relu',
                        solver='adam',
                        alpha=0.001,
                        max_iter=200,  # 빠른 테스트를 위해 줄임
                        early_stopping=True,
                        validation_fraction=0.2,
                        random_state=42
                    )
                    
                    # 데이터 스케일링
                    X_scaled = self.scaler.fit_transform(X)
                    
                    # 훈련 및 평가
                    temp_model.fit(X_scaled, y)
                    score = temp_model.loss_
                    
                    results.append({
                        'architecture': architecture,
                        'score': score,
                        'n_iter': temp_model.n_iter_,
                        'converged': temp_model.n_iter_ < temp_model.max_iter
                    })
                    
                    if score < best_score:
                        best_score = score
                        best_architecture = architecture
                    
                except Exception as e:
                    self.logger.debug(f"구조 {architecture} 테스트 실패: {e}")
                    continue
            
            # 최적 구조로 업데이트
            if best_architecture != self.hidden_layers:
                self.hidden_layers = best_architecture
                self.model = self._create_model()
                
                self.logger.info(f"✅ {self.model_name} 최적 구조: {best_architecture}")
            
            return {
                'success': True,
                'best_architecture': best_architecture,
                'best_score': best_score,
                'all_results': results
            }
            
        except Exception as e:
            self.logger.error(f"구조 최적화 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def analyze_learning_curve(self, X, y) -> Dict[str, Any]:
        """학습 곡선 분석"""
        try:
            if not ML_AVAILABLE:
                return {'success': False, 'error': 'ML libraries not available'}
            
            # 데이터 스케일링
            X_scaled = self.scaler.fit_transform(X)
            
            # 다양한 max_iter 값에 대해 검증 곡선 생성
            param_range = [50, 100, 200, 300, 500]
            
            train_scores, validation_scores = validation_curve(
                MLPRegressor(
                    hidden_layer_sizes=self.hidden_layers,
                    activation='relu',
                    solver='adam',
                    alpha=0.001,
                    early_stopping=False,  # 곡선 분석을 위해 비활성화
                    random_state=42
                ),
                X_scaled, y,
                param_name='max_iter',
                param_range=param_range,
                cv=3,
                scoring='neg_mean_squared_error',
                n_jobs=-1
            )
            
            # 결과 정리
            train_mean = -train_scores.mean(axis=1)
            train_std = train_scores.std(axis=1)
            val_mean = -validation_scores.mean(axis=1)
            val_std = validation_scores.std(axis=1)
            
            return {
                'success': True,
                'param_range': param_range,
                'train_scores': {
                    'mean': train_mean.tolist(),
                    'std': train_std.tolist()
                },
                'validation_scores': {
                    'mean': val_mean.tolist(),
                    'std': val_std.tolist()
                },
                'optimal_iterations': param_range[np.argmin(val_mean)]
            }
            
        except Exception as e:
            self.logger.error(f"학습 곡선 분석 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_prediction_confidence(self, X_scaled):
        """신경망 모델의 예측 신뢰도 계산"""
        try:
            # 기본 신뢰도
            base_confidence = super()._calculate_prediction_confidence(X_scaled)
            
            # 신경망 특성을 활용한 신뢰도 조정
            if hasattr(self.model, 'loss_'):
                # 훈련 손실을 기반으로 신뢰도 조정
                loss = self.model.loss_
                
                # 손실이 낮을수록 신뢰도 높음
                loss_confidence = max(0.0, 1.0 - min(1.0, loss / 10.0))
                
                # 수렴 여부도 고려
                converged = True
                if hasattr(self.model, 'n_iter_') and hasattr(self.model, 'max_iter'):
                    converged = self.model.n_iter_ < self.model.max_iter
                
                convergence_bonus = 0.1 if converged else -0.1
                
                final_confidence = 0.6 * base_confidence + 0.3 * loss_confidence + convergence_bonus
                return min(1.0, max(0.0, final_confidence))
            
            return base_confidence
            
        except Exception as e:
            self.logger.debug(f"신뢰도 계산 실패: {e}")
            return 0.5
    
    def get_network_info(self) -> Dict[str, Any]:
        """신경망 정보 반환"""
        info = self.get_performance_summary()
        
        if self.model:
            info['network_info'] = {
                'hidden_layers': self.hidden_layers,
                'n_layers': len(self.hidden_layers) + 2,  # hidden + input + output
                'total_parameters': self._estimate_parameters(),
                'activation': getattr(self.model, 'activation', 'relu'),
                'solver': getattr(self.model, 'solver', 'adam'),
                'learning_rate_init': getattr(self.model, 'learning_rate_init', 0.001)
            }
            
            if hasattr(self.model, 'n_iter_'):
                info['training_info'] = {
                    'iterations': self.model.n_iter_,
                    'loss': getattr(self.model, 'loss_', None),
                    'converged': self.model.n_iter_ < getattr(self.model, 'max_iter', 500)
                }
        
        info['training_history'] = self.training_history
        
        return info
    
    def _estimate_parameters(self) -> int:
        """신경망 파라미터 수 추정"""
        try:
            if not self.feature_names:
                return 0
            
            input_size = len(self.feature_names)
            total_params = 0
            
            prev_size = input_size
            for hidden_size in self.hidden_layers:
                total_params += prev_size * hidden_size + hidden_size  # weights + biases
                prev_size = hidden_size
            
            # 출력층
            total_params += prev_size * 1 + 1  # output layer weights + bias
            
            return total_params
            
        except Exception:
            return 0
    
    def reset_training_history(self):
        """훈련 히스토리 초기화"""
        self.training_history = []
        self.logger.info(f"🔄 {self.model_name} 훈련 히스토리 초기화")
"""
Ensemble Model
앙상블 모델 (Random Forest, Gradient Boosting 등)
"""

from typing import Dict, Any
from .base_model import BaseModel

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.model_selection import GridSearchCV
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class EnsembleModel(BaseModel):
    """앙상블 기반 모델 클래스"""
    
    def __init__(self, model_name: str, config, db, model_type: str = "random_forest"):
        super().__init__(model_name, config, db)
        self.model_type = model_type
        self.hyperparameters = self._get_default_hyperparameters()
    
    def _create_model(self):
        """앙상블 모델 생성"""
        if not ML_AVAILABLE:
            return None
        
        if self.model_type == "random_forest":
            return RandomForestRegressor(
                n_estimators=self.hyperparameters['n_estimators'],
                max_depth=self.hyperparameters['max_depth'],
                min_samples_split=self.hyperparameters['min_samples_split'],
                min_samples_leaf=self.hyperparameters['min_samples_leaf'],
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == "gradient_boosting":
            return GradientBoostingRegressor(
                n_estimators=self.hyperparameters['n_estimators'],
                max_depth=self.hyperparameters['max_depth'],
                learning_rate=self.hyperparameters['learning_rate'],
                subsample=self.hyperparameters['subsample'],
                random_state=42
            )
        else:
            # 기본값으로 Random Forest 사용
            return RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
    
    def _get_default_hyperparameters(self) -> Dict[str, Any]:
        """기본 하이퍼파라미터 반환"""
        if self.model_type == "random_forest":
            return {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 5,
                'min_samples_leaf': 2
            }
        elif self.model_type == "gradient_boosting":
            return {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8
            }
        else:
            return {'n_estimators': 100, 'max_depth': 10}
    
    def get_model_params(self) -> Dict[str, Any]:
        """모델 파라미터 반환"""
        return {
            'model_type': self.model_type,
            'hyperparameters': self.hyperparameters.copy(),
            'sklearn_params': self.model.get_params() if self.model else {}
        }
    
    def optimize_hyperparameters(self, X, y, cv_folds: int = 3) -> Dict[str, Any]:
        """하이퍼파라미터 최적화"""
        try:
            if not ML_AVAILABLE or len(X) < 50:  # 데이터가 부족하면 스킵
                return {'success': False, 'error': 'Insufficient data for optimization'}
            
            # 파라미터 그리드 정의
            if self.model_type == "random_forest":
                param_grid = {
                    'n_estimators': [50, 100, 200],
                    'max_depth': [5, 10, 15],
                    'min_samples_split': [2, 5, 10]
                }
            elif self.model_type == "gradient_boosting":
                param_grid = {
                    'n_estimators': [50, 100, 150],
                    'max_depth': [3, 6, 9],
                    'learning_rate': [0.05, 0.1, 0.2]
                }
            else:
                return {'success': False, 'error': 'Unknown model type'}
            
            # 그리드 서치 수행
            base_model = self._create_model()
            grid_search = GridSearchCV(
                base_model, 
                param_grid, 
                cv=cv_folds, 
                scoring='neg_mean_squared_error',
                n_jobs=-1
            )
            
            # 데이터 스케일링
            X_scaled = self.scaler.fit_transform(X)
            
            # 최적화 실행
            grid_search.fit(X_scaled, y)
            
            # 최적 파라미터로 업데이트
            self.hyperparameters.update(grid_search.best_params_)
            self.model = grid_search.best_estimator_
            self.is_trained = True
            
            self.logger.info(f"✅ {self.model_name} 하이퍼파라미터 최적화 완료")
            self.logger.info(f"최적 파라미터: {grid_search.best_params_}")
            
            return {
                'success': True,
                'best_params': grid_search.best_params_,
                'best_score': -grid_search.best_score_,  # 음수를 양수로 변환
                'cv_results': {
                    'mean_test_scores': grid_search.cv_results_['mean_test_score'].tolist(),
                    'std_test_scores': grid_search.cv_results_['std_test_score'].tolist()
                }
            }
            
        except Exception as e:
            self.logger.error(f"하이퍼파라미터 최적화 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """특성 중요도 반환"""
        if not self.is_trained or not hasattr(self.model, 'feature_importances_'):
            return {}
        
        try:
            importance_dict = {}
            for i, importance in enumerate(self.model.feature_importances_):
                feature_name = self.feature_names[i] if i < len(self.feature_names) else f'feature_{i}'
                importance_dict[feature_name] = float(importance)
            
            # 중요도 순으로 정렬
            sorted_importance = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
            return sorted_importance
            
        except Exception as e:
            self.logger.error(f"특성 중요도 계산 실패: {e}")
            return {}
    
    def _calculate_prediction_confidence(self, X_scaled):
        """앙상블 모델의 예측 신뢰도 계산"""
        try:
            # 기본 신뢰도
            base_confidence = super()._calculate_prediction_confidence(X_scaled)
            
            # 앙상블 특성을 활용한 신뢰도 조정
            if hasattr(self.model, 'estimators_'):
                # 개별 추정기들의 예측 분산을 이용
                predictions = []
                for estimator in self.model.estimators_[:10]:  # 처음 10개만 사용
                    pred = estimator.predict(X_scaled)
                    predictions.append(pred[0] if len(pred) == 1 else pred)
                
                if predictions:
                    pred_std = float(np.std(predictions))
                    # 분산이 낮을수록 신뢰도 높음
                    variance_confidence = max(0.0, 1.0 - pred_std)
                    
                    # 기본 신뢰도와 분산 기반 신뢰도의 가중 평균
                    final_confidence = 0.7 * base_confidence + 0.3 * variance_confidence
                    return min(1.0, max(0.0, final_confidence))
            
            return base_confidence
            
        except Exception as e:
            self.logger.debug(f"신뢰도 계산 실패: {e}")
            return 0.5
    
    def get_ensemble_stats(self) -> Dict[str, Any]:
        """앙상블 모델 통계"""
        stats = self.get_performance_summary()
        
        if self.is_trained and hasattr(self.model, 'n_estimators'):
            stats['ensemble_info'] = {
                'n_estimators': getattr(self.model, 'n_estimators', 0),
                'model_type': self.model_type,
                'oob_score': getattr(self.model, 'oob_score_', None) if hasattr(self.model, 'oob_score_') else None
            }
        
        return stats
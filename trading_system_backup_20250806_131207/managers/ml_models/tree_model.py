"""
Tree Model
트리 기반 모델 (XGBoost, LightGBM 등)
"""

import warnings
warnings.filterwarnings('ignore')

from typing import Dict, Any
from .base_model import BaseModel

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    from sklearn.tree import DecisionTreeRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class TreeModel(BaseModel):
    """트리 기반 모델 클래스"""
    
    def __init__(self, model_name: str, config, db, model_type: str = "xgboost"):
        super().__init__(model_name, config, db)
        self.model_type = model_type
        self.hyperparameters = self._get_default_hyperparameters()
        
    def _create_model(self):
        """트리 모델 생성"""
        if self.model_type == "xgboost" and XGBOOST_AVAILABLE:
            return xgb.XGBRegressor(
                n_estimators=self.hyperparameters['n_estimators'],
                max_depth=self.hyperparameters['max_depth'],
                learning_rate=self.hyperparameters['learning_rate'],
                subsample=self.hyperparameters['subsample'],
                colsample_bytree=self.hyperparameters['colsample_bytree'],
                random_state=42,
                n_jobs=-1,
                verbosity=0  # 로그 출력 억제
            )
        elif self.model_type == "decision_tree" and SKLEARN_AVAILABLE:
            return DecisionTreeRegressor(
                max_depth=self.hyperparameters['max_depth'],
                min_samples_split=self.hyperparameters['min_samples_split'],
                min_samples_leaf=self.hyperparameters['min_samples_leaf'],
                random_state=42
            )
        else:
            # 기본값으로 Decision Tree 사용 (sklearn 기반)
            if SKLEARN_AVAILABLE:
                return DecisionTreeRegressor(
                    max_depth=10,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=42
                )
            else:
                return None
    
    def _get_default_hyperparameters(self) -> Dict[str, Any]:
        """기본 하이퍼파라미터 반환"""
        if self.model_type == "xgboost":
            return {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8
            }
        elif self.model_type == "decision_tree":
            return {
                'max_depth': 10,
                'min_samples_split': 5,
                'min_samples_leaf': 2
            }
        else:
            return {'max_depth': 10}
    
    def get_model_params(self) -> Dict[str, Any]:
        """모델 파라미터 반환"""
        return {
            'model_type': self.model_type,
            'hyperparameters': self.hyperparameters.copy(),
            'xgboost_available': XGBOOST_AVAILABLE,
            'sklearn_available': SKLEARN_AVAILABLE,
            'model_params': self.model.get_params() if self.model else {}
        }
    
    def train(self, X, y) -> Dict[str, Any]:
        """트리 모델 훈련"""
        try:
            # XGBoost 전용 설정
            if self.model_type == "xgboost" and XGBOOST_AVAILABLE:
                # 조기 종료를 위한 검증 셋 분할
                if len(X) > 50:
                    split_idx = int(len(X) * 0.8)
                    X_train, X_val = X[:split_idx], X[split_idx:]
                    y_train, y_val = y[:split_idx], y[split_idx:]
                    
                    # 데이터 스케일링
                    X_train_scaled = self.scaler.fit_transform(X_train)
                    X_val_scaled = self.scaler.transform(X_val)
                    
                    # XGBoost 훈련 (조기 종료 포함)
                    self.model.fit(
                        X_train_scaled, y_train,
                        eval_set=[(X_val_scaled, y_val)],
                        early_stopping_rounds=10,
                        verbose=False
                    )
                    
                    self.is_trained = True
                    self.last_train_time = datetime.now()
                    
                    # 검증 셋으로 성능 평가
                    y_pred = self.model.predict(X_val_scaled)
                    metrics = self._calculate_metrics(y_val, y_pred)
                    
                else:
                    # 데이터가 적으면 기본 훈련
                    return super().train(X, y)
            else:
                # 다른 트리 모델들은 기본 훈련
                return super().train(X, y)
            
            # 성능 메트릭 업데이트
            self.performance_metrics.update(metrics)
            self.performance_metrics['last_update'] = datetime.now()
            
            # 특성 중요도 저장
            if hasattr(self.model, 'feature_importances_'):
                self.feature_importance = dict(zip(
                    self.feature_names,
                    self.model.feature_importances_
                ))
            
            self.logger.info(f"✅ {self.model_name} 훈련 완료 - R²: {metrics['r2']:.3f}")
            
            return {
                'success': True,
                'metrics': metrics,
                'early_stopping': True if self.model_type == "xgboost" else False,
                'n_estimators_used': getattr(self.model, 'best_ntree_limit', 
                                           getattr(self.model, 'n_estimators', 0))
            }
            
        except Exception as e:
            self.logger.error(f"트리 모델 훈련 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def optimize_hyperparameters(self, X, y) -> Dict[str, Any]:
        """하이퍼파라미터 최적화"""
        try:
            if len(X) < 50:
                return {'success': False, 'error': 'Insufficient data for optimization'}
            
            best_score = float('inf')
            best_params = self.hyperparameters.copy()
            
            # 파라미터 후보들
            if self.model_type == "xgboost":
                param_candidates = [
                    {'n_estimators': 50, 'max_depth': 3, 'learning_rate': 0.1},
                    {'n_estimators': 100, 'max_depth': 6, 'learning_rate': 0.1},
                    {'n_estimators': 150, 'max_depth': 6, 'learning_rate': 0.05},
                    {'n_estimators': 200, 'max_depth': 8, 'learning_rate': 0.05},
                ]
            else:
                param_candidates = [
                    {'max_depth': 5, 'min_samples_split': 5},
                    {'max_depth': 10, 'min_samples_split': 5},
                    {'max_depth': 15, 'min_samples_split': 10},
                    {'max_depth': 20, 'min_samples_split': 10},
                ]
            
            # 각 파라미터 조합 테스트
            for params in param_candidates:
                try:
                    # 임시 모델 생성
                    temp_hyperparams = self.hyperparameters.copy()
                    temp_hyperparams.update(params)
                    
                    temp_model = self._create_model_with_params(temp_hyperparams)
                    
                    # 데이터 분할
                    split_idx = int(len(X) * 0.8)
                    X_train, X_val = X[:split_idx], X[split_idx:]
                    y_train, y_val = y[:split_idx], y[split_idx:]
                    
                    # 스케일링
                    X_train_scaled = self.scaler.fit_transform(X_train)
                    X_val_scaled = self.scaler.transform(X_val)
                    
                    # 훈련
                    temp_model.fit(X_train_scaled, y_train)
                    
                    # 평가
                    y_pred = temp_model.predict(X_val_scaled)
                    mse = np.mean((y_val - y_pred) ** 2)
                    
                    if mse < best_score:
                        best_score = mse
                        best_params = temp_hyperparams.copy()
                
                except Exception as e:
                    self.logger.debug(f"파라미터 {params} 테스트 실패: {e}")
                    continue
            
            # 최적 파라미터로 업데이트
            if best_params != self.hyperparameters:
                self.hyperparameters = best_params
                self.model = self._create_model()
                self.logger.info(f"✅ {self.model_name} 최적 파라미터 발견: {best_params}")
            
            return {
                'success': True,
                'best_params': best_params,
                'best_score': best_score,
                'improvement': best_score < self.performance_metrics.get('mse', float('inf'))
            }
            
        except Exception as e:
            self.logger.error(f"하이퍼파라미터 최적화 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    def _create_model_with_params(self, params: Dict[str, Any]):
        """지정된 파라미터로 모델 생성"""
        if self.model_type == "xgboost" and XGBOOST_AVAILABLE:
            return xgb.XGBRegressor(
                n_estimators=params.get('n_estimators', 100),
                max_depth=params.get('max_depth', 6),
                learning_rate=params.get('learning_rate', 0.1),
                subsample=params.get('subsample', 0.8),
                colsample_bytree=params.get('colsample_bytree', 0.8),
                random_state=42,
                n_jobs=-1,
                verbosity=0
            )
        elif SKLEARN_AVAILABLE:
            return DecisionTreeRegressor(
                max_depth=params.get('max_depth', 10),
                min_samples_split=params.get('min_samples_split', 5),
                min_samples_leaf=params.get('min_samples_leaf', 2),
                random_state=42
            )
        else:
            return None
    
    def get_feature_importance(self) -> Dict[str, float]:
        """특성 중요도 반환 (트리 모델 특화)"""
        if not self.is_trained or not hasattr(self.model, 'feature_importances_'):
            return {}
        
        try:
            importance_dict = {}
            
            for i, importance in enumerate(self.model.feature_importances_):
                feature_name = self.feature_names[i] if i < len(self.feature_names) else f'feature_{i}'
                importance_dict[feature_name] = float(importance)
            
            # 중요도 순으로 정렬
            sorted_importance = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
            
            # XGBoost의 경우 추가 중요도 정보
            if self.model_type == "xgboost" and hasattr(self.model, 'get_booster'):
                try:
                    # Gain 기반 중요도
                    gain_importance = self.model.get_booster().get_score(importance_type='gain')
                    sorted_importance['gain_importance'] = gain_importance
                except Exception:
                    pass
            
            return sorted_importance
            
        except Exception as e:
            self.logger.error(f"특성 중요도 계산 실패: {e}")
            return {}
    
    def get_tree_info(self) -> Dict[str, Any]:
        """트리 모델 정보 반환"""
        info = self.get_performance_summary()
        
        if self.model:
            info['tree_info'] = {
                'model_type': self.model_type,
                'xgboost_available': XGBOOST_AVAILABLE,
                'sklearn_available': SKLEARN_AVAILABLE
            }
            
            if self.model_type == "xgboost" and hasattr(self.model, 'get_booster'):
                try:
                    booster = self.model.get_booster()
                    info['tree_info'].update({
                        'n_trees': len(booster.get_dump()),
                        'best_ntree_limit': getattr(self.model, 'best_ntree_limit', None)
                    })
                except Exception:
                    pass
            
            elif hasattr(self.model, 'tree_'):
                info['tree_info'].update({
                    'tree_depth': self.model.tree_.max_depth,
                    'n_leaves': self.model.tree_.n_leaves,
                    'n_node_samples': self.model.tree_.n_node_samples[0] if len(self.model.tree_.n_node_samples) > 0 else 0
                })
        
        return info
"""
Enhanced ML Model Manager
Machine learning model management with real-time learning and performance tracking
"""

import asyncio
import logging
import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Any

# ML libraries
try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    import xgboost as xgb
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

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
        self.models = {}
        self.scalers = {}
        self.feature_names = []
        self.model_performance = {}
        self.last_retrain_time = {}
        
        # 🔍 Prediction verification system
        self.pending_predictions = {}  # 검증 대기 중인 예측들
        self.verification_task = None
        self._is_trained = False
        
        if not ML_AVAILABLE:
            self.logger.warning("ML 라이브러리가 설치되지 않았습니다. ML 기능을 비활성화합니다.")
            self.config.ENABLE_ML_MODELS = False
            return
        
        if hasattr(config, 'ENABLE_ML_MODELS') and config.ENABLE_ML_MODELS:
            self._initialize_models()
    
    async def initialize(self):
        """Initialize ML models (async compatibility)"""
        # Already initialized in __init__, this is for compatibility
        
        # Start prediction verification task
        if ML_AVAILABLE:
            self.verification_task = asyncio.create_task(self._prediction_verification_loop())
            self.logger.info("🔍 ML 예측 검증 시스템 시작")
        
        return True
    
    def _initialize_models(self):
        """Initialize ML models and scalers"""
        try:
            # Feature configuration
            self.feature_names = [
                'returns_1', 'returns_5', 'returns_20',
                'volume_ratio', 'atr_ratio', 'bb_position',
                'rsi', 'macd_signal', 'adx', 'obv_slope',
                'price_ma_ratio', 'volume_ma_ratio',
                'trend_strength', 'volatility_ratio'
            ]
            
            # Initialize scalers
            self.scalers['features'] = StandardScaler()
            self.scalers['target'] = MinMaxScaler()
            
            # Try to load existing models
            self._load_models()
            
            # If no models exist, create default ones
            if not self.models:
                self._create_default_models()
                # Note: Initial training will be triggered later during first use
                
        except Exception as e:
            self.logger.error(f"ML 모델 초기화 오류: {e}")
            self.config.ENABLE_ML_MODELS = False
    
    def _load_models(self):
        """Load saved models"""
        model_dir = "models"
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
            return
        
        # Load models
        model_files = {
            'random_forest': 'random_forest_model.pkl',
            'gradient_boost': 'gradient_boost_model.pkl',
            'neural_network': 'neural_network_model.pkl',
            'xgboost': 'xgboost_model.pkl'
        }
        
        for model_name, filename in model_files.items():
            filepath = os.path.join(model_dir, filename)
            if os.path.exists(filepath):
                try:
                    self.models[model_name] = joblib.load(filepath)
                    self.logger.info(f"{model_name} 모델 로드 완료")
                    self._is_trained = True
                    
                    # Load performance history
                    perf = self.db.get_ml_model_performance(model_name)
                    self.model_performance[model_name] = perf
                    
                except Exception as e:
                    self.logger.error(f"{model_name} 로드 실패: {e}")
        
        # Load scalers
        scaler_path = os.path.join(model_dir, 'scalers.pkl')
        if os.path.exists(scaler_path):
            try:
                self.scalers = joblib.load(scaler_path)
            except Exception as e:
                self.logger.warning(f"ML 스케일러 로딩 실패: {e}")
    
    def _create_default_models(self):
        """Create default models"""
        # Random Forest
        self.models['random_forest'] = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            random_state=42,
            n_jobs=-1
        )
        
        # Gradient Boosting
        self.models['gradient_boost'] = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        # Neural Network
        self.models['neural_network'] = MLPRegressor(
            hidden_layer_sizes=(100, 50, 25),
            activation='relu',
            solver='adam',
            alpha=0.001,
            random_state=42,
            max_iter=500
        )
        
        # XGBoost
        self.models['xgboost'] = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
        
        self.logger.info("기본 ML 모델 생성 완료")
    
    async def get_predictions(self, symbol: str, features: Dict[str, float]) -> Dict[str, Any]:
        """Get predictions from all models with performance tracking"""
        if not self.config.ENABLE_ML_MODELS or not self.models:
            return self._get_empty_prediction()
        
        # Check if models are trained
        if not self._is_trained:
            self.logger.info("ML 모델이 아직 학습되지 않았습니다. 초기 학습을 시도합니다...")
            await self._initial_training()
            if not self._is_trained:
                self.logger.warning("초기 학습 실패. 기본 예측을 반환합니다.")
                return self._get_default_prediction()
        
        # Check if models need retraining
        await self._check_and_retrain_models()
        
        try:
            # Prepare features
            feature_array = self._prepare_features(features)
            
            if feature_array is None:
                return self._get_empty_prediction()
            
            # Get predictions from each model
            predictions = {}
            prediction_ids = {}
            
            for model_name, model in self.models.items():
                try:
                    prediction = await self._predict_with_model(
                        model_name, model, feature_array
                    )
                    predictions[model_name] = prediction
                    
                    # Save prediction for tracking
                    if prediction:
                        pred_id = self.db.save_ml_prediction(
                            model_name, symbol, prediction['prediction'],
                            prediction['confidence'], features
                        )
                        prediction_ids[model_name] = pred_id
                        
                except Exception as e:
                    self.logger.error(f"{model_name} 예측 오류: {e}")
                    predictions[model_name] = None
            
            # Ensemble prediction
            ensemble_prediction = self._ensemble_predictions(predictions)
            
            return {
                'individual_predictions': predictions,
                'ensemble': ensemble_prediction,
                'features_used': self.feature_names,
                'confidence_factors': self._calculate_confidence_factors(features),
                'prediction_ids': prediction_ids
            }
            
        except Exception as e:
            self.logger.error(f"ML 예측 오류: {e}")
            return self._get_empty_prediction()
    
    async def _check_and_retrain_models(self):
        """Check if models need retraining based on performance"""
        current_time = datetime.now()
        
        for model_name in self.models:
            # Check last retrain time
            last_retrain = self.last_retrain_time.get(model_name, datetime.min)
            hours_since_retrain = (current_time - last_retrain).total_seconds() / 3600
            
            # Get current performance
            perf = self.db.get_ml_model_performance(model_name, self.config.ML_PREDICTION_WINDOW)
            
            # Retrain if:
            # 1. It's been longer than configured hours
            # 2. Performance dropped below threshold
            should_retrain = (
                hours_since_retrain >= self.config.ML_RETRAIN_HOURS or
                perf['accuracy'] < self.config.ML_MIN_PERFORMANCE
            )
            
            if should_retrain and perf['total_predictions'] >= 100:
                self.logger.info(f"{model_name} 재학습 중 - 정확도: {perf['accuracy']:.2%}")
                await self._retrain_model(model_name)
    
    async def _retrain_model(self, model_name: str):
        """Retrain a specific model with recent data"""
        try:
            # Get training data from recent predictions and actual results
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT features, actual 
                    FROM ml_performance 
                    WHERE model_name = ? AND actual IS NOT NULL
                    ORDER BY timestamp DESC 
                    LIMIT 5000
                """, (model_name,))
                
                training_data = cursor.fetchall()
            
            if len(training_data) < 1000:
                self.logger.warning(f"{model_name} 재학습을 위한 데이터 부족")
                return
            
            # Prepare training data
            X = []
            y = []
            
            for row in training_data:
                features = json.loads(row['features'])
                feature_array = [features.get(fname, 0) for fname in self.feature_names]
                X.append(feature_array)
                y.append(row['actual'])
            
            X = np.array(X)
            y = np.array(y)
            
            # Split data
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]
            
            # Retrain in background
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._train_model,
                model_name, X_train, y_train, X_test, y_test
            )
            
            self.last_retrain_time[model_name] = datetime.now()
            self.logger.info(f"{model_name} 모델 재학습 완료")
            
        except Exception as e:
            self.logger.error(f"{model_name} 재학습 실패: {e}")
    
    def _train_model(self, model_name: str, X_train, y_train, X_test, y_test):
        """Train model and evaluate performance"""
        model = self.models[model_name]
        
        # Fit model
        model.fit(X_train, y_train)
        self._is_trained = True
        
        # Evaluate
        predictions = model.predict(X_test)
        accuracy = np.mean(np.sign(predictions) == np.sign(y_test))
        
        self.logger.info(f"{model_name} 재학습 정확도: {accuracy:.2%}")
        
        # Save model
        self.save_models()
    
    async def _initial_model_training(self):
        """Initial training for new models using historical data"""
        try:
            self.logger.info("초기 모델 학습 시작...")
            
            # Try to load historical data from CSV files
            csv_files = [
                "BTCUSDT_15m_1month.csv",
                "BTCUSDT_30min.csv", 
                "btcusdt_1h_dtp.csv",
                "btcusdt_30m.csv"
            ]
            
            training_data = []
            for csv_file in csv_files:
                if os.path.exists(csv_file):
                    try:
                        df = pd.read_csv(csv_file)
                        if len(df) > 100:
                            training_data.append(df)
                            self.logger.info(f"{csv_file}에서 {len(df)}개 행 로드")
                    except Exception as e:
                        self.logger.warning(f"{csv_file} 로드 실패: {e}")
            
            if not training_data:
                self.logger.warning("초기 학습을 위한 과거 데이터가 없습니다")
                return
            
            # Combine all data
            combined_df = pd.concat(training_data, ignore_index=True)
            self.logger.info(f"결합된 학습 데이터: {len(combined_df)}개 행")
            
            # Generate features and targets from historical data
            X, y = await self._prepare_training_data(combined_df)
            
            if len(X) < 100:
                self.logger.warning("학습 데이터 부족")
                return
            
            # Fit scalers
            self.scalers['features'].fit(X)
            X_scaled = self.scalers['features'].transform(X)
            
            # Split data
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X_scaled[:split_idx], X_scaled[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]
            
            # Train all models
            for model_name in self.models:
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        self._train_model,
                        model_name, X_train, y_train, X_test, y_test
                    )
                    self.logger.info(f"{model_name} 초기 학습 완료")
                except Exception as e:
                    self.logger.error(f"{model_name} 초기 학습 실패: {e}")
            
            self._is_trained = True
            self.logger.info("초기 모델 학습 완료")
            
        except Exception as e:
            self.logger.error(f"초기 모델 학습 실패: {e}")
    
    async def _prepare_training_data(self, df):
        """Prepare training data from historical DataFrame"""
        try:
            # Calculate technical indicators
            df['returns'] = df['close'].pct_change()
            df['returns_1'] = df['returns'].shift(1)
            df['returns_5'] = df['returns'].rolling(5).mean()
            df['returns_20'] = df['returns'].rolling(20).mean()
            
            # Volume indicators
            df['volume_ma'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            
            # Price indicators
            df['sma_20'] = df['close'].rolling(20).mean()
            df['price_ma_ratio'] = df['close'] / df['sma_20']
            
            # Simple volatility
            df['volatility'] = df['returns'].rolling(20).std()
            df['volatility_ratio'] = df['volatility'] / df['volatility'].rolling(50).mean()
            
            # Remove NaN values
            df = df.dropna()
            
            # Prepare features
            X = []
            y = []
            
            for i in range(len(df) - 1):
                features = {
                    'returns_1': df.iloc[i]['returns_1'] if not pd.isna(df.iloc[i]['returns_1']) else 0,
                    'returns_5': df.iloc[i]['returns_5'] if not pd.isna(df.iloc[i]['returns_5']) else 0,
                    'returns_20': df.iloc[i]['returns_20'] if not pd.isna(df.iloc[i]['returns_20']) else 0,
                    'volume_ratio': df.iloc[i]['volume_ratio'] if not pd.isna(df.iloc[i]['volume_ratio']) else 1,
                    'price_ma_ratio': df.iloc[i]['price_ma_ratio'] if not pd.isna(df.iloc[i]['price_ma_ratio']) else 1,
                    'volatility_ratio': df.iloc[i]['volatility_ratio'] if not pd.isna(df.iloc[i]['volatility_ratio']) else 1,
                    'atr_ratio': 0.02,  # Default values for missing indicators
                    'bb_position': 0.5,
                    'rsi': 50.0,
                    'macd_signal': 0.0,
                    'adx': 25.0,
                    'obv_slope': 0.0,
                    'volume_ma_ratio': df.iloc[i]['volume_ratio'] if not pd.isna(df.iloc[i]['volume_ratio']) else 1,
                    'trend_strength': 0.5
                }
                
                # Target: next period return
                target = df.iloc[i + 1]['returns'] * 100  # Convert to percentage
                
                # Convert features to array
                feature_array = [features.get(fname, 0) for fname in self.feature_names]
                X.append(feature_array)
                y.append(target)
            
            return np.array(X), np.array(y)
            
        except Exception as e:
            self.logger.error(f"학습 데이터 준비 오류: {e}")
            return np.array([]), np.array([])
    
    def _prepare_features(self, raw_features: Dict[str, float]) -> Optional[np.ndarray]:
        """Prepare features for ML models"""
        try:
            # Extract features in correct order
            feature_values = []
            for feature_name in self.feature_names:
                if feature_name in raw_features:
                    feature_values.append(raw_features[feature_name])
                else:
                    # Use default values for missing features
                    feature_values.append(0.0)
            
            # Convert to numpy array
            feature_array = np.array(feature_values).reshape(1, -1)
            
            # Scale features if scaler is fitted
            if hasattr(self.scalers['features'], 'mean_'):
                feature_array = self.scalers['features'].transform(feature_array)
            
            return feature_array
            
        except Exception as e:
            self.logger.error(f"특징 준비 오류: {e}")
            return None
    
    async def _predict_with_model(self, model_name: str, model: Any, 
                                 features: np.ndarray) -> Dict:
        """Get prediction from single model"""
        try:
            # Check if model is fitted
            if not hasattr(model, 'n_features_in_'):
                self.logger.warning(f"{model_name}이 아직 학습되지 않았습니다")
                return None
                
            # Run prediction in thread pool
            loop = asyncio.get_event_loop()
            
            # Make prediction
            prediction = await loop.run_in_executor(
                None, model.predict, features
            )
            
            # Get prediction probability/confidence if available
            confidence = 0.5
            if hasattr(model, 'predict_proba'):
                try:
                    proba = await loop.run_in_executor(
                        None, model.predict_proba, features
                    )
                    confidence = np.max(proba)
                except (AttributeError, ValueError, TypeError, Exception) as e:
                    logging.error(f"ML 예측 실패: {e}")
                    confidence = 0.5
            
            # Convert prediction to direction and magnitude
            pred_value = float(prediction[0])
            
            if abs(pred_value) < 0.001:  # Near zero
                direction = 'neutral'
            elif pred_value > 0:
                direction = 'long'
            else:
                direction = 'short'
            
            return {
                'prediction': pred_value,
                'direction': direction,
                'confidence': float(confidence),
                'model': model_name
            }
            
        except Exception as e:
            self.logger.error(f"모델 예측 오류: {e}")
            return None
    
    def _ensemble_predictions(self, predictions: Dict) -> Dict:
        """Combine predictions from multiple models with performance weighting"""
        valid_predictions = [
            p for p in predictions.values() 
            if p is not None and 'prediction' in p
        ]
        
        if not valid_predictions:
            return {
                'prediction': 0,
                'direction': 'neutral',
                'confidence': 0,
                'method': 'none'
            }
        
        # Weighted average based on model performance
        total_weight = 0
        weighted_sum = 0
        direction_votes = defaultdict(float)
        
        for pred in valid_predictions:
            # Get model weight based on historical performance
            model_name = pred['model']
            perf = self.model_performance.get(model_name, {'accuracy': 0.5})
            
            # Use accuracy as weight
            weight = max(0.1, perf['accuracy'])
            
            # Weight by confidence too
            weight *= pred['confidence']
            
            weighted_sum += pred['prediction'] * weight
            direction_votes[pred['direction']] += weight
            total_weight += weight
        
        if total_weight == 0:
            ensemble_pred = np.mean([p['prediction'] for p in valid_predictions])
            ensemble_conf = np.mean([p['confidence'] for p in valid_predictions])
        else:
            ensemble_pred = weighted_sum / total_weight
            ensemble_conf = total_weight / len(valid_predictions)
        
        # Determine direction from votes
        ensemble_direction = max(direction_votes.items(), key=lambda x: x[1])[0]
        
        return {
            'prediction': ensemble_pred,
            'direction': ensemble_direction,
            'confidence': min(ensemble_conf, 0.95),
            'method': 'weighted_ensemble',
            'model_count': len(valid_predictions)
        }
    
    def _calculate_confidence_factors(self, features: Dict[str, float]) -> Dict[str, float]:
        """Calculate factors affecting prediction confidence"""
        factors = {}
        
        # Market regime confidence
        if 'trend_strength' in features:
            factors['trend_clarity'] = abs(features['trend_strength'])
        
        # Volatility impact
        if 'atr_ratio' in features:
            # Lower confidence in high volatility
            factors['volatility_penalty'] = max(0, 1 - features['atr_ratio'] * 10)
        
        # Technical alignment
        technical_signals = ['rsi', 'macd_signal', 'bb_position']
        aligned_signals = sum(1 for sig in technical_signals 
                            if sig in features and abs(features[sig]) > 0.3)
        factors['technical_alignment'] = aligned_signals / len(technical_signals)
        
        return factors
    
    def update_prediction_result(self, prediction_id: int, actual_result: float):
        """Update prediction with actual result for learning"""
        self.db.update_ml_prediction_result(prediction_id, actual_result)
    
    def save_models(self):
        """Save models to disk"""
        model_dir = "models"
        os.makedirs(model_dir, exist_ok=True)
        
        # Save models
        for model_name, model in self.models.items():
            filepath = os.path.join(model_dir, f"{model_name}_model.pkl")
            joblib.dump(model, filepath)
        
        # Save scalers
        scaler_path = os.path.join(model_dir, 'scalers.pkl')
        joblib.dump(self.scalers, scaler_path)
        
        self.logger.info("모델 저장 완료")
    
    async def _initial_training(self):
        """Perform initial training with minimal data or synthetic data"""
        try:
            # Try to get some historical data for training
            # If no data available, use synthetic data for initialization
            self.logger.info("초기 ML 모델 학습 중...")
            
            # Create minimal synthetic training data
            n_samples = 100
            np.random.seed(42)
            
            # Generate random features
            X = np.random.rand(n_samples, len(self.feature_names))
            # Simple target: slight trend based on features
            y = (X[:, 0] - 0.5) * 0.02 + np.random.normal(0, 0.005, n_samples)
            
            # Fit scalers
            self.scalers['features'].fit(X)
            self.scalers['target'].fit(y.reshape(-1, 1))
            
            # Train models with synthetic data
            X_scaled = self.scalers['features'].transform(X)
            y_scaled = self.scalers['target'].transform(y.reshape(-1, 1)).ravel()
            
            trained_count = 0
            for model_name, model in self.models.items():
                try:
                    model.fit(X_scaled, y_scaled)
                    trained_count += 1
                    self.logger.info(f"{model_name} 초기 학습 완료")
                except Exception as e:
                    self.logger.error(f"{model_name} 초기 학습 실패: {e}")
            
            if trained_count > 0:
                self._is_trained = True
                self.logger.info(f"{trained_count}개 모델 초기 학습 완료")
            
        except Exception as e:
            self.logger.error(f"초기 학습 오류: {e}")
    
    def _get_default_prediction(self) -> Dict:
        """Return default prediction when models are not available"""
        return {
            'individual_predictions': {},
            'ensemble': {
                'prediction': 0.001,  # Slightly positive bias
                'direction': 'neutral',
                'confidence': 0.3,  # Low confidence
                'method': 'default'
            },
            'features_used': [],
            'confidence_factors': {'default_mode': True},
            'prediction_ids': {}
        }
    
    def _get_empty_prediction(self) -> Dict:
        """Return empty prediction structure"""
        return {
            'individual_predictions': {},
            'ensemble': {
                'prediction': 0,
                'direction': 'neutral',
                'confidence': 0,
                'method': 'none'
            },
            'features_used': [],
            'confidence_factors': {},
            'prediction_ids': {}
        }
    
    async def _prediction_verification_loop(self):
        """주기적으로 예측 결과를 검증하는 루프"""
        while True:
            try:
                await asyncio.sleep(300)  # 5분마다 실행
                
                # 24시간 이상 지난 예측들을 검증
                cutoff_time = datetime.now().timestamp() - 86400  # 24시간 전
                
                # 미검증 예측들 가져오기
                unverified_predictions = await self._get_unverified_predictions(cutoff_time)
                
                for prediction in unverified_predictions:
                    await self._verify_single_prediction(prediction)
                
                # 모델 성능 통계 업데이트
                await self._update_model_performance_stats()
                
            except Exception as e:
                self.logger.error(f"❌ 예측 검증 루프 오류: {e}")
                await asyncio.sleep(60)
    
    async def _get_unverified_predictions(self, cutoff_time: float) -> List[Dict]:
        """검증되지 않은 예측들을 데이터베이스에서 가져오기"""
        try:
            # 데이터베이스에서 미검증 예측 조회
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, symbol, prediction, confidence, timestamp
                    FROM ml_performance 
                    WHERE actual IS NULL 
                    AND timestamp < ?
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (cutoff_time * 1000,))  # milliseconds
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"❌ 미검증 예측 조회 오류: {e}")
            return []
    
    async def _verify_single_prediction(self, prediction: Dict):
        """단일 예측 결과 검증"""
        try:
            symbol = prediction['symbol']
            prediction_value = prediction['prediction']
            prediction_time = prediction['timestamp'] / 1000  # Convert to seconds
            
            # 예측 시점 이후의 실제 가격 변화 계산
            actual_change = await self._get_actual_price_change(symbol, prediction_time)
            
            if actual_change is not None:
                # 방향 예측 정확도 계산
                direction_correct = (prediction_value > 0 and actual_change > 0) or \
                                  (prediction_value < 0 and actual_change < 0)
                
                # 데이터베이스 업데이트
                self.db.update_ml_prediction_result(prediction['id'], actual_change)
                
                self.logger.debug(f"🔍 {symbol} 예측 검증: 예측={prediction_value:.4f}, 실제={actual_change:.4f}, 방향일치={direction_correct}")
                
        except Exception as e:
            self.logger.error(f"❌ 예측 검증 오류: {e}")
    
    async def _get_actual_price_change(self, symbol: str, prediction_time: float) -> Optional[float]:
        """예측 시점 이후의 실제 가격 변화 계산"""
        try:
            # 예측 시점과 24시간 후의 가격 데이터 조회
            start_time = prediction_time
            end_time = prediction_time + 86400  # 24시간 후
            
            # 실제 구현에서는 거래소에서 과거 가격 데이터를 조회해야 함
            # 여기서는 간단한 구현
            if hasattr(self, 'exchange') and self.exchange:
                current_price = self.exchange.get_current_price(symbol)
                if current_price:
                    # 임시: 현재 가격 기준으로 랜덤 변화율 생성 (실제로는 과거 데이터 조회)
                    return np.random.normal(0, 0.02)  # 평균 0, 표준편차 2% 변화
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 실제 가격 변화 계산 오류: {e}")
            return None
    
    async def _update_model_performance_stats(self):
        """모델 성능 통계 업데이트"""
        try:
            for symbol in self.config.SYMBOLS:
                performance = self.db.get_ml_model_performance(f"ensemble_{symbol}")
                self.model_performance[symbol] = performance
                
                if performance['total_predictions'] > 0:
                    self.logger.info(f"📊 {symbol} ML 성능: 정확도={performance['accuracy']:.1%}, 예측수={performance['total_predictions']}")
                    
        except Exception as e:
            self.logger.error(f"❌ 모델 성능 통계 업데이트 오류: {e}")
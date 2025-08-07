"""
ML DAO
머신러닝 관련 데이터베이스 접근 객체
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base_dao import BaseDAO


class MLDao(BaseDAO):
    """머신러닝 관련 데이터베이스 접근 객체"""
    
    def __init__(self, db_path: str):
        super().__init__(db_path)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """ML 관련 테이블 생성"""
        tables = {
            'ml_predictions': '''
                CREATE TABLE IF NOT EXISTS ml_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    prediction REAL NOT NULL,
                    confidence REAL NOT NULL,
                    model_version TEXT DEFAULT '1.0',
                    features TEXT,
                    actual_outcome REAL,
                    is_validated BOOLEAN DEFAULT 0,
                    validation_timestamp DATETIME
                )
            ''',
            'model_performance': '''
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    accuracy REAL DEFAULT 0,
                    precision_score REAL DEFAULT 0,
                    recall REAL DEFAULT 0,
                    f1_score REAL DEFAULT 0,
                    total_predictions INTEGER DEFAULT 0,
                    correct_predictions INTEGER DEFAULT 0,
                    training_samples INTEGER DEFAULT 0,
                    last_training DATETIME
                )
            ''',
            'feature_importance': '''
                CREATE TABLE IF NOT EXISTS feature_importance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    feature_name TEXT NOT NULL,
                    importance_score REAL NOT NULL,
                    model_version TEXT DEFAULT '1.0'
                )
            '''
        }
        
        for table_name, create_sql in tables.items():
            self._execute_query(create_sql, fetch_all=False)
    
    def add_prediction(self, prediction_data: Dict[str, Any]) -> int:
        """ML 예측 결과 저장"""
        required_fields = ['symbol', 'timeframe', 'prediction', 'confidence']
        self._validate_required_fields(prediction_data, required_fields)
        
        sanitized_data = self._sanitize_data(prediction_data)
        
        query = '''
            INSERT INTO ml_predictions (
                symbol, timeframe, prediction, confidence, model_version, features
            ) VALUES (?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            sanitized_data['symbol'],
            sanitized_data['timeframe'],
            sanitized_data['prediction'],
            sanitized_data['confidence'],
            sanitized_data.get('model_version', '1.0'),
            sanitized_data.get('features', '{}')
        )
        
        return self._execute_insert(query, params)
    
    def get_recent_predictions(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 예측 결과 조회"""
        cache_key = f"ml_predictions:{symbol}:{timeframe}:recent:{limit}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        query = '''
            SELECT * FROM ml_predictions 
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC 
            LIMIT ?
        '''
        
        result = self._execute_query(query, (symbol, timeframe, limit))
        self._set_cached_data(cache_key, result, ttl=300)  # 5분 캐시
        return result
    
    def validate_prediction(self, prediction_id: int, actual_outcome: float) -> bool:
        """예측 결과 검증"""
        query = '''
            UPDATE ml_predictions 
            SET actual_outcome = ?, is_validated = 1, validation_timestamp = CURRENT_TIMESTAMP
            WHERE id = ?
        '''
        
        result = self._execute_query(query, (actual_outcome, prediction_id), fetch_all=False)
        
        # 캐시 무효화
        self._clear_cache_pattern("ml_predictions:*")
        
        return result > 0
    
    def get_model_performance(self, symbol: str, model_version: str = None) -> Dict[str, Any]:
        """모델 성능 조회"""
        cache_key = f"model_performance:{symbol}:{model_version or 'latest'}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        if model_version:
            query = '''
                SELECT * FROM model_performance 
                WHERE symbol = ? AND model_version = ?
                ORDER BY timestamp DESC 
                LIMIT 1
            '''
            params = (symbol, model_version)
        else:
            query = '''
                SELECT * FROM model_performance 
                WHERE symbol = ?
                ORDER BY timestamp DESC 
                LIMIT 1
            '''
            params = (symbol,)
        
        result = self._execute_query(query, params, fetch_one=True)
        
        if result:
            performance = dict(result)
        else:
            performance = {
                'symbol': symbol,
                'model_version': model_version or '1.0',
                'accuracy': 0.5,
                'precision_score': 0.5,
                'recall': 0.5,
                'f1_score': 0.5,
                'total_predictions': 0,
                'correct_predictions': 0,
                'training_samples': 0,
                'last_training': None
            }
        
        self._set_cached_data(cache_key, performance, ttl=1800)  # 30분 캐시
        return performance
    
    def update_model_performance(self, performance_data: Dict[str, Any]) -> bool:
        """모델 성능 업데이트"""
        required_fields = ['symbol', 'model_version']
        self._validate_required_fields(performance_data, required_fields)
        
        sanitized_data = self._sanitize_data(performance_data)
        
        # 캐시 무효화
        self._clear_cache_pattern(f"model_performance:{sanitized_data['symbol']}:*")
        
        query = '''
            INSERT OR REPLACE INTO model_performance (
                symbol, model_version, accuracy, precision_score, recall, f1_score,
                total_predictions, correct_predictions, training_samples, last_training
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            sanitized_data['symbol'],
            sanitized_data['model_version'],
            sanitized_data.get('accuracy', 0.5),
            sanitized_data.get('precision_score', 0.5),
            sanitized_data.get('recall', 0.5),
            sanitized_data.get('f1_score', 0.5),
            sanitized_data.get('total_predictions', 0),
            sanitized_data.get('correct_predictions', 0),
            sanitized_data.get('training_samples', 0),
            sanitized_data.get('last_training', datetime.now().isoformat())
        )
        
        result = self._execute_query(query, params, fetch_all=False)
        return result > 0
    
    def calculate_prediction_accuracy(self, symbol: str, days: int = 7) -> Dict[str, Any]:
        """예측 정확도 계산"""
        cache_key = f"prediction_accuracy:{symbol}:days:{days}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        query = '''
            SELECT 
                COUNT(*) as total_predictions,
                COUNT(CASE WHEN is_validated = 1 THEN 1 END) as validated_predictions,
                AVG(CASE WHEN is_validated = 1 AND 
                    ((prediction > 0 AND actual_outcome > 0) OR 
                     (prediction < 0 AND actual_outcome < 0)) THEN 1.0 ELSE 0.0 END) as accuracy,
                AVG(confidence) as avg_confidence
            FROM ml_predictions 
            WHERE symbol = ? AND timestamp >= datetime('now', '-{} days')
        '''.format(days)
        
        result = self._execute_query(query, (symbol,), fetch_one=True)
        
        if result:
            accuracy_stats = {
                'total_predictions': result['total_predictions'] or 0,
                'validated_predictions': result['validated_predictions'] or 0,
                'accuracy': result['accuracy'] or 0.5,
                'avg_confidence': result['avg_confidence'] or 0.5,
                'validation_rate': (result['validated_predictions'] or 0) / max(result['total_predictions'] or 1, 1)
            }
        else:
            accuracy_stats = {
                'total_predictions': 0,
                'validated_predictions': 0,
                'accuracy': 0.5,
                'avg_confidence': 0.5,
                'validation_rate': 0.0
            }
        
        self._set_cached_data(cache_key, accuracy_stats, ttl=3600)  # 1시간 캐시
        return accuracy_stats
    
    def save_feature_importance(self, symbol: str, features: Dict[str, float], model_version: str = "1.0") -> bool:
        """피처 중요도 저장"""
        if not features:
            return False
        
        # 기존 데이터 삭제 (같은 심볼, 모델 버전)
        delete_query = '''
            DELETE FROM feature_importance 
            WHERE symbol = ? AND model_version = ?
        '''
        self._execute_query(delete_query, (symbol, model_version), fetch_all=False)
        
        # 새 데이터 배치 삽입
        insert_query = '''
            INSERT INTO feature_importance (symbol, feature_name, importance_score, model_version)
            VALUES (?, ?, ?, ?)
        '''
        
        params_list = [
            (symbol, feature_name, importance_score, model_version)
            for feature_name, importance_score in features.items()
        ]
        
        result = self._execute_batch(insert_query, params_list)
        return result > 0
    
    def get_feature_importance(self, symbol: str, model_version: str = None) -> Dict[str, float]:
        """피처 중요도 조회"""
        cache_key = f"feature_importance:{symbol}:{model_version or 'latest'}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        if model_version:
            query = '''
                SELECT feature_name, importance_score 
                FROM feature_importance 
                WHERE symbol = ? AND model_version = ?
                ORDER BY importance_score DESC
            '''
            params = (symbol, model_version)
        else:
            query = '''
                SELECT feature_name, importance_score 
                FROM feature_importance 
                WHERE symbol = ? AND timestamp = (
                    SELECT MAX(timestamp) FROM feature_importance WHERE symbol = ?
                )
                ORDER BY importance_score DESC
            '''
            params = (symbol, symbol)
        
        results = self._execute_query(query, params)
        
        features = {row['feature_name']: row['importance_score'] for row in results}
        
        self._set_cached_data(cache_key, features, ttl=3600)  # 1시간 캐시
        return features
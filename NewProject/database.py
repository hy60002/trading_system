"""
데이터베이스 모듈
주문 정보, 고객 정보, 대화 기록 관리
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger
import os

class DatabaseManager:
    """데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = "ai_delivery.db"):
        self.db_path = db_path
        self.init_database()
        logger.info(f"데이터베이스 초기화 완료: {db_path}")
    
    def init_database(self):
        """데이터베이스 테이블 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 고객 정보 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT UNIQUE NOT NULL,
                    name TEXT,
                    preferred_address TEXT,
                    order_count INTEGER DEFAULT 0,
                    last_order_date DATETIME,
                    preferences TEXT,  -- JSON 형태로 저장
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 주문 정보 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_sid TEXT UNIQUE NOT NULL,
                    customer_phone TEXT NOT NULL,
                    menu_items TEXT NOT NULL,  -- JSON 형태
                    total_amount INTEGER NOT NULL,
                    delivery_address TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',  -- pending, confirmed, delivered, cancelled
                    order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    delivery_time DATETIME,
                    notes TEXT,
                    FOREIGN KEY (customer_phone) REFERENCES customers (phone_number)
                )
            ''')
            
            # 대화 기록 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_sid TEXT NOT NULL,
                    customer_phone TEXT NOT NULL,
                    conversation_data TEXT NOT NULL,  -- JSON 형태
                    call_duration INTEGER,  -- 초 단위
                    call_status TEXT,  -- completed, failed, in_progress
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (call_sid) REFERENCES orders (call_sid)
                )
            ''')
            
            # 메뉴 정보 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS menu_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT,
                    available BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 시스템 로그 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    call_sid TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            
            # 기본 메뉴 데이터 삽입
            self._insert_default_menu_items(cursor)
            conn.commit()
    
    def _insert_default_menu_items(self, cursor):
        """기본 메뉴 아이템 삽입"""
        default_menu = [
            # 치킨
            ('후라이드치킨', 'chicken', 18000, '바삭바삭한 후라이드 치킨'),
            ('양념치킨', 'chicken', 19000, '달콤매콤한 양념 치킨'),
            ('간장치킨', 'chicken', 20000, '고소한 간장 치킨'),
            
            # 피자
            ('페퍼로니피자', 'pizza', 25000, '클래식 페퍼로니 피자'),
            ('불고기피자', 'pizza', 27000, '한국식 불고기 피자'),
            ('치즈피자', 'pizza', 23000, '모짜렐라 치즈 피자'),
            
            # 중식
            ('짜장면', 'chinese', 7000, '진한 짜장 소스의 면 요리'),
            ('짬뽕', 'chinese', 8000, '매콤한 해물 짬뽕'),
            ('탕수육', 'chinese', 20000, '바삭한 탕수육'),
            
            # 한식
            ('김치찌개', 'korean', 9000, '얼큰한 김치찌개'),
            ('된장찌개', 'korean', 8000, '구수한 된장찌개'),
            ('제육볶음', 'korean', 12000, '매콤한 제육볶음'),
        ]
        
        # 기존 메뉴가 없을 때만 삽입
        cursor.execute('SELECT COUNT(*) FROM menu_items')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                'INSERT INTO menu_items (name, category, price, description) VALUES (?, ?, ?, ?)',
                default_menu
            )
            logger.info("기본 메뉴 아이템 삽입 완료")
    
    def get_customer_info(self, phone_number: str) -> Optional[Dict]:
        """고객 정보 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT * FROM customers WHERE phone_number = ?',
                    (phone_number,)
                )
                row = cursor.fetchone()
                
                if row:
                    return {
                        'id': row[0],
                        'phone_number': row[1],
                        'name': row[2],
                        'preferred_address': row[3],
                        'order_count': row[4],
                        'last_order_date': row[5],
                        'preferences': json.loads(row[6]) if row[6] else {},
                        'created_at': row[7]
                    }
                return None
                
        except Exception as e:
            logger.error(f"고객 정보 조회 오류: {e}")
            return None
    
    def save_customer_info(self, customer_data: Dict) -> bool:
        """고객 정보 저장/업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 기존 고객 확인
                existing = self.get_customer_info(customer_data['phone_number'])
                
                if existing:
                    # 업데이트
                    cursor.execute('''
                        UPDATE customers 
                        SET name = ?, preferred_address = ?, order_count = order_count + 1,
                            last_order_date = ?, preferences = ?
                        WHERE phone_number = ?
                    ''', (
                        customer_data.get('name', existing['name']),
                        customer_data.get('preferred_address', existing['preferred_address']),
                        datetime.now().isoformat(),
                        json.dumps(customer_data.get('preferences', {})),
                        customer_data['phone_number']
                    ))
                else:
                    # 신규 삽입
                    cursor.execute('''
                        INSERT INTO customers 
                        (phone_number, name, preferred_address, order_count, last_order_date, preferences)
                        VALUES (?, ?, ?, 1, ?, ?)
                    ''', (
                        customer_data['phone_number'],
                        customer_data.get('name'),
                        customer_data.get('preferred_address'),
                        datetime.now().isoformat(),
                        json.dumps(customer_data.get('preferences', {}))
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"고객 정보 저장 오류: {e}")
            return False
    
    def save_order(self, order_data: Dict) -> Optional[int]:
        """주문 정보 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO orders 
                    (call_sid, customer_phone, menu_items, total_amount, 
                     delivery_address, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order_data['call_sid'],
                    order_data['customer_phone'],
                    json.dumps(order_data['menu_items']),
                    order_data['total_amount'],
                    order_data['delivery_address'],
                    order_data.get('status', 'pending'),
                    order_data.get('notes', '')
                ))
                
                order_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"주문 저장 완료: ID {order_id}")
                return order_id
                
        except Exception as e:
            logger.error(f"주문 저장 오류: {e}")
            return None
    
    def get_order(self, call_sid: str) -> Optional[Dict]:
        """주문 정보 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT * FROM orders WHERE call_sid = ?',
                    (call_sid,)
                )
                row = cursor.fetchone()
                
                if row:
                    return {
                        'id': row[0],
                        'call_sid': row[1],
                        'customer_phone': row[2],
                        'menu_items': json.loads(row[3]),
                        'total_amount': row[4],
                        'delivery_address': row[5],
                        'status': row[6],
                        'order_date': row[7],
                        'delivery_time': row[8],
                        'notes': row[9]
                    }
                return None
                
        except Exception as e:
            logger.error(f"주문 조회 오류: {e}")
            return None
    
    def save_conversation(self, call_sid: str, customer_phone: str, 
                         conversation_data: List[Dict], call_status: str = 'completed') -> bool:
        """대화 기록 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO conversations 
                    (call_sid, customer_phone, conversation_data, call_status)
                    VALUES (?, ?, ?, ?)
                ''', (
                    call_sid,
                    customer_phone,
                    json.dumps(conversation_data, ensure_ascii=False),
                    call_status
                ))
                
                conn.commit()
                logger.info(f"대화 기록 저장 완료: {call_sid}")
                return True
                
        except Exception as e:
            logger.error(f"대화 기록 저장 오류: {e}")
            return False
    
    def get_menu_items(self, category: Optional[str] = None) -> List[Dict]:
        """메뉴 아이템 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if category:
                    cursor.execute(
                        'SELECT * FROM menu_items WHERE category = ? AND available = 1',
                        (category,)
                    )
                else:
                    cursor.execute('SELECT * FROM menu_items WHERE available = 1')
                
                rows = cursor.fetchall()
                
                return [
                    {
                        'id': row[0],
                        'name': row[1],
                        'category': row[2],
                        'price': row[3],
                        'description': row[4],
                        'available': row[5]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"메뉴 조회 오류: {e}")
            return []
    
    def get_customer_order_history(self, phone_number: str, limit: int = 5) -> List[Dict]:
        """고객 주문 이력 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM orders 
                    WHERE customer_phone = ? 
                    ORDER BY order_date DESC 
                    LIMIT ?
                ''', (phone_number, limit))
                
                rows = cursor.fetchall()
                
                return [
                    {
                        'id': row[0],
                        'call_sid': row[1],
                        'menu_items': json.loads(row[3]),
                        'total_amount': row[4],
                        'delivery_address': row[5],
                        'status': row[6],
                        'order_date': row[7]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"주문 이력 조회 오류: {e}")
            return []
    
    def log_system_event(self, level: str, message: str, call_sid: Optional[str] = None):
        """시스템 이벤트 로깅"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO system_logs (level, message, call_sid)
                    VALUES (?, ?, ?)
                ''', (level, message, call_sid))
                conn.commit()
                
        except Exception as e:
            logger.error(f"시스템 로그 저장 오류: {e}")
    
    def get_system_stats(self) -> Dict:
        """시스템 통계 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 총 주문 수
                cursor.execute('SELECT COUNT(*) FROM orders')
                total_orders = cursor.fetchone()[0]
                
                # 총 고객 수
                cursor.execute('SELECT COUNT(*) FROM customers')
                total_customers = cursor.fetchone()[0]
                
                # 오늘 주문 수
                today = datetime.now().date().isoformat()
                cursor.execute('SELECT COUNT(*) FROM orders WHERE DATE(order_date) = ?', (today,))
                today_orders = cursor.fetchone()[0]
                
                # 인기 메뉴 (상위 5개)
                cursor.execute('''
                    SELECT menu_items, COUNT(*) as order_count 
                    FROM orders 
                    GROUP BY menu_items 
                    ORDER BY order_count DESC 
                    LIMIT 5
                ''')
                popular_items = cursor.fetchall()
                
                return {
                    'total_orders': total_orders,
                    'total_customers': total_customers,
                    'today_orders': today_orders,
                    'popular_items': popular_items
                }
                
        except Exception as e:
            logger.error(f"통계 조회 오류: {e}")
            return {}

# 전역 인스턴스
db_manager = DatabaseManager()
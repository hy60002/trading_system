import sqlite3

conn = sqlite3.connect('advanced_trading_v3.db')
cursor = conn.cursor()

print("=== 데이터베이스 테이블 스키마 분석 ===")

# 모든 테이블 목록
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("테이블 목록:", [table[0] for table in tables])
print()

# 각 테이블의 구조 확인
for table in tables:
    table_name = table[0]
    if table_name != 'sqlite_sequence':
        print(f"=== {table_name} 테이블 구조 ===")
        cursor.execute(f'PRAGMA table_info({table_name})')
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # 데이터 샘플 확인
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f"  총 레코드 수: {count}")
        
        if count > 0:
            cursor.execute(f'SELECT * FROM {table_name} LIMIT 3')
            samples = cursor.fetchall()
            print(f"  샘플 데이터:")
            for i, sample in enumerate(samples):
                print(f"    {i+1}: {sample}")
        print()

conn.close()
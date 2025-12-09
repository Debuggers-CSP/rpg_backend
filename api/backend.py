from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
from contextlib import contextmanager

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:4500", "http://127.0.0.1:4500"],
        "methods": ["GET", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

DATABASE = 'rpg_statistics.db'

# 数据库连接管理
@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# 初始化数据库
def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 创建统计表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0
            )
        ''')
        
        # 创建历史记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        
        # 初始化统计数据（如果不存在）
        cursor.execute('SELECT COUNT(*) FROM statistics')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO statistics (mode, count) VALUES (?, ?)', ('chill', 0))
            cursor.execute('INSERT INTO statistics (mode, count) VALUES (?, ?)', ('action', 0))
        
        conn.commit()

# 获取统计数据
def get_statistics():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 获取统计
        cursor.execute('SELECT mode, count FROM statistics')
        stats_rows = cursor.fetchall()
        
        stats = {'chill': 0, 'action': 0, 'total': 0}
        for row in stats_rows:
            mode = row['mode']
            count = row['count']
            stats[mode] = count
            stats['total'] += count
        
        # 获取历史记录（最近100条）
        cursor.execute('''
            SELECT user_id, mode, timestamp 
            FROM history 
            ORDER BY id DESC 
            LIMIT 100
        ''')
        history_rows = cursor.fetchall()
        
        stats['history'] = [
            {
                'userId': row['user_id'],
                'mode': row['mode'],
                'timestamp': row['timestamp']
            }
            for row in history_rows
        ]
        
        return stats

# API 路由 - 获取统计数据
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        stats = get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API 路由 - 记录选择（改为 GET，使用 URL 参数）
@app.route('/api/stats/record', methods=['GET'])
def record_selection():
    try:
        # 从 URL 参数获取数据
        mode = request.args.get('mode')
        user_id = request.args.get('userId', 'anonymous')
        
        if mode not in ['chill', 'action']:
            return jsonify({'error': 'Invalid mode'}), 400
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 更新统计
            cursor.execute('''
                UPDATE statistics 
                SET count = count + 1 
                WHERE mode = ?
            ''', (mode,))
            
            # 添加历史记录
            timestamp = datetime.utcnow().isoformat()
            cursor.execute('''
                INSERT INTO history (user_id, mode, timestamp)
                VALUES (?, ?, ?)
            ''', (user_id, mode, timestamp))
            
            conn.commit()
        
        stats = get_statistics()
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API 路由 - 重置统计（改为 GET）
@app.route('/api/stats/reset', methods=['GET'])
def reset_stats():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 重置统计
            cursor.execute('UPDATE statistics SET count = 0')
            
            # 清空历史记录
            cursor.execute('DELETE FROM history')
            
            conn.commit()
        
        stats = get_statistics()
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'database': DATABASE})

@app.route('/')
def home():
    return jsonify({'message': 'RPG Statistics API', 'status': 'running'})

# 启动时初始化数据库
if __name__ == '__main__':
    print('Initializing database...')
    init_db()
    print('Database initialized!')
    print(f'Database file: {DATABASE}')
    print('Starting Flask server...')
    app.run(debug=True, host='0.0.0.0', port=5002)
# 修改后的后端代码，支持GET请求
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
from contextlib import contextmanager

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:4500", "http://127.0.0.1:4500"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

DATABASE = 'rpg_statistics.db'

# ... [保持其他函数不变，get_db(), init_db(), get_statistics()] ...

# API 路由
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        stats = get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 同时支持POST和GET请求
@app.route('/api/stats/record', methods=['POST', 'GET'])
def record_selection():
    try:
        if request.method == 'GET':
            # GET请求，从URL参数获取
            mode = request.args.get('mode')
            user_id = request.args.get('userId', 'anonymous')
        else:
            # POST请求，从JSON数据获取
            data = request.json
            mode = data.get('mode')
            user_id = data.get('userId', 'anonymous')
        
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

# 同时支持POST和GET请求
@app.route('/api/stats/reset', methods=['POST', 'GET'])
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

# ... [其他代码保持不变] ...

if __name__ == '__main__':
    print('Initializing database...')
    init_db()
    print('Database initialized!')
    print(f'Database file: {DATABASE}')
    print('Starting Flask server...')
    app.run(debug=True, host='0.0.0.0', port=5001)
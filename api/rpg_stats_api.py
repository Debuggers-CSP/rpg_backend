from flask import Blueprint, request, jsonify
import sqlite3
from datetime import datetime
from contextlib import contextmanager
import os

rpg_stats_api = Blueprint('rpg_stats_api', __name__, url_prefix='/api/rpg_stats')

# 数据库文件路径（放在 instance 或 volumes 目录）
DATABASE = os.path.join('instance', 'rpg_statistics.db')

# 确保目录存在
os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

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
def init_rpg_stats():
    """初始化 RPG 统计数据库"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 创建统计表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL UNIQUE,
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
            print('✓ RPG Statistics database initialized')
        
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
@rpg_stats_api.route('/stats', methods=['GET'])
def get_stats():
    """GET /api/rpg_stats/stats - 获取统计数据"""
    try:
        stats = get_statistics()
        print(f'📊 Returning stats: chill={stats["chill"]}, action={stats["action"]}, total={stats["total"]}')
        return jsonify(stats)
    except Exception as e:
        print(f'❌ Error getting stats: {e}')
        return jsonify({'error': str(e)}), 500

# API 路由 - 记录选择
@rpg_stats_api.route('/record', methods=['GET'])
def record_selection():
    """GET /api/rpg_stats/record?mode=chill&userId=xxx - 记录选择"""
    try:
        # 从 URL 参数获取数据
        mode = request.args.get('mode')
        user_id = request.args.get('userId', 'anonymous')
        
        print(f'📝 Recording: mode={mode}, userId={user_id}')
        
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
            print(f'✓ Successfully recorded {mode} selection')
        
        stats = get_statistics()
        return jsonify(stats)
    
    except Exception as e:
        print(f'❌ Error recording selection: {e}')
        return jsonify({'error': str(e)}), 500

# API 路由 - 重置统计
@rpg_stats_api.route('/reset', methods=['GET', 'POST'])
def reset_stats():
    """GET/POST /api/rpg_stats/reset - 重置统计数据"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 重置统计
            cursor.execute('UPDATE statistics SET count = 0')
            
            # 清空历史记录
            cursor.execute('DELETE FROM history')
            
            conn.commit()
            print('✓ Statistics reset successfully')
        
        stats = get_statistics()
        return jsonify(stats)
    
    except Exception as e:
        print(f'❌ Error resetting stats: {e}')
        return jsonify({'error': str(e)}), 500

@rpg_stats_api.route('/health', methods=['GET'])
def health():
    """GET /api/rpg_stats/health - 健康检查"""
    return jsonify({
        'status': 'healthy', 
        'database': DATABASE,
        'message': 'RPG Statistics API is running'
    })
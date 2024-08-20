from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, join_room, leave_room as socketio_leave_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import pymysql
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Initialize Flask-SocketIO with eventlet as the async mode
socketio = SocketIO(app, async_mode='eventlet')

# MySQL database configuration
DATABASE_HOST = os.getenv('AURORA_HOST')  # Aurora MySQL 클러스터 엔드포인트
DATABASE_USER = os.getenv('AURORA_USER')  # Aurora MySQL 사용자 이름
DATABASE_PASSWORD = os.getenv('AURORA_PASSWORD')  # Aurora MySQL 비밀번호
DATABASE_NAME = os.getenv('AURORA_DB_NAME')  # Aurora MySQL 데이터베이스 이름

def get_db_connection():
    conn = pymysql.connect(
        host=DATABASE_HOST,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        db=DATABASE_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def convert_path_to_url(path):
    return path.replace('\\', '/')

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['nickname'] = user['nickname']
            return redirect(url_for('main'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nickname = request.form['nickname']
        
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('INSERT INTO users (username, password, nickname) VALUES (%s, %s, %s)', (username, hashed_password, nickname))
        conn.commit()
        conn.close()
        
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/main')
def main():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'show_intro' not in session:
        session['show_intro'] = True
    else:
        session['show_intro'] = False

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM items')
        items = cursor.fetchall()
    conn.close()

    for item in items:
        item['image_url'] = url_for('static', filename=convert_path_to_url(item['image_url']))

    return render_template('main.html', username=session['username'], items=items)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/post_item', methods=['GET', 'POST'])
def post_item():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        file = request.files['image']
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            image_url = os.path.join('uploads', filename)
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO items (title, description, image_url, user_id, created_at, nickname) VALUES (%s, %s, %s, %s, %s, %s)', 
                               (title, description, image_url, session['user_id'], created_at, session['nickname']))
            conn.commit()
            conn.close()
            
            return redirect(url_for('main'))
        else:
            flash('Invalid file format. Please upload a PNG, JPG, JPEG, or GIF file.')
    
    return render_template('post_item.html')

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM items WHERE id = %s', (item_id,))
        item = cursor.fetchone()
        cursor.execute('SELECT * FROM bids WHERE item_id = %s', (item_id,))
        bids = cursor.fetchall()
    conn.close()

    for bid in bids:
        bid['image_url'] = url_for('static', filename=convert_path_to_url(bid['image_url']))

    return render_template('item_detail.html', item=item, bids=bids)

@app.route('/bid_item/<int:item_id>', methods=['GET', 'POST'])
def bid_item(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        file = request.files['image']
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            image_url = os.path.join('uploads', filename)
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO bids (item_id, title, description, image_url, user_id, created_at, nickname) VALUES (%s, %s, %s, %s, %s, %s, %s)', 
                               (item_id, title, description, image_url, session['user_id'], created_at, session['nickname']))
            conn.commit()
            conn.close()
            
            return redirect(url_for('item_detail', item_id=item_id))
        else:
            flash('Invalid file format. Please upload a PNG, JPG, JPEG, or GIF file.')
    
    return render_template('bid_item.html', item_id=item_id)

@app.route('/bid_detail/<int:bid_id>')
def bid_detail(bid_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM bids WHERE id = %s', (bid_id,))
        bid = cursor.fetchone()
        cursor.execute('SELECT * FROM items WHERE id = %s', (bid['item_id'],))
        item = cursor.fetchone()
    conn.close()

    bid['image_url'] = url_for('static', filename=convert_path_to_url(bid['image_url']))
    item['image_url'] = url_for('static', filename=convert_path_to_url(item['image_url']))

    return render_template('bid_detail.html', bid=bid, item=item)

@app.route('/complete_exchange/<int:bid_id>', methods=['POST'])
def complete_exchange(bid_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM bids WHERE id = %s', (bid_id,))
        bid = cursor.fetchone()
        if bid:
            cursor.execute('UPDATE items SET status = %s WHERE id = %s', ('completed', bid['item_id']))
        conn.commit()
    conn.close()

    return redirect(url_for('main'))

@app.route('/create_chat_room/<int:bid_id>')
def create_chat_room(bid_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM bids WHERE id = %s', (bid_id,))
        bid = cursor.fetchone()
        cursor.execute('''
            SELECT * FROM chat_rooms
            WHERE bid_id = %s AND ((user1_id = %s AND user2_id = %s) OR (user1_id = %s AND user2_id = %s))
        ''', (bid_id, session['user_id'], bid['user_id'], bid['user_id'], session['user_id']))
        existing_room = cursor.fetchone()
        
        if existing_room:
            chat_room = existing_room
        else:
            cursor.execute('''
                INSERT INTO chat_rooms (bid_id, user1_id, user2_id, created_at)
                VALUES (%s, %s, %s, %s)
            ''', (bid_id, session['user_id'], bid['user_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            cursor.execute('SELECT * FROM chat_rooms WHERE id = last_insert_id()')
            chat_room = cursor.fetchone()
    
    conn.close()
    return redirect(url_for('chat_room', room_id=chat_room['id']))

@app.route('/chat_room/<int:room_id>', methods=['GET', 'POST'])
def chat_room(room_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM chat_rooms WHERE id = %s', (room_id,))
        room = cursor.fetchone()
        cursor.execute('SELECT * FROM bids WHERE id = %s', (room['bid_id'],))
        bid = cursor.fetchone()
        cursor.execute('SELECT * FROM items WHERE id = %s', (bid['item_id'],))
        post_item = cursor.fetchone()
        cursor.execute('SELECT * FROM messages WHERE room_id = %s', (room_id,))
        messages = cursor.fetchall()

    for message in messages:
        if message['timestamp']:
            message['timestamp'] = datetime.strptime(message['timestamp'], '%Y-%m-%d %H:%M:%S')

    user_id = session['user_id']
    other_user_id = room['user2_id'] if room['user1_id'] == user_id else room['user1_id']
    other_user = conn.cursor().execute('SELECT nickname FROM users WHERE user_id = %s', (other_user_id,)).fetchone()

    post_item['image_url'] = url_for('static', filename=convert_path_to_url(post_item['image_url']))
    bid['image_url'] = url_for('static', filename=convert_path_to_url(bid['image_url']))

    conn.close()

    return render_template('chat.html', room=room, messages=messages, bid=bid, post_item=post_item, other_user=other_user)

@socketio.on('join')
def handle_join(data):
    join_room(data['room'])
    emit('message', {'msg': f"{data['username']} has entered the room."}, room=data['room'])

@socketio.on('send_message')
def handle_send_message(data):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('INSERT INTO messages (room_id, sender_id, message, timestamp) VALUES (%s, %s, %s, %s)',
                       (data['room'], session['user_id'], data['message'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    emit('receive_message', {
        'username': data['username'],
        'message': data['message'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }, room=data['room'])

@app.route('/chat_rooms')
def chat_rooms():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT * FROM chat_rooms
            WHERE user1_id = %s OR user2_id = %s
        ''', (session['user_id'], session['user_id']))
        rooms = cursor.fetchall()

    for room in rooms:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM bids WHERE id = %s', (room['bid_id'],))
            bid = cursor.fetchone()
            if bid:
                room['item_title'] = bid['title']
                room['item_image_url'] = url_for('static', filename=convert_path_to_url(bid['image_url']))
                room['user1_nickname'] = conn.cursor().execute('SELECT nickname FROM users WHERE user_id = %s', (room['user1_id'],)).fetchone()['nickname']
                room['user2_nickname'] = conn.cursor().execute('SELECT nickname FROM users WHERE user_id = %s', (room['user2_id'],)).fetchone()['nickname']
    conn.close()

    return render_template('chat_rooms.html', rooms=rooms)

@app.route('/delete_item/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM items WHERE id = %s', (item_id,))
        item = cursor.fetchone()

        if item and item['user_id'] == session['user_id']:
            cursor.execute('DELETE FROM items WHERE id = %s', (item_id,))
            conn.commit()
            conn.close()
            return jsonify({'success': 'Item deleted'}), 200
        else:
            conn.close()
            return jsonify({'error': 'Item not found or unauthorized'}), 404
    
@app.route('/leave_chat_room/<int:room_id>', methods=['DELETE'])
def leave_chat_room(room_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM chat_rooms WHERE id = %s', (room_id,))
        room = cursor.fetchone()

        if room and (room['user1_id'] == session['user_id'] or room['user2_id'] == session['user_id']):
            cursor.execute('DELETE FROM messages WHERE room_id = %s', (room_id,))
            cursor.execute('DELETE FROM chat_rooms WHERE id = %s', (room_id,))
            conn.commit()
            conn.close()
            return jsonify({'success': 'Room and messages deleted'}), 200
        else:
            conn.close()
            return jsonify({'error': 'Room not found or unauthorized'}), 404

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True)

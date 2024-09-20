from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, join_room, leave_room as socketio_leave_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import pymysql
import boto3
from botocore.exceptions import NoCredentialsError
from datetime import datetime
from dotenv import load_dotenv

#2 Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Initialize Flask-SocketIO with eventlet as the async mode1
socketio = SocketIO(app, async_mode='eventlet')

# MySQL3 database configuration
DATABASE_HOST = '217.83.162.65'
DATABASE_USER = 'admin'
DATABASE_PASSWORD = 'VMware1!'
DATABASE_NAME = 'mydatabase'

# S3 configuration
S3_BUCKET_NAME = 'baggu-s3'
S3_REGION = 'ap-northeast-2'
s3_client = boto3.client('s3', region_name=S3_REGION)

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

def upload_to_s3(file, bucket_name, filename):
    try:
        s3_client.upload_fileobj(file, bucket_name, filename)
        s3_url = f"https://{bucket_name}.s3.{S3_REGION}.amazonaws.com/{filename}"
        return s3_url
    except NoCredentialsError:
        return None

@app.route('/healthz')
def healthz():
    return '', 200

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
        cursor = conn.cursor()
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
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password, nickname) VALUES (%s, %s, %s)', (username, hashed_password, nickname))
        conn.commit()
        conn.close()
        
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/main')
def main():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    sort_by = request.args.get('sort_by', 'date')  # 정렬 기준
    order = request.args.get('order', 'desc')  # 정렬 방식 (기본: 내림차순)

    # 현재 정렬 기준이 asc면 desc로 변경하고, desc면 asc로 변경
    next_order = 'asc' if order == 'desc' else 'desc'

    conn = get_db_connection()
    cursor = conn.cursor()

    # 정렬 기준에 따라 쿼리 실행
    if sort_by == 'name':
        query = f"SELECT * FROM items ORDER BY title {order}"
    elif sort_by == 'date':
        query = f"SELECT * FROM items ORDER BY created_at {order}"
    elif sort_by == 'user':
        query = f"SELECT * FROM items ORDER BY user_id {order}"
    else:
        query = "SELECT * FROM items ORDER BY created_at DESC"  # 기본 날짜순 내림차순
    cursor.execute(query)
    items = cursor.fetchall()

    conn.close()

    return render_template('main.html', username=session['username'], items=items, sort_by=sort_by, order=order, next_order=next_order)

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
            s3_url = upload_to_s3(file, S3_BUCKET_NAME, filename)

            if s3_url:
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('INSERT INTO items (title, description, image_url, user_id, created_at, nickname) VALUES (%s, %s, %s, %s, %s, %s)', 
                               (title, description, s3_url, session['user_id'], created_at, session['nickname']))
                conn.commit()
                conn.close()
                return redirect(url_for('main'))
            else:
                flash('Failed to upload image to S3')
        else:
            flash('Invalid file format. Please upload a PNG, JPG, JPEG, or GIF file.')
    
    return render_template('post_item.html')

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items WHERE id = %s', (item_id,))
    item = cursor.fetchone()
    cursor.execute('SELECT * FROM bids WHERE item_id = %s', (item_id,))
    bids = cursor.fetchall()
    conn.close()

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
            s3_url = upload_to_s3(file, S3_BUCKET_NAME, filename)

            if s3_url:
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('INSERT INTO bids (item_id, title, description, image_url, user_id, created_at, nickname) VALUES (%s, %s, %s, %s, %s, %s, %s)', 
                               (item_id, title, description, s3_url, session['user_id'], created_at, session['nickname']))
                conn.commit()
                conn.close()
                return redirect(url_for('item_detail', item_id=item_id))
            else:
                flash('Failed to upload image to S3')
        else:
            flash('Invalid file format. Please upload a PNG, JPG, JPEG, or GIF file.')
    
    return render_template('bid_item.html', item_id=item_id)

@app.route('/bid_detail/<int:bid_id>')
def bid_detail(bid_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bids WHERE id = %s', (bid_id,))
    bid = cursor.fetchone()
    cursor.execute('SELECT * FROM items WHERE id = %s', (bid['item_id'],))
    item = cursor.fetchone()
    conn.close()

    return render_template('bid_detail.html', bid=bid, item=item)

@app.route('/complete_exchange/<int:bid_id>', methods=['POST'])
def complete_exchange(bid_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
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
    cursor = conn.cursor()
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
    try:
        cursor = conn.cursor()
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

        cursor.execute('SELECT nickname FROM users WHERE user_id = %s', (other_user_id,))
        other_user = cursor.fetchone()

    finally:
        conn.close()

    return render_template('chat.html', room=room, messages=messages, bid=bid, post_item=post_item, other_user=other_user)

@socketio.on('join')
def handle_join(data):
    join_room(data['room'])
    emit('message', {'msg': f"{data['username']} has entered the room."}, room=data['room'])

@socketio.on('send_message')
def handle_send_message(data):
    conn = get_db_connection()
    cursor = conn.cursor()
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
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM chat_rooms
        WHERE user1_id = %s OR user2_id = %s
    ''', (session['user_id'], session['user_id']))
    rooms = cursor.fetchall()

    for room in rooms:
        cursor.execute('SELECT * FROM bids WHERE id = %s', (room['bid_id'],))
        bid = cursor.fetchone()
        if bid:
            room['item_title'] = bid['title']

            if 'static/' in bid['image_url']:
                room['item_image_url'] = bid['image_url']
            else:
                room['item_image_url'] = url_for('static', filename=f'uploads/{bid["image_url"]}')

        cursor.execute('SELECT nickname FROM users WHERE user_id = %s', (room['user1_id'],))
        user1_nickname = cursor.fetchone()
        room['user1_nickname'] = user1_nickname['nickname'] if user1_nickname else None

        cursor.execute('SELECT nickname FROM users WHERE user_id = %s', (room['user2_id'],))
        user2_nickname = cursor.fetchone()
        room['user2_nickname'] = user2_nickname['nickname'] if user2_nickname else None

    conn.close()

    return render_template('chat_rooms.html', rooms=rooms)

@app.route('/delete_item/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
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
    cursor = conn.cursor()
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

@app.route('/my_transactions')
def my_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT items.*, bids.title AS bid_title, bids.description AS bid_description, bids.image_url AS bid_image_url, bids.nickname AS bid_nickname
        FROM items
        JOIN bids ON items.id = bids.item_id
        WHERE items.user_id = %s AND items.status = 'completed'
    ''', (session['user_id'],))
    my_posted_transactions = cursor.fetchall()

    cursor.execute('''
        SELECT items.*, bids.title AS bid_title, bids.description AS bid_description, bids.image_url AS bid_image_url, bids.nickname AS bid_nickname
        FROM bids
        JOIN items ON items.id = bids.item_id
        WHERE bids.user_id = %s AND items.status = 'completed'
    ''', (session['user_id'],))
    my_bid_transactions = cursor.fetchall()

    transaction_data_my_posts = []
    for transaction in my_posted_transactions:
        transaction_data_my_posts.append({
            'my_item': {
                'title': transaction['title'],
                'description': transaction['description'],
                'image_url': transaction['image_url'],
                'nickname': transaction['nickname']
            },
            'bid_item': {
                'title': transaction['bid_title'],
                'description': transaction['bid_description'],
                'image_url': transaction['bid_image_url'],
                'nickname': transaction['bid_nickname']
            }
        })

    transaction_data_my_bids = []
    for transaction in my_bid_transactions:
        transaction_data_my_bids.append({
            'my_item': {
                'title': transaction['bid_title'],
                'description': transaction['bid_description'],
                'image_url': transaction['bid_image_url'],
                'nickname': transaction['bid_nickname']
            },
            'bid_item': {
                'title': transaction['title'],
                'description': transaction['description'],
                'image_url': transaction['image_url'],
                'nickname': transaction['nickname']
            }
        })

    conn.close()

    return render_template('my_transactions.html', 
                           my_posted_transactions=transaction_data_my_posts, 
                           my_bid_transactions=transaction_data_my_bids)

@app.route('/search_items')
def search_items():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    query = request.args.get('query', '').strip()

    if not query:
        flash('검색어를 입력해주세요.')
        return redirect(url_for('main'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # 검색어가 물품 제목에 포함된 물품을 검색
    cursor.execute("SELECT * FROM items WHERE title LIKE %s", ('%' + query + '%',))
    search_results = cursor.fetchall()

    conn.close()

    return render_template('search_results.html', search_results=search_results, query=query)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000)

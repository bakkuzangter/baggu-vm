from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, join_room, leave_room as socketio_leave_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # your_secret_key should be in your .env file
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Initialize Flask-SocketIO with gevent as the async mode
socketio = SocketIO(app, async_mode='gevent')

# RDS MySQL configuration
DATABASE = 'database.db'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
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
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
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
        conn.execute('INSERT INTO users (username, password, nickname) VALUES (?, ?, ?)', (username, hashed_password, nickname))
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
    items = conn.execute('SELECT * FROM items').fetchall()
    conn.close()

    # convert image paths to URLs
    items = [dict(item) for item in items]
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
            conn.execute('INSERT INTO items (title, description, image_url, user_id, created_at, nickname) VALUES (?, ?, ?, ?, ?, ?)', 
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
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    item = dict(item)  # sqlite3.Row 객체를 dict로 변환
    item['image_url'] = url_for('static', filename=convert_path_to_url(item['image_url']))
    bids = conn.execute('SELECT * FROM bids WHERE item_id = ?', (item_id,)).fetchall()
    bids = [dict(bid) for bid in bids]
    for bid in bids:
        bid['image_url'] = url_for('static', filename=convert_path_to_url(bid['image_url']))
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
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            image_url = os.path.join('uploads', filename)
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn = get_db_connection()
            conn.execute('INSERT INTO bids (item_id, title, description, image_url, user_id, created_at, nickname) VALUES (?, ?, ?, ?, ?, ?, ?)', 
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
    bid = conn.execute('SELECT * FROM bids WHERE id = ?', (bid_id,)).fetchone()
    bid = dict(bid)  # sqlite3.Row 객체를 dict로 변환
    bid['image_url'] = url_for('static', filename=convert_path_to_url(bid['image_url']))
    conn.close()
    return render_template('bid_detail.html', bid=bid)

@app.route('/create_chat_room/<int:bid_id>')
def create_chat_room(bid_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    bid = conn.execute('SELECT * FROM bids WHERE id = ?', (bid_id,)).fetchone()
    existing_room = conn.execute('''
        SELECT * FROM chat_rooms
        WHERE bid_id = ? AND ((user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?))
    ''', (bid_id, session['user_id'], bid['user_id'], bid['user_id'], session['user_id'])).fetchone()
    
    if existing_room:
        chat_room = dict(existing_room)
    else:
        conn.execute('''
            INSERT INTO chat_rooms (bid_id, user1_id, user2_id, created_at)
            VALUES (?, ?, ?, ?)
        ''', (bid_id, session['user_id'], bid['user_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        chat_room = conn.execute('SELECT * FROM chat_rooms WHERE id = last_insert_rowid()').fetchone()
        chat_room = dict(chat_room)
    
    conn.close()
    return redirect(url_for('chat_room', room_id=chat_room['id']))

@app.route('/chat_room/<int:room_id>', methods=['GET', 'POST'])
def chat_room(room_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    room = conn.execute('SELECT * FROM chat_rooms WHERE id = ?', (room_id,)).fetchone()
    bid = conn.execute('SELECT * FROM bids WHERE id = ?', (room['bid_id'],)).fetchone()
    post_item = conn.execute('SELECT * FROM items WHERE id = ?', (bid['item_id'],)).fetchone()
    messages = conn.execute('SELECT * FROM messages WHERE room_id = ?', (room_id,)).fetchall()

    messages = [dict(message) for message in messages]
    for message in messages:
        if message['timestamp']:
            message['timestamp'] = datetime.strptime(message['timestamp'], '%Y-%m-%d %H:%M:%S')

    user_id = session['user_id']
    other_user_id = room['user2_id'] if room['user1_id'] == user_id else room['user1_id']
    other_user = conn.execute('SELECT nickname FROM users WHERE user_id = ?', (other_user_id,)).fetchone()

    # Convert sqlite3.Row objects to dictionaries
    post_item = dict(post_item)
    bid = dict(bid)
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
    conn.execute('INSERT INTO messages (room_id, sender_id, message, timestamp) VALUES (?, ?, ?, ?)',
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
    user_id = session['user_id']
    rooms = conn.execute('''
        SELECT * FROM chat_rooms
        WHERE user1_id = ? OR user2_id = ?
    ''', (user_id, user_id)).fetchall()
    rooms = [dict(room) for room in rooms]

    for room in rooms:
        bid = conn.execute('SELECT * FROM bids WHERE id = ?', (room['bid_id'],)).fetchone()
        if bid:
            room['item_title'] = bid['title']
            room['item_image_url'] = url_for('static', filename=convert_path_to_url(bid['image_url']))
            room['user1_nickname'] = conn.execute('SELECT nickname FROM users WHERE user_id = ?', (room['user1_id'],)).fetchone()['nickname']
            room['user2_nickname'] = conn.execute('SELECT nickname FROM users WHERE user_id = ?', (room['user2_id'],)).fetchone()['nickname']
    conn.close()

    return render_template('chat_rooms.html', rooms=rooms)

@app.route('/delete_item/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()

    if item and item['user_id'] == session['user_id']:
        conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
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
    room = conn.execute('SELECT * FROM chat_rooms WHERE id = ?', (room_id,)).fetchone()

    if room and (room['user1_id'] == session['user_id'] or room['user2_id'] == session['user_id']):
        conn.execute('DELETE FROM messages WHERE room_id = ?', (room_id,))
        conn.execute('DELETE FROM chat_rooms WHERE id = ?', (room_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': 'Room and messages deleted'}), 200
    else:
        conn.close()
        return jsonify({'error': 'Room not found or unauthorized'}), 404

if __name__ == '__main__':
    # Running the app using SocketIO's run method with the gevent server
    socketio.run(app, host='0.0.0.0', port=8000)

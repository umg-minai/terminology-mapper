from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DATABASE = 'database.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with schema"""
    conn = get_db()
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_points INTEGER DEFAULT 0
    )''')

    # Terms table
    c.execute('''CREATE TABLE IF NOT EXISTS terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term TEXT UNIQUE NOT NULL,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Mappings table
    c.execute('''CREATE TABLE IF NOT EXISTS mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        mapped_code TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (term_id) REFERENCES terms(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        terms_count INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    conn.commit()
    conn.close()

def import_terms_from_csv():
    """Import terms from data.CSV if not already imported"""
    conn = get_db()
    c = conn.cursor()

    # Check if terms already imported
    c.execute('SELECT COUNT(*) FROM terms')
    if c.fetchone()[0] > 0:
        conn.close()
        return

    # Import terms - try different encodings
    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
    for encoding in encodings:
        try:
            with open('data/data.CSV', 'r', encoding=encoding) as f:
                next(f)  # Skip header
                for line in f:
                    term = line.strip()
                    if term:
                        try:
                            c.execute('INSERT INTO terms (term) VALUES (?)', (term,))
                        except sqlite3.IntegrityError:
                            pass  # Skip duplicates
            conn.commit()
            break
        except UnicodeDecodeError:
            continue

    conn.close()

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_terms_for_session(count=15):
    """Get terms with lowest number of ratings (prioritize <2)"""
    conn = get_db()
    c = conn.cursor()

    # Get terms with their mapping counts
    c.execute('''
        SELECT t.id, t.term, COUNT(m.id) as mapping_count
        FROM terms t
        LEFT JOIN mappings m ON t.id = m.term_id
        GROUP BY t.id
        ORDER BY mapping_count ASC, RANDOM()
        LIMIT ?
    ''', (count,))

    terms = [dict(row) for row in c.fetchall()]
    conn.close()
    return terms

def get_user_stats(user_id):
    """Get user statistics"""
    conn = get_db()
    c = conn.cursor()

    # Total mappings
    c.execute('SELECT COUNT(*) FROM mappings WHERE user_id = ?', (user_id,))
    total_mappings = c.fetchone()[0]

    # Completed sessions
    c.execute('SELECT COUNT(*) FROM sessions WHERE user_id = ? AND completed_at IS NOT NULL', (user_id,))
    completed_sessions = c.fetchone()[0]

    # Current streak (completed sessions in last 7 days)
    c.execute('''
        SELECT COUNT(*) FROM sessions
        WHERE user_id = ?
        AND completed_at IS NOT NULL
        AND completed_at > datetime('now', '-7 days')
    ''', (user_id,))
    streak = c.fetchone()[0]

    conn.close()
    return {
        'total_mappings': total_mappings,
        'completed_sessions': completed_sessions,
        'streak': streak
    }

def get_overall_progress():
    """Get overall progress statistics"""
    conn = get_db()
    c = conn.cursor()

    # Total terms
    c.execute('SELECT COUNT(*) FROM terms')
    total_terms = c.fetchone()[0]

    # Terms with at least 2 mappings
    c.execute('''
        SELECT COUNT(DISTINCT term_id)
        FROM mappings
        GROUP BY term_id
        HAVING COUNT(*) >= 2
    ''')
    completed_terms = len(c.fetchall())

    conn.close()
    return {
        'total_terms': total_terms,
        'completed_terms': completed_terms,
        'percentage': round((completed_terms / total_terms * 100) if total_terms > 0 else 0, 1)
    }

def get_leaderboard(limit=10):
    """Get top users by total mappings"""
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        SELECT u.username, COUNT(m.id) as mappings_count
        FROM users u
        LEFT JOIN mappings m ON u.id = m.user_id
        GROUP BY u.id
        ORDER BY mappings_count DESC
        LIMIT ?
    ''', (limit,))

    leaderboard = [dict(row) for row in c.fetchall()]
    conn.close()
    return leaderboard

@app.route('/')
def index():
    """Landing page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login or create user"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()

        if not username:
            return render_template('login.html', error='Please enter a username')

        conn = get_db()
        c = conn.cursor()

        # Check if user exists
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        user = c.fetchone()

        if user:
            user_id = user[0]
        else:
            # Create new user
            c.execute('INSERT INTO users (username) VALUES (?)', (username,))
            user_id = c.lastrowid
            conn.commit()

        conn.close()

        session['user_id'] = user_id
        session['username'] = username
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    user_stats = get_user_stats(session['user_id'])
    overall_progress = get_overall_progress()
    leaderboard = get_leaderboard()

    return render_template('dashboard.html',
                         username=session['username'],
                         stats=user_stats,
                         progress=overall_progress,
                         leaderboard=leaderboard)

@app.route('/session/start', methods=['POST'])
@login_required
def start_session():
    """Start a new mapping session"""
    terms_count = int(request.form.get('count', 15))

    # Create session
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO sessions (user_id, terms_count) VALUES (?, ?)',
              (session['user_id'], terms_count))
    session_id = c.lastrowid
    conn.commit()
    conn.close()

    session['current_session'] = session_id
    session['session_terms'] = get_terms_for_session(terms_count)
    session['current_index'] = 0

    return redirect(url_for('mapping_session'))

@app.route('/session')
@login_required
def mapping_session():
    """Active mapping session"""
    if 'session_terms' not in session or 'current_index' not in session:
        return redirect(url_for('dashboard'))

    current_index = session['current_index']
    terms = session['session_terms']

    if current_index >= len(terms):
        return redirect(url_for('complete_session'))

    current_term = terms[current_index]
    progress_percent = round((current_index / len(terms)) * 100)

    return render_template('session.html',
                         term=current_term,
                         current=current_index + 1,
                         total=len(terms),
                         progress=progress_percent)

@app.route('/session/submit', methods=['POST'])
@login_required
def submit_mapping():
    """Submit a mapping for current term"""
    if 'session_terms' not in session or 'current_index' not in session:
        return redirect(url_for('dashboard'))

    current_index = session['current_index']
    terms = session['session_terms']

    if current_index >= len(terms):
        return redirect(url_for('complete_session'))

    term_id = terms[current_index]['id']
    mapped_code = request.form.get('code', '').strip()

    if mapped_code:
        # Save mapping
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT INTO mappings (term_id, user_id, mapped_code) VALUES (?, ?, ?)',
                  (term_id, session['user_id'], mapped_code))
        conn.commit()
        conn.close()

    # Move to next term
    session['current_index'] = current_index + 1

    return redirect(url_for('mapping_session'))

@app.route('/session/complete')
@login_required
def complete_session():
    """Complete current session"""
    if 'current_session' not in session:
        return redirect(url_for('dashboard'))

    # Mark session as completed
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE sessions SET completed_at = CURRENT_TIMESTAMP WHERE id = ?',
              (session['current_session'],))

    # Get session stats
    c.execute('SELECT COUNT(*) FROM mappings WHERE user_id = ? AND created_at > (SELECT started_at FROM sessions WHERE id = ?)',
              (session['user_id'], session['current_session']))
    mappings_count = c.fetchone()[0]

    conn.commit()
    conn.close()

    # Clear session data
    session.pop('current_session', None)
    session.pop('session_terms', None)
    session.pop('current_index', None)

    return render_template('complete.html', mappings_count=mappings_count)

if __name__ == '__main__':
    init_db()
    import_terms_from_csv()
    app.run(debug=True, host='0.0.0.0', port=5000)

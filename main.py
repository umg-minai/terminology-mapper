from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import sqlite3
import secrets
import csv
from datetime import datetime
from typing import Optional, List
import json
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
import yaml
import ssl
import traceback

# Load configuration from YAML file
CONFIG_FILE = 'config.yaml'

def load_config():
    """Load configuration from YAML file"""
    if not os.path.exists(CONFIG_FILE):
        print(f"ERROR: Configuration file '{CONFIG_FILE}' not found!")
        print(f"Please copy 'config.example.yaml' to '{CONFIG_FILE}' and customize it.")
        sys.exit(1)
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML in configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        sys.exit(1)

# Load configuration
config = load_config()

# Extract configuration sections
DATABASE = config['database']['path']
GLOBAL_PASSWORD = config['passwords']['global_password']
ADMIN_PASSWORD = config['passwords']['admin_password']
DATA_IMPORT_CONFIG = config['data_import']
IMPRINT_CONFIG = config['imprint']
DATENSCHUTZ_CONFIG = config['datenschutz']
CONTACT_CONFIG = config['contact']
EMAIL_CONFIG = config['email']

# Middleware to add X-Robots-Tag header to all responses
class RobotsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
        return response

app = FastAPI()
app.add_middleware(RobotsMiddleware)
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def send_contact_email(name: str, email: str, subject: str, message: str):
    """Send contact form email"""
    if not CONTACT_CONFIG.get('send_email', False):
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[Kontaktformular] {subject}"
        msg['From'] = f"{EMAIL_CONFIG['from_name']} <{EMAIL_CONFIG['from_email']}>"
        msg['To'] = CONTACT_CONFIG['email']
        msg['Reply-To'] = email
        
        # Create email body
        text_body = f"""
Neue Nachricht über das Kontaktformular

Von: {name}
E-Mail: {email}
Betreff: {subject}

Nachricht:
{message}

---
Diese E-Mail wurde über das Kontaktformular auf {DATENSCHUTZ_CONFIG.get('website', 'terminology-mapper.de')} gesendet.
"""
        
        html_body = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4f46e5; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f8fafc; padding: 20px; border: 1px solid #e2e8f0; }}
        .field {{ margin-bottom: 15px; }}
        .label {{ font-weight: bold; color: #64748b; }}
        .message-box {{ background: white; padding: 15px; border-left: 4px solid #4f46e5; margin-top: 10px; }}
        .footer {{ text-align: center; color: #64748b; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">Neue Kontaktanfrage</h2>
        </div>
        <div class="content">
            <div class="field">
                <span class="label">Von:</span> {name}
            </div>
            <div class="field">
                <span class="label">E-Mail:</span> <a href="mailto:{email}">{email}</a>
            </div>
            <div class="field">
                <span class="label">Betreff:</span> {subject}
            </div>
            <div class="field">
                <span class="label">Nachricht:</span>
                <div class="message-box">{message.replace(chr(10), '<br>')}</div>
            </div>
        </div>
        <div class="footer">
            Diese E-Mail wurde über das Kontaktformular auf {DATENSCHUTZ_CONFIG.get('website', 'terminology-mapper.de')} gesendet.
        </div>
    </div>
</body>
</html>
"""
        
        # Attach both plain text and HTML versions
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email using TLS or SSL
        use_tls = EMAIL_CONFIG.get('use_tls', True)
        use_ssl = EMAIL_CONFIG.get('use_ssl', False)
        smtp_server = EMAIL_CONFIG['smtp_server']
        smtp_port = EMAIL_CONFIG['smtp_port']
        username = EMAIL_CONFIG['username']
        password = EMAIL_CONFIG['password']
        
        # Create SSL context
        context = ssl.create_default_context()
        
        # Determine envelope sender (can be different from From header)
        envelope_from = EMAIL_CONFIG.get('envelope_from', EMAIL_CONFIG['from_email'])
        recipients = [CONTACT_CONFIG['email']]
        
        if use_ssl or smtp_port == 465:
            # Use SSL (port 465 typically)
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=30) as server:
                server.login(username, password)
                refused = server.sendmail(envelope_from, recipients, msg.as_string())
                if refused:
                    print(f"Refused recipients: {refused}", file=sys.stderr)
        else:
            # Use STARTTLS (port 587 typically) or plain SMTP
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(username, password)
                refused = server.sendmail(envelope_from, recipients, msg.as_string())
                if refused:
                    print(f"Refused recipients: {refused}", file=sys.stderr)
        
        return True
    except smtplib.SMTPResponseException as e:
        print(f"SMTP error {e.smtp_code}: {e.smtp_error!r}", file=sys.stderr)
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"Error sending email: {e}", file=sys.stderr)
        traceback.print_exc()
        return False

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

    # Terms table - now with category
    c.execute('''CREATE TABLE IF NOT EXISTS terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        term TEXT NOT NULL,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(category, term)
    )''')

    # Mappings table - updated to support multiple codes
    c.execute('''CREATE TABLE IF NOT EXISTS mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        codes TEXT NOT NULL,
        no_code_found BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (term_id) REFERENCES terms(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(term_id, user_id)
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

    # Contact messages table
    c.execute('''CREATE TABLE IF NOT EXISTS contact_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        read BOOLEAN DEFAULT 0
    )''')

    conn.commit()
    conn.close()

def import_terms_from_csv():
    """Import terms from data.CSV with category and item columns"""
    conn = get_db()
    c = conn.cursor()

    # Check if terms already imported
    c.execute('SELECT COUNT(*) FROM terms')
    if c.fetchone()[0] > 0:
        conn.close()
        return

    # Import terms from CSV using configuration
    csv_path = DATA_IMPORT_CONFIG['csv_path']
    encoding = DATA_IMPORT_CONFIG['encoding']
    delimiter = DATA_IMPORT_CONFIG['delimiter']
    
    try:
        with open(csv_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                category = row.get('Kategorie', '').strip()
                term = row.get('Item', '').strip()
                if category and term:
                    try:
                        c.execute('INSERT INTO terms (category, term) VALUES (?, ?)', (category, term))
                    except sqlite3.IntegrityError:
                        pass  # Skip duplicates
        
        conn.commit()
        print(f"Successfully imported terms from {csv_path}")
    except FileNotFoundError:
        print(f"WARNING: CSV file not found at {csv_path}")
    except Exception as e:
        print(f"ERROR importing terms: {e}")
    finally:
        conn.close()

def get_current_user(request: Request):
    """Get current user from session"""
    user_id = request.session.get('user_id')
    username = request.session.get('username')
    if not user_id or not username:
        return None
    return {'user_id': user_id, 'username': username}

def get_terms_for_session(count=15, user_id=None):
    """Get terms with lowest number of UNIQUE ratings (prioritize <2 unique users)"""
    conn = get_db()
    c = conn.cursor()

    # Get terms with count of DISTINCT users who have rated them
    # Exclude terms this user has already rated
    if user_id:
        c.execute('''
            SELECT t.id, t.category, t.term,
                   COUNT(DISTINCT m.user_id) as mapping_count
            FROM terms t
            LEFT JOIN mappings m ON t.id = m.term_id
            WHERE t.id NOT IN (
                SELECT term_id FROM mappings WHERE user_id = ?
            )
            GROUP BY t.id
            ORDER BY mapping_count ASC, RANDOM()
            LIMIT ?
        ''', (user_id, count))
    else:
        c.execute('''
            SELECT t.id, t.category, t.term,
                   COUNT(DISTINCT m.user_id) as mapping_count
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

    # Current streak
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

    # Terms with at least 2 mappings from UNIQUE users
    c.execute('''
        SELECT COUNT(*) FROM (
            SELECT term_id
            FROM mappings
            GROUP BY term_id
            HAVING COUNT(DISTINCT user_id) >= 2
        )
    ''')
    completed_terms = c.fetchone()[0]

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

@app.on_event("startup")
async def startup_event():
    init_db()
    import_terms_from_csv()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Login or create user"""
    if not username.strip():
        return templates.TemplateResponse("login.html",
            {"request": request, "error": "Please enter a username"})

    # Check password
    if password != GLOBAL_PASSWORD:
        return templates.TemplateResponse("login.html",
            {"request": request, "error": "Invalid password"})

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

    request.session['user_id'] = user_id
    request.session['username'] = username
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/logout")
async def logout(request: Request):
    """Logout user"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """User dashboard"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    user_stats = get_user_stats(user['user_id'])
    overall_progress = get_overall_progress()
    leaderboard = get_leaderboard()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": user['username'],
        "stats": user_stats,
        "progress": overall_progress,
        "leaderboard": leaderboard
    })

@app.post("/session/start")
async def start_session(request: Request, count: int = Form(15)):
    """Start a new mapping session"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Create session
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO sessions (user_id, terms_count) VALUES (?, ?)',
              (user['user_id'], count))
    session_id = c.lastrowid
    conn.commit()
    conn.close()

    request.session['current_session'] = session_id
    request.session['session_terms'] = get_terms_for_session(count, user['user_id'])
    request.session['current_index'] = 0

    return RedirectResponse(url="/session", status_code=302)

@app.get("/session", response_class=HTMLResponse)
async def mapping_session(request: Request):
    """Active mapping session"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    session_terms = request.session.get('session_terms')
    current_index = request.session.get('current_index')

    if not session_terms or current_index is None:
        return RedirectResponse(url="/dashboard", status_code=302)

    if current_index >= len(session_terms):
        return RedirectResponse(url="/session/complete", status_code=302)

    current_term = session_terms[current_index]
    progress_percent = round((current_index / len(session_terms)) * 100)

    return templates.TemplateResponse("session.html", {
        "request": request,
        "term": current_term,
        "current": current_index + 1,
        "total": len(session_terms),
        "progress": progress_percent
    })

@app.post("/session/submit")
async def submit_mapping(
    request: Request,
    codes_json: str = Form("[]"),
    no_code_found: bool = Form(False)
):
    """Submit a mapping for current term"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    session_terms = request.session.get('session_terms')
    current_index = request.session.get('current_index')

    if not session_terms or current_index is None or current_index >= len(session_terms):
        return RedirectResponse(url="/dashboard", status_code=302)

    term_id = session_terms[current_index]['id']

    # Save mapping (with error handling for duplicates)
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO mappings (term_id, user_id, codes, no_code_found) VALUES (?, ?, ?, ?)',
                  (term_id, user['user_id'], codes_json, no_code_found))
        conn.commit()
    except sqlite3.IntegrityError:
        # User already rated this term - skip it
        pass
    finally:
        conn.close()

    # Move to next term
    request.session['current_index'] = current_index + 1

    return RedirectResponse(url="/session", status_code=302)

@app.get("/session/complete", response_class=HTMLResponse)
async def complete_session(request: Request):
    """Complete current session"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    current_session = request.session.get('current_session')
    if not current_session:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Mark session as completed
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE sessions SET completed_at = CURRENT_TIMESTAMP WHERE id = ?',
              (current_session,))

    # Get session stats
    c.execute('SELECT COUNT(*) FROM mappings WHERE user_id = ? AND created_at > (SELECT started_at FROM sessions WHERE id = ?)',
              (user['user_id'], current_session))
    mappings_count = c.fetchone()[0]

    conn.commit()
    conn.close()

    # Clear session data
    request.session.pop('current_session', None)
    request.session.pop('session_terms', None)
    request.session.pop('current_index', None)

    return templates.TemplateResponse("complete.html", {
        "request": request,
        "mappings_count": mappings_count
    })

# Admin Console Routes
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Admin console login page"""
    # Check if already logged in as admin
    if request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin/console", status_code=302)
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    """Admin login"""
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse("admin_login.html",
            {"request": request, "error": "Invalid admin password"})

    request.session['admin_logged_in'] = True
    return RedirectResponse(url="/admin/console", status_code=302)

@app.get("/admin/console", response_class=HTMLResponse)
async def admin_console(request: Request):
    """Admin console dashboard"""
    if not request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin", status_code=302)

    # Get statistics
    conn = get_db()
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM terms')
    total_terms = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM mappings')
    total_mappings = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM contact_messages')
    total_messages = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM contact_messages WHERE read = 0')
    unread_messages = c.fetchone()[0]

    c.execute('SELECT username FROM users ORDER BY username')
    users = [row[0] for row in c.fetchall()]

    conn.close()

    return templates.TemplateResponse("admin_console.html", {
        "request": request,
        "total_terms": total_terms,
        "total_mappings": total_mappings,
        "total_users": total_users,
        "total_messages": total_messages,
        "unread_messages": unread_messages,
        "users": users
    })

@app.get("/admin/export")
async def export_mappings(request: Request):
    """Export all mappings as CSV"""
    if not request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin", status_code=302)

    conn = get_db()
    c = conn.cursor()

    c.execute('''
        SELECT u.username, t.category, t.term, m.codes, m.no_code_found, m.created_at
        FROM mappings m
        JOIN users u ON m.user_id = u.id
        JOIN terms t ON m.term_id = t.id
        ORDER BY m.created_at DESC
    ''')

    rows = c.fetchall()
    conn.close()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Username', 'Category', 'Term', 'Codes', 'No Code Found', 'Created At'])

    for row in rows:
        writer.writerow(row)

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=mappings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

@app.post("/admin/reset/mappings")
async def reset_mappings(request: Request):
    """Delete all mappings"""
    if not request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin", status_code=302)

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM mappings')
    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin/console?message=All mappings deleted", status_code=302)

@app.post("/admin/reset/all")
async def reset_all(request: Request):
    """Delete all mappings and terms"""
    if not request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin", status_code=302)

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM mappings')
    c.execute('DELETE FROM terms')
    conn.commit()
    conn.close()

    # Re-import terms
    import_terms_from_csv()

    return RedirectResponse(url="/admin/console?message=Database reset and terms re-imported", status_code=302)

@app.post("/admin/reset/user")
async def reset_user_mappings(request: Request, username: str = Form(...)):
    """Delete mappings for a specific user"""
    if not request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin", status_code=302)

    conn = get_db()
    c = conn.cursor()

    # Get user ID
    c.execute('SELECT id FROM users WHERE username = ?', (username,))
    user = c.fetchone()

    if user:
        c.execute('DELETE FROM mappings WHERE user_id = ?', (user[0],))
        conn.commit()
        message = f"Mappings deleted for user: {username}"
    else:
        message = f"User not found: {username}"

    conn.close()

    return RedirectResponse(url=f"/admin/console?message={message}", status_code=302)

@app.get("/admin/logout")
async def admin_logout(request: Request):
    """Admin logout"""
    request.session.pop('admin_logged_in', None)
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/admin/messages", response_class=HTMLResponse)
async def admin_messages(request: Request):
    """View contact messages"""
    if not request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin", status_code=302)

    conn = get_db()
    c = conn.cursor()

    c.execute('''SELECT id, name, email, subject, message, created_at, read 
                 FROM contact_messages 
                 ORDER BY created_at DESC''')
    messages = [dict(row) for row in c.fetchall()]

    conn.close()

    return templates.TemplateResponse("admin_messages.html", {
        "request": request,
        "messages": messages
    })

@app.post("/admin/messages/{message_id}/mark-read")
async def mark_message_read(request: Request, message_id: int):
    """Mark a contact message as read"""
    if not request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin", status_code=302)

    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE contact_messages SET read = 1 WHERE id = ?', (message_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin/messages", status_code=302)

@app.post("/admin/messages/{message_id}/delete")
async def delete_message(request: Request, message_id: int):
    """Delete a contact message"""
    if not request.session.get('admin_logged_in'):
        return RedirectResponse(url="/admin", status_code=302)

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM contact_messages WHERE id = ?', (message_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin/messages", status_code=302)

# Robots.txt Route
@app.get("/robots.txt")
async def robots_txt():
    """Serve robots.txt to prevent search engine indexing"""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("User-agent: *\nDisallow: /\n", headers={"X-Robots-Tag": "noindex, nofollow"})

# Imprint Route
@app.get("/imprint", response_class=HTMLResponse)
async def imprint(request: Request):
    """Display imprint page (Impressum)"""
    if not IMPRINT_CONFIG.get('enabled', True):
        raise HTTPException(status_code=404, detail="Imprint not available")

    return templates.TemplateResponse("imprint.html", {
        "request": request,
        "imprint": IMPRINT_CONFIG
    })

# Data Protection Route
@app.get("/datenschutz", response_class=HTMLResponse)
async def datenschutz(request: Request):
    """Display data protection page (Datenschutzerklärung)"""
    if not DATENSCHUTZ_CONFIG.get('enabled', True):
        raise HTTPException(status_code=404, detail="Data protection page not available")

    return templates.TemplateResponse("datenschutz.html", {
        "request": request,
        "datenschutz": DATENSCHUTZ_CONFIG
    })

# Contact Form Routes
@app.get("/contact", response_class=HTMLResponse)
async def contact_form(request: Request, success: bool = False):
    """Display contact form"""
    if not CONTACT_CONFIG.get('enabled', True):
        raise HTTPException(status_code=404, detail="Contact form not available")

    return templates.TemplateResponse("contact.html", {
        "request": request,
        "contact": CONTACT_CONFIG,
        "success": success
    })

@app.post("/contact/submit")
async def submit_contact(request: Request, 
                        name: str = Form(...),
                        email: str = Form(...),
                        subject: str = Form(...),
                        message: str = Form(...)):
    """Submit contact form"""
    if not CONTACT_CONFIG.get('enabled', True):
        raise HTTPException(status_code=404, detail="Contact form not available")

    # Basic validation
    if not name.strip() or not email.strip() or not message.strip():
        return templates.TemplateResponse("contact.html", {
            "request": request,
            "contact": CONTACT_CONFIG,
            "error": "Bitte füllen Sie alle erforderlichen Felder aus."
        })

    # Store in database if enabled
    if CONTACT_CONFIG.get('store_in_db', True):
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO contact_messages (name, email, subject, message) 
                     VALUES (?, ?, ?, ?)''',
                  (name, email, subject, message))
        conn.commit()
        conn.close()

    # Send email if enabled
    if CONTACT_CONFIG.get('send_email', False):
        email_sent = send_contact_email(name, email, subject, message)
        if not email_sent:
            print("Warning: Failed to send contact form email")

    # Redirect to contact page with success message
    return RedirectResponse(url="/contact?success=true", status_code=302)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

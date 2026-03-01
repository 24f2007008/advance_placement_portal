from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from database import init_db, get_db
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'placement_portal_secret_key_2026'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─────────────────────────── AUTH ───────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role']
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        if role == 'admin':
            user = db.execute('SELECT * FROM admin WHERE email=? AND password=?', (email, password)).fetchone()
            if user:
                session['user_id'] = user['id']
                session['role'] = 'admin'
                session['name'] = user['name']
                return redirect(url_for('admin_dashboard'))
        elif role == 'company':
            user = db.execute('SELECT * FROM company WHERE email=? AND password=?', (email, password)).fetchone()
            if user:
                if user['approval_status'] != 'approved':
                    flash('Your account is pending approval or has been rejected/blacklisted.', 'warning')
                    return redirect(url_for('login'))
                session['user_id'] = user['id']
                session['role'] = 'company'
                session['name'] = user['company_name']
                return redirect(url_for('company_dashboard'))
        elif role == 'student':
            user = db.execute('SELECT * FROM student WHERE email=? AND password=?', (email, password)).fetchone()
            if user:
                if user['is_active'] == 0:
                    flash('Your account has been deactivated.', 'warning')
                    return redirect(url_for('login'))
                session['user_id'] = user['id']
                session['role'] = 'student'
                session['name'] = user['name']
                return redirect(url_for('student_dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        db = get_db()
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        branch = request.form['branch']
        cgpa = request.form['cgpa']
        graduation_year = request.form['graduation_year']
        existing = db.execute('SELECT id FROM student WHERE email=?', (email,)).fetchone()
        if existing:
            flash('Email already registered.', 'danger')
            return redirect(url_for('register_student'))
        db.execute('INSERT INTO student (name, email, password, phone, branch, cgpa, graduation_year, is_active) VALUES (?,?,?,?,?,?,?,1)',
                   (name, email, password, phone, branch, cgpa, graduation_year))
        db.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register_student.html')

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        db = get_db()
        company_name = request.form['company_name']
        email = request.form['email']
        password = request.form['password']
        hr_contact = request.form['hr_contact']
        website = request.form['website']
        industry = request.form['industry']
        description = request.form['description']
        existing = db.execute('SELECT id FROM company WHERE email=?', (email,)).fetchone()
        if existing:
            flash('Email already registered.', 'danger')
            return redirect(url_for('register_company'))
        db.execute('INSERT INTO company (company_name, email, password, hr_contact, website, industry, description, approval_status) VALUES (?,?,?,?,?,?,?,?)',
                   (company_name, email, password, hr_contact, website, industry, description, 'pending'))
        db.commit()
        flash('Registration submitted! Wait for admin approval.', 'success')
        return redirect(url_for('login'))
    return render_template('register_company.html')

# ─────────────────────────── ADMIN ───────────────────────────

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'total_students': db.execute('SELECT COUNT(*) FROM student').fetchone()[0],
        'total_companies': db.execute('SELECT COUNT(*) FROM company WHERE approval_status="approved"').fetchone()[0],
        'total_drives': db.execute('SELECT COUNT(*) FROM placement_drive').fetchone()[0],
        'total_applications': db.execute('SELECT COUNT(*) FROM application').fetchone()[0],
        'pending_companies': db.execute('SELECT COUNT(*) FROM company WHERE approval_status="pending"').fetchone()[0],
        'pending_drives': db.execute('SELECT COUNT(*) FROM placement_drive WHERE status="pending"').fetchone()[0],
    }
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/companies')
@admin_required
def admin_companies():
    db = get_db()
    q = request.args.get('q', '')
    if q:
        companies = db.execute('SELECT * FROM company WHERE company_name LIKE ? OR id LIKE ?', (f'%{q}%', f'%{q}%')).fetchall()
    else:
        companies = db.execute('SELECT * FROM company').fetchall()
    return render_template('admin/companies.html', companies=companies, q=q)

@app.route('/admin/company/<int:cid>/action/<action>')
@admin_required
def admin_company_action(cid, action):
    db = get_db()
    if action in ('approve', 'reject', 'blacklist'):
        status_map = {'approve': 'approved', 'reject': 'rejected', 'blacklist': 'blacklisted'}
        db.execute('UPDATE company SET approval_status=? WHERE id=?', (status_map[action], cid))
        db.commit()
        flash(f'Company {action}d successfully.', 'success')
    elif action == 'delete':
        db.execute('DELETE FROM company WHERE id=?', (cid,))
        db.commit()
        flash('Company deleted.', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/students')
@admin_required
def admin_students():
    db = get_db()
    q = request.args.get('q', '')
    if q:
        students = db.execute('SELECT * FROM student WHERE name LIKE ? OR id LIKE ? OR phone LIKE ?', (f'%{q}%', f'%{q}%', f'%{q}%')).fetchall()
    else:
        students = db.execute('SELECT * FROM student').fetchall()
    return render_template('admin/students.html', students=students, q=q)

@app.route('/admin/student/<int:sid>/action/<action>')
@admin_required
def admin_student_action(sid, action):
    db = get_db()
    if action == 'deactivate':
        db.execute('UPDATE student SET is_active=0 WHERE id=?', (sid,))
        db.commit()
        flash('Student deactivated.', 'success')
    elif action == 'activate':
        db.execute('UPDATE student SET is_active=1 WHERE id=?', (sid,))
        db.commit()
        flash('Student activated.', 'success')
    elif action == 'delete':
        db.execute('DELETE FROM student WHERE id=?', (sid,))
        db.commit()
        flash('Student deleted.', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/drives')
@admin_required
def admin_drives():
    db = get_db()
    drives = db.execute('''SELECT pd.*, c.company_name FROM placement_drive pd
                           JOIN company c ON pd.company_id = c.id ORDER BY pd.id DESC''').fetchall()
    return render_template('admin/drives.html', drives=drives)

@app.route('/admin/drive/<int:did>/action/<action>')
@admin_required
def admin_drive_action(did, action):
    db = get_db()
    if action in ('approve', 'reject'):
        db.execute('UPDATE placement_drive SET status=? WHERE id=?', (action + 'd' if action == 'approve' else 'rejected', did))
        # fix: approved
        if action == 'approve':
            db.execute('UPDATE placement_drive SET status="approved" WHERE id=?', (did,))
        db.commit()
        flash(f'Drive {action}d.', 'success')
    elif action == 'close':
        db.execute('UPDATE placement_drive SET status="closed" WHERE id=?', (did,))
        db.commit()
        flash('Drive closed.', 'success')
    elif action == 'delete':
        db.execute('DELETE FROM placement_drive WHERE id=?', (did,))
        db.commit()
        flash('Drive deleted.', 'success')
    return redirect(url_for('admin_drives'))

@app.route('/admin/applications')
@admin_required
def admin_applications():
    db = get_db()
    apps = db.execute('''SELECT a.*, s.name as student_name, pd.job_title, c.company_name
                         FROM application a
                         JOIN student s ON a.student_id = s.id
                         JOIN placement_drive pd ON a.drive_id = pd.id
                         JOIN company c ON pd.company_id = c.id
                         ORDER BY a.id DESC''').fetchall()
    return render_template('admin/applications.html', apps=apps)

# ─────────────────────────── COMPANY ───────────────────────────

def company_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'company':
            flash('Company access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/company/dashboard')
@company_required
def company_dashboard():
    db = get_db()
    company = db.execute('SELECT * FROM company WHERE id=?', (session['user_id'],)).fetchone()
    drives = db.execute('''SELECT pd.*, COUNT(a.id) as applicant_count
                           FROM placement_drive pd
                           LEFT JOIN application a ON pd.id = a.drive_id
                           WHERE pd.company_id=? GROUP BY pd.id ORDER BY pd.id DESC''', (session['user_id'],)).fetchall()
    return render_template('company/dashboard.html', company=company, drives=drives)

@app.route('/company/drive/create', methods=['GET', 'POST'])
@company_required
def company_create_drive():
    if request.method == 'POST':
        db = get_db()
        job_title = request.form['job_title']
        job_description = request.form['job_description']
        eligibility = request.form['eligibility']
        deadline = request.form['deadline']
        salary = request.form['salary']
        location = request.form['location']
        db.execute('''INSERT INTO placement_drive (company_id, job_title, job_description, eligibility_criteria,
                      application_deadline, salary, location, status) VALUES (?,?,?,?,?,?,?,"pending")''',
                   (session['user_id'], job_title, job_description, eligibility, deadline, salary, location))
        db.commit()
        flash('Drive created! Waiting for admin approval.', 'success')
        return redirect(url_for('company_dashboard'))
    return render_template('company/create_drive.html')

@app.route('/company/drive/<int:did>/edit', methods=['GET', 'POST'])
@company_required
def company_edit_drive(did):
    db = get_db()
    drive = db.execute('SELECT * FROM placement_drive WHERE id=? AND company_id=?', (did, session['user_id'])).fetchone()
    if not drive:
        flash('Drive not found.', 'danger')
        return redirect(url_for('company_dashboard'))
    if request.method == 'POST':
        job_title = request.form['job_title']
        job_description = request.form['job_description']
        eligibility = request.form['eligibility']
        deadline = request.form['deadline']
        salary = request.form['salary']
        location = request.form['location']
        db.execute('''UPDATE placement_drive SET job_title=?, job_description=?, eligibility_criteria=?,
                      application_deadline=?, salary=?, location=?, status="pending" WHERE id=?''',
                   (job_title, job_description, eligibility, deadline, salary, location, did))
        db.commit()
        flash('Drive updated. Re-submitted for approval.', 'success')
        return redirect(url_for('company_dashboard'))
    return render_template('company/edit_drive.html', drive=drive)

@app.route('/company/drive/<int:did>/action/<action>')
@company_required
def company_drive_action(did, action):
    db = get_db()
    drive = db.execute('SELECT * FROM placement_drive WHERE id=? AND company_id=?', (did, session['user_id'])).fetchone()
    if not drive:
        flash('Drive not found.', 'danger')
        return redirect(url_for('company_dashboard'))
    if action == 'close':
        db.execute('UPDATE placement_drive SET status="closed" WHERE id=?', (did,))
        db.commit()
        flash('Drive closed.', 'success')
    elif action == 'delete':
        db.execute('DELETE FROM placement_drive WHERE id=?', (did,))
        db.commit()
        flash('Drive deleted.', 'success')
    return redirect(url_for('company_dashboard'))

@app.route('/company/drive/<int:did>/applications')
@company_required
def company_drive_applications(did):
    db = get_db()
    drive = db.execute('SELECT * FROM placement_drive WHERE id=? AND company_id=?', (did, session['user_id'])).fetchone()
    if not drive:
        flash('Drive not found.', 'danger')
        return redirect(url_for('company_dashboard'))
    apps = db.execute('''SELECT a.*, s.name, s.email, s.phone, s.branch, s.cgpa, s.resume_path
                         FROM application a JOIN student s ON a.student_id = s.id
                         WHERE a.drive_id=? ORDER BY a.id''', (did,)).fetchall()
    return render_template('company/applications.html', drive=drive, apps=apps)

@app.route('/company/application/<int:aid>/status', methods=['POST'])
@company_required
def company_update_application(aid):
    db = get_db()
    new_status = request.form['status']
    app_row = db.execute('''SELECT a.*, pd.company_id FROM application a
                            JOIN placement_drive pd ON a.drive_id = pd.id WHERE a.id=?''', (aid,)).fetchone()
    if not app_row or app_row['company_id'] != session['user_id']:
        flash('Not authorized.', 'danger')
        return redirect(url_for('company_dashboard'))
    db.execute('UPDATE application SET status=? WHERE id=?', (new_status, aid))
    db.commit()
    flash('Application status updated.', 'success')
    return redirect(url_for('company_drive_applications', did=app_row['drive_id']))

# ─────────────────────────── STUDENT ───────────────────────────

def student_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Student access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    db = get_db()
    student = db.execute('SELECT * FROM student WHERE id=?', (session['user_id'],)).fetchone()
    approved_drives = db.execute('''SELECT pd.*, c.company_name FROM placement_drive pd
                                    JOIN company c ON pd.company_id = c.id
                                    WHERE pd.status="approved" ORDER BY pd.application_deadline''').fetchall()
    my_applications = db.execute('''SELECT a.*, pd.job_title, c.company_name
                                    FROM application a
                                    JOIN placement_drive pd ON a.drive_id = pd.id
                                    JOIN company c ON pd.company_id = c.id
                                    WHERE a.student_id=? ORDER BY a.application_date DESC''', (session['user_id'],)).fetchall()
    applied_drive_ids = {row['drive_id'] for row in my_applications}
    return render_template('student/dashboard.html', student=student, approved_drives=approved_drives,
                           my_applications=my_applications, applied_drive_ids=applied_drive_ids)

@app.route('/student/apply/<int:did>', methods=['POST'])
@student_required
def student_apply(did):
    db = get_db()
    existing = db.execute('SELECT id FROM application WHERE student_id=? AND drive_id=?', (session['user_id'], did)).fetchone()
    if existing:
        flash('You have already applied for this drive.', 'warning')
        return redirect(url_for('student_dashboard'))
    drive = db.execute('SELECT * FROM placement_drive WHERE id=? AND status="approved"', (did,)).fetchone()
    if not drive:
        flash('Drive not available.', 'danger')
        return redirect(url_for('student_dashboard'))
    db.execute('INSERT INTO application (student_id, drive_id, application_date, status) VALUES (?,?,?,?)',
               (session['user_id'], did, datetime.now().strftime('%Y-%m-%d'), 'applied'))
    db.commit()
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/student/profile', methods=['GET', 'POST'])
@student_required
def student_profile():
    db = get_db()
    student = db.execute('SELECT * FROM student WHERE id=?', (session['user_id'],)).fetchone()
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        branch = request.form['branch']
        cgpa = request.form['cgpa']
        graduation_year = request.form['graduation_year']
        skills = request.form['skills']
        bio = request.form['bio']
        resume_path = student['resume_path']
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"resume_{session['user_id']}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                resume_path = filename
        db.execute('''UPDATE student SET name=?, phone=?, branch=?, cgpa=?, graduation_year=?,
                      skills=?, bio=?, resume_path=? WHERE id=?''',
                   (name, phone, branch, cgpa, graduation_year, skills, bio, resume_path, session['user_id']))
        db.commit()
        session['name'] = name
        flash('Profile updated.', 'success')
        return redirect(url_for('student_profile'))
    return render_template('student/profile.html', student=student)

@app.route('/student/history')
@student_required
def student_history():
    db = get_db()
    history = db.execute('''SELECT a.*, pd.job_title, pd.salary, pd.location, c.company_name
                            FROM application a
                            JOIN placement_drive pd ON a.drive_id = pd.id
                            JOIN company c ON pd.company_id = c.id
                            WHERE a.student_id=? ORDER BY a.application_date DESC''', (session['user_id'],)).fetchall()
    return render_template('student/history.html', history=history)

# ─────────────────────────── API ───────────────────────────

@app.route('/api/drives')
def api_drives():
    db = get_db()
    drives = db.execute('''SELECT pd.id, pd.job_title, pd.job_description, pd.eligibility_criteria,
                           pd.application_deadline, pd.salary, pd.location, pd.status, c.company_name
                           FROM placement_drive pd JOIN company c ON pd.company_id = c.id
                           WHERE pd.status="approved"''').fetchall()
    return jsonify([dict(d) for d in drives])

@app.route('/api/students')
def api_students():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    students = db.execute('SELECT id, name, email, branch, cgpa, graduation_year FROM student').fetchall()
    return jsonify([dict(s) for s in students])

@app.route('/api/applications/<int:drive_id>')
def api_applications(drive_id):
    if session.get('role') not in ('admin', 'company'):
        return jsonify({'error': 'Unauthorized'}), 401
    db = get_db()
    apps = db.execute('''SELECT a.id, s.name, s.email, a.status, a.application_date
                         FROM application a JOIN student s ON a.student_id = s.id
                         WHERE a.drive_id=?''', (drive_id,)).fetchall()
    return jsonify([dict(a) for a in apps])

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

if __name__ == '__main__':
    init_db()
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)

from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'skillorax-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///skillorax.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para aceder.'
login_manager.login_message_category = 'info'

# ─── MODELS ───────────────────────────────────────────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30))
    whatsapp = db.Column(db.String(30))
    photo_url = db.Column(db.String(500), default='')
    role = db.Column(db.String(20), nullable=False)  # student, tutor, admin
    status = db.Column(db.String(20), default='active')
    is_admin_principal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Student fields
    university = db.Column(db.String(150))
    course = db.Column(db.String(150))
    academic_year = db.Column(db.String(30))
    province = db.Column(db.String(100))
    # Tutor fields
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Discipline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50), default='Geral')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TutorService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    disciplines = db.Column(db.Text, nullable=False)
    lesson_type = db.Column(db.String(20), nullable=False)
    province = db.Column(db.String(100))
    price = db.Column(db.String(100))
    schedule = db.Column(db.String(200))
    description = db.Column(db.Text)
    photo_url = db.Column(db.String(500), default='')
    status = db.Column(db.String(20), default='pendente')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tutor = db.relationship('User', backref='services')


class StudentRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    discipline = db.Column(db.String(150), nullable=False)
    lesson_type = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text)
    availability = db.Column(db.String(200))
    province = db.Column(db.String(100))
    university = db.Column(db.String(150))
    status = db.Column(db.String(20), default='pendente')
    tutor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('User', foreign_keys=[student_id], backref='requests')
    tutor = db.relationship('User', foreign_keys=[tutor_id])


class Opportunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    photo_url = db.Column(db.String(500), default='')
    category = db.Column(db.String(50))
    visibility = db.Column(db.String(50), default='all')
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin = db.relationship('User', backref='opportunities')


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='notifications')


class AdminLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin = db.relationship('User', backref='logs')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def notify(user_id, message):
    n = Notification(user_id=user_id, message=message)
    db.session.add(n)
    db.session.commit()


def log_action(admin_id, action):
    l = AdminLog(admin_id=admin_id, action=action)
    db.session.add(l)
    db.session.commit()


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    tutors = TutorService.query.filter_by(status='aprovado').order_by(TutorService.created_at.desc()).limit(6).all()
    opportunities = Opportunity.query.order_by(Opportunity.created_at.desc()).limit(5).all()
    requests_list = StudentRequest.query.filter_by(status='aprovado').order_by(StudentRequest.created_at.desc()).limit(8).all()
    return render_template('index.html', tutors=tutors, opportunities=opportunities, requests=requests_list)


@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        f = request.form
        if not f.get('photo_url'):
            flash('A foto de perfil é obrigatória.', 'danger')
            return redirect(url_for('register_student'))
        if User.query.filter_by(email=f['email']).first():
            flash('Email já registado.', 'danger')
            return redirect(url_for('register_student'))
        if User.query.filter_by(username=f['username']).first():
            flash('Username já em uso.', 'danger')
            return redirect(url_for('register_student'))
        u = User(
            username=f['username'], email=f['email'], full_name=f['full_name'],
            phone=f.get('phone', ''), whatsapp=f.get('whatsapp', ''),
            photo_url=f.get('photo_url', ''), role='student',
            university=f.get('university', ''), course=f.get('course', ''),
            academic_year=f.get('academic_year', ''), province=f.get('province', '')
        )
        u.set_password(f['password'])
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash('Conta criada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register_student.html')


@app.route('/register/tutor', methods=['GET', 'POST'])
def register_tutor():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        f = request.form
        if not f.get('photo_url'):
            flash('A foto de perfil é obrigatória.', 'danger')
            return redirect(url_for('register_tutor'))
        if User.query.filter_by(email=f['email']).first():
            flash('Email já registado.', 'danger')
            return redirect(url_for('register_tutor'))
        username = f['email'].split('@')[0]
        base = username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base}{counter}"
            counter += 1
        u = User(
            username=username, email=f['email'], full_name=f['full_name'],
            phone=f.get('phone', ''), whatsapp=f.get('whatsapp', ''),
            photo_url=f.get('photo_url', ''), role='tutor',
            province=f.get('province', ''), description=f.get('description', '')
        )
        u.set_password(f['password'])
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash('Conta criada! Agora crie o seu formulário de serviço.', 'success')
        return redirect(url_for('tutor_service_create'))
    return render_template('register_tutor.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if u and u.check_password(request.form['password']):
            if u.status in ('suspended', 'blocked'):
                flash(f'Conta {u.status}. Contacte o administrador.', 'danger')
                return redirect(url_for('login'))
            login_user(u)
            return redirect(url_for('dashboard'))
        flash('Email ou senha incorretos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_panel'))
    if current_user.role == 'student':
        my_requests = StudentRequest.query.filter_by(student_id=current_user.id).order_by(StudentRequest.created_at.desc()).all()
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(10).all()
        opportunities = Opportunity.query.order_by(Opportunity.created_at.desc()).limit(5).all()
        return render_template('dashboard_student.html', my_requests=my_requests, notifications=notifications, opportunities=opportunities)
    if current_user.role == 'tutor':
        services = TutorService.query.filter_by(tutor_id=current_user.id).order_by(TutorService.created_at.desc()).all()
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(10).all()
        opportunities = Opportunity.query.order_by(Opportunity.created_at.desc()).limit(5).all()
        return render_template('dashboard_tutor.html', services=services, notifications=notifications, opportunities=opportunities)
    return redirect(url_for('index'))


# ─── TUTOR SERVICES ───────────────────────────────────────────────────────────

@app.route('/tutor/service/create', methods=['GET', 'POST'])
@login_required
def tutor_service_create():
    if current_user.role != 'tutor':
        abort(403)
    disciplines = Discipline.query.order_by(Discipline.name).all()
    if request.method == 'POST':
        f = request.form
        if not f.get('photo_url') and not current_user.photo_url:
            flash('A foto de perfil é obrigatória.', 'danger')
            return redirect(url_for('tutor_service_create'))
        s = TutorService(
            tutor_id=current_user.id,
            disciplines=f['disciplines'],
            lesson_type=f['lesson_type'],
            province=f.get('province', ''),
            price=f.get('price', ''),
            schedule=f.get('schedule', ''),
            description=f.get('description', ''),
            photo_url=f.get('photo_url', '')
        )
        # update whatsapp if provided
        if f.get('whatsapp'):
            current_user.whatsapp = f.get('whatsapp')
            db.session.commit()
        db.session.add(s)
        db.session.commit()
        admins = User.query.filter_by(role='admin').all()
        for adm in admins:
            notify(adm.id, f'Novo serviço de {current_user.full_name} aguarda aprovação.')
        flash('Formulário enviado! Aguarda aprovação.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('tutor_service_form.html', service=None, disciplines=disciplines)


@app.route('/tutor/service/<int:sid>/edit', methods=['GET', 'POST'])
@login_required
def tutor_service_edit(sid):
    s = TutorService.query.get_or_404(sid)
    if s.tutor_id != current_user.id:
        abort(403)
    disciplines = Discipline.query.order_by(Discipline.name).all()
    if request.method == 'POST':
        f = request.form
        s.disciplines = f['disciplines']
        s.lesson_type = f['lesson_type']
        s.province = f.get('province', '')
        s.price = f.get('price', '')
        s.schedule = f.get('schedule', '')
        s.description = f.get('description', '')
        if f.get('photo_url'):
            s.photo_url = f.get('photo_url')
        if f.get('whatsapp'):
            current_user.whatsapp = f.get('whatsapp')
        s.status = 'pendente'
        db.session.commit()
        flash('Serviço actualizado. Aguarda nova aprovação.', 'info')
        return redirect(url_for('dashboard'))
    return render_template('tutor_service_form.html', service=s, disciplines=disciplines)


@app.route('/tutor/service/<int:sid>/delete', methods=['POST'])
@login_required
def tutor_service_delete(sid):
    s = TutorService.query.get_or_404(sid)
    if s.tutor_id != current_user.id:
        abort(403)
    db.session.delete(s)
    db.session.commit()
    flash('Serviço eliminado.', 'success')
    return redirect(url_for('dashboard'))


# ─── STUDENT REQUESTS ─────────────────────────────────────────────────────────

@app.route('/request/create', methods=['GET', 'POST'])
@login_required
def request_create():
    if current_user.role != 'student':
        abort(403)
    tutors = TutorService.query.filter_by(status='aprovado').all()
    disciplines = Discipline.query.order_by(Discipline.name).all()
    if request.method == 'POST':
        f = request.form
        tutor_id = f.get('tutor_id') or None
        if tutor_id == '':
            tutor_id = None
        r = StudentRequest(
            student_id=current_user.id,
            discipline=f['discipline'],
            lesson_type=f['lesson_type'],
            message=f.get('message', ''),
            availability=f.get('availability', ''),
            province=f.get('province', current_user.province or ''),
            university=f.get('university', current_user.university or ''),
            tutor_id=tutor_id
        )
        db.session.add(r)
        db.session.commit()
        admins = User.query.filter_by(role='admin').all()
        for adm in admins:
            notify(adm.id, f'Novo pedido de {current_user.full_name} ({f["discipline"]}) aguarda aprovação.')
        flash('Pedido enviado! Aguarda aprovação.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('request_create.html', tutors=tutors, disciplines=disciplines)


@app.route('/request/<int:rid>/edit', methods=['GET', 'POST'])
@login_required
def request_edit(rid):
    r = StudentRequest.query.get_or_404(rid)
    if r.student_id != current_user.id:
        abort(403)
    tutors = TutorService.query.filter_by(status='aprovado').all()
    disciplines = Discipline.query.order_by(Discipline.name).all()
    if request.method == 'POST':
        f = request.form
        r.discipline = f['discipline']
        r.lesson_type = f['lesson_type']
        r.message = f.get('message', '')
        r.availability = f.get('availability', '')
        r.province = f.get('province', '')
        r.university = f.get('university', '')
        r.tutor_id = f.get('tutor_id') or None
        r.status = 'pendente'
        db.session.commit()
        flash('Pedido actualizado.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('request_create.html', req=r, tutors=tutors, disciplines=disciplines)


@app.route('/request/<int:rid>/delete', methods=['POST'])
@login_required
def request_delete(rid):
    r = StudentRequest.query.get_or_404(rid)
    if r.student_id != current_user.id:
        abort(403)
    db.session.delete(r)
    db.session.commit()
    flash('Pedido eliminado.', 'success')
    return redirect(url_for('dashboard'))


# ─── EXPLORE ──────────────────────────────────────────────────────────────────

@app.route('/explore')
def explore():
    q = request.args.get('q', '')
    province = request.args.get('province', '')
    lesson_type = request.args.get('lesson_type', '')
    query = TutorService.query.filter_by(status='aprovado')
    if q:
        query = query.filter(TutorService.disciplines.ilike(f'%{q}%'))
    if province:
        query = query.filter(TutorService.province.ilike(f'%{province}%'))
    if lesson_type:
        query = query.filter(TutorService.lesson_type == lesson_type)
    services = query.order_by(TutorService.created_at.desc()).all()
    disciplines = Discipline.query.order_by(Discipline.name).all()
    return render_template('explore.html', services=services, q=q, province=province, lesson_type=lesson_type, disciplines=disciplines)


@app.route('/alunos')
def alunos():
    q = request.args.get('q', '')
    province = request.args.get('province', '')
    university = request.args.get('university', '')
    discipline = request.args.get('discipline', '')
    query = StudentRequest.query.filter_by(status='aprovado')
    if q:
        query = query.join(User, StudentRequest.student_id == User.id).filter(
            db.or_(User.full_name.ilike(f'%{q}%'), StudentRequest.discipline.ilike(f'%{q}%'))
        )
    if province:
        query = query.filter(StudentRequest.province.ilike(f'%{province}%'))
    if university:
        query = query.filter(StudentRequest.university.ilike(f'%{university}%'))
    if discipline:
        query = query.filter(StudentRequest.discipline.ilike(f'%{discipline}%'))
    reqs = query.order_by(StudentRequest.created_at.desc()).all()
    disciplines = Discipline.query.order_by(Discipline.name).all()
    return render_template('alunos.html', requests=reqs, q=q, province=province,
                           university=university, discipline=discipline, disciplines=disciplines)


@app.route('/oportunidades')
def oportunidades():
    category = request.args.get('category', '')
    query = Opportunity.query
    if category:
        query = query.filter_by(category=category)
    opps = query.order_by(Opportunity.created_at.desc()).all()
    return render_template('oportunidades.html', opportunities=opps, category=category)


@app.route('/feed')
def feed():
    requests_list = StudentRequest.query.filter_by(status='aprovado').order_by(StudentRequest.created_at.desc()).all()
    opportunities = Opportunity.query.order_by(Opportunity.created_at.desc()).all()
    return render_template('feed.html', requests=requests_list, opportunities=opportunities)


# ─── PROFILE ──────────────────────────────────────────────────────────────────

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    if request.method == 'POST':
        f = request.form
        if not f.get('photo_url') and not current_user.photo_url:
            flash('A foto de perfil é obrigatória.', 'danger')
            return redirect(url_for('profile_edit'))
        current_user.full_name = f.get('full_name', current_user.full_name)
        current_user.phone = f.get('phone', current_user.phone)
        current_user.whatsapp = f.get('whatsapp', current_user.whatsapp)
        if f.get('photo_url'):
            current_user.photo_url = f.get('photo_url')
        current_user.province = f.get('province', current_user.province)
        if current_user.role == 'student':
            current_user.university = f.get('university', '')
            current_user.course = f.get('course', '')
            current_user.academic_year = f.get('academic_year', '')
        if current_user.role == 'tutor':
            current_user.description = f.get('description', '')
        db.session.commit()
        flash('Perfil actualizado.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('profile_edit.html')


@app.route('/profile/delete', methods=['POST'])
@login_required
def profile_delete():
    u = current_user
    logout_user()
    db.session.delete(u)
    db.session.commit()
    flash('Conta eliminada.', 'info')
    return redirect(url_for('index'))


@app.route('/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return redirect(request.referrer or url_for('dashboard'))


# ─── ADMIN ────────────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    pending_services = TutorService.query.filter_by(status='pendente').count()
    pending_requests = StudentRequest.query.filter_by(status='pendente').count()
    total_students = User.query.filter_by(role='student').count()
    total_tutors = User.query.filter_by(role='tutor').count()
    recent_logs = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(10).all()
    return render_template('admin_panel.html',
        pending_services=pending_services, pending_requests=pending_requests,
        total_students=total_students, total_tutors=total_tutors, recent_logs=recent_logs)


@app.route('/admin/services')
@login_required
@admin_required
def admin_services():
    status_filter = request.args.get('status', 'pendente')
    services = TutorService.query.filter_by(status=status_filter).order_by(TutorService.created_at.desc()).all()
    pending_services = TutorService.query.filter_by(status='pendente').count()
    pending_requests = StudentRequest.query.filter_by(status='pendente').count()
    return render_template('admin_services.html', services=services, status_filter=status_filter,
                           pending_services=pending_services, pending_requests=pending_requests)


@app.route('/admin/service/<int:sid>/<action>', methods=['POST'])
@login_required
@admin_required
def admin_service_action(sid, action):
    s = TutorService.query.get_or_404(sid)
    if action in ('aprovado', 'rejeitado'):
        s.status = action
        db.session.commit()
        notify(s.tutor_id, f'O seu serviço foi {action}.')
        log_action(current_user.id, f'Serviço #{sid} de {s.tutor.full_name} foi {action}.')
        flash(f'Serviço {action}.', 'success')
    return redirect(url_for('admin_services'))


@app.route('/admin/requests')
@login_required
@admin_required
def admin_requests():
    status_filter = request.args.get('status', 'pendente')
    q = request.args.get('q', '')
    province = request.args.get('province', '')
    university = request.args.get('university', '')
    query = StudentRequest.query.filter_by(status=status_filter)
    if q:
        query = query.join(User, StudentRequest.student_id == User.id).filter(
            db.or_(User.full_name.ilike(f'%{q}%'), StudentRequest.discipline.ilike(f'%{q}%'))
        )
    if province:
        query = query.filter(StudentRequest.province.ilike(f'%{province}%'))
    if university:
        query = query.filter(StudentRequest.university.ilike(f'%{university}%'))
    reqs = query.order_by(StudentRequest.created_at.desc()).all()
    pending_services = TutorService.query.filter_by(status='pendente').count()
    pending_requests = StudentRequest.query.filter_by(status='pendente').count()
    return render_template('admin_requests.html', requests=reqs, status_filter=status_filter,
                           pending_services=pending_services, pending_requests=pending_requests,
                           q=q, province=province, university=university)


@app.route('/admin/request/<int:rid>/<action>', methods=['POST'])
@login_required
@admin_required
def admin_request_action(rid, action):
    r = StudentRequest.query.get_or_404(rid)
    if action in ('aprovado', 'rejeitado'):
        r.status = action
        db.session.commit()
        if action == 'aprovado':
            if r.tutor:
                notify(r.student_id, f'Pedido aprovado! Explicador: {r.tutor.full_name} | Tel: {r.tutor.phone} | WhatsApp: {r.tutor.whatsapp or r.tutor.phone}')
                notify(r.tutor_id, f'Novo aluno: {r.student.full_name} ({r.discipline}) | Tel: {r.student.phone} | WhatsApp: {r.student.whatsapp or r.student.phone}')
            else:
                notify(r.student_id, f'Pedido de {r.discipline} aprovado! Consulta os explicadores disponíveis.')
        else:
            notify(r.student_id, f'Pedido de {r.discipline} foi {action}.')
        log_action(current_user.id, f'Pedido #{rid} de {r.student.full_name} foi {action}.')
        flash(f'Pedido {action}.', 'success')
    return redirect(url_for('admin_requests'))


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    role_filter = request.args.get('role', '')
    q = User.query
    if role_filter:
        q = q.filter_by(role=role_filter)
    users = q.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users, role_filter=role_filter)


@app.route('/admin/user/<int:uid>/<action>', methods=['POST'])
@login_required
@admin_required
def admin_user_action(uid, action):
    u = User.query.get_or_404(uid)
    if action == 'delete':
        if u.is_admin_principal:
            flash('Não pode eliminar o admin principal.', 'danger')
            return redirect(url_for('admin_users'))
        db.session.delete(u)
        db.session.commit()
        log_action(current_user.id, f'Conta de {u.full_name} eliminada.')
        flash('Utilizador eliminado.', 'success')
    elif action in ('suspended', 'blocked', 'active'):
        u.status = action
        db.session.commit()
        log_action(current_user.id, f'Utilizador {u.full_name} marcado como {action}.')
        flash(f'Utilizador {action}.', 'success')
    elif action == 'make_admin':
        if not current_user.is_admin_principal:
            flash('Apenas o admin principal pode criar admins.', 'danger')
            return redirect(url_for('admin_users'))
        u.role = 'admin'
        db.session.commit()
        flash(f'{u.full_name} agora é admin.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/opportunities', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_opportunities():
    if request.method == 'POST':
        f = request.form
        o = Opportunity(
            title=f['title'], content=f['content'],
            category=f.get('category', 'aviso'),
            photo_url=f.get('photo_url', ''),
            visibility=f.get('visibility', 'all'),
            admin_id=current_user.id
        )
        db.session.add(o)
        db.session.commit()
        if o.visibility == 'all':
            users = User.query.filter(User.role.in_(['student', 'tutor'])).all()
        elif o.visibility == 'tutors':
            users = User.query.filter_by(role='tutor').all()
        else:
            users = User.query.filter_by(role='student').all()
        for usr in users:
            notify(usr.id, f'Nova oportunidade: {o.title}')
        log_action(current_user.id, f'Oportunidade "{o.title}" publicada.')
        flash('Oportunidade publicada!', 'success')
        return redirect(url_for('admin_opportunities'))
    opps = Opportunity.query.order_by(Opportunity.created_at.desc()).all()
    return render_template('admin_opportunities.html', opportunities=opps)


@app.route('/admin/opportunity/<int:oid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_opportunity_delete(oid):
    o = Opportunity.query.get_or_404(oid)
    db.session.delete(o)
    db.session.commit()
    log_action(current_user.id, f'Oportunidade "{o.title}" eliminada.')
    flash('Oportunidade eliminada.', 'success')
    return redirect(url_for('admin_opportunities'))


# ─── ADMIN DISCIPLINES ────────────────────────────────────────────────────────

@app.route('/admin/disciplines', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_disciplines():
    if request.method == 'POST':
        f = request.form
        name = f.get('name', '').strip()
        if name:
            if not Discipline.query.filter_by(name=name).first():
                d = Discipline(name=name, category=f.get('category', 'Geral'))
                db.session.add(d)
                db.session.commit()
                log_action(current_user.id, f'Disciplina "{name}" adicionada.')
                flash(f'Disciplina "{name}" adicionada!', 'success')
            else:
                flash('Disciplina já existe.', 'warning')
    disciplines = Discipline.query.order_by(Discipline.category, Discipline.name).all()
    return render_template('admin_disciplines.html', disciplines=disciplines)


@app.route('/admin/discipline/<int:did>/delete', methods=['POST'])
@login_required
@admin_required
def admin_discipline_delete(did):
    d = Discipline.query.get_or_404(did)
    db.session.delete(d)
    db.session.commit()
    flash(f'Disciplina "{d.name}" eliminada.', 'success')
    return redirect(url_for('admin_disciplines'))


@app.route('/admin/logs')
@login_required
@admin_required
def admin_logs():
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).all()
    return render_template('admin_logs.html', logs=logs)


@app.route('/admin/create-admin', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_admin():
    if not current_user.is_admin_principal:
        flash('Apenas o admin principal pode criar novos admins.', 'danger')
        return redirect(url_for('admin_users'))
    if request.method == 'POST':
        f = request.form
        if User.query.filter_by(email=f['email']).first():
            flash('Email já registado.', 'danger')
            return redirect(url_for('admin_create_admin'))
        username = f['email'].split('@')[0]
        base = username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base}{counter}"
            counter += 1
        u = User(username=username, email=f['email'], full_name=f['full_name'], role='admin', status='active')
        u.set_password(f['password'])
        db.session.add(u)
        db.session.commit()
        log_action(current_user.id, f'Novo admin criado: {u.full_name}')
        flash(f'Admin {u.full_name} criado!', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin_create.html')


# ─── INIT DB ──────────────────────────────────────────────────────────────────

def create_admin():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='admin').first():
            admin = User(
                username='admin', email='admin@skillorax.com',
                full_name='Administrador SkilloraX', role='admin',
                is_admin_principal=True, status='active',
                photo_url=''
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin criado: admin@skillorax.com / admin123")
        # Seed default disciplines
        default_disciplines = [
            ('Matemática','Exactas'),('Física','Exactas'),('Química','Exactas'),
            ('Biologia','Ciências'),('Bioquímica','Ciências'),('Estatística','Exactas'),
            ('Cálculo I','Exactas'),('Cálculo II','Exactas'),('Álgebra Linear','Exactas'),
            ('Programação','Tecnologia'),('Python','Tecnologia'),('Java','Tecnologia'),
            ('Web Development','Tecnologia'),('Bases de Dados','Tecnologia'),
            ('Inglês','Línguas'),('Português','Línguas'),('Francês','Línguas'),
            ('Economia','Sociais'),('Gestão','Sociais'),('Contabilidade','Sociais'),
            ('Direito','Sociais'),('Relações Internacionais','Sociais'),
            ('Geografia','Sociais'),('História','Sociais'),
        ]
        for name, cat in default_disciplines:
            if not Discipline.query.filter_by(name=name).first():
                db.session.add(Discipline(name=name, category=cat))
        db.session.commit()


if __name__ == '__main__':
    create_admin()
    app.run(debug=True)

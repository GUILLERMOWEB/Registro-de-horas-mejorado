from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_sesiones'

# Configuración para PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ─── Modelos ─────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)

    registros = db.relationship('Registro', backref='user', lazy=True)

class Registro(db.Model):
    __tablename__ = 'registros'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    fecha = db.Column(db.String(50))
    entrada = db.Column(db.String(50))
    salida = db.Column(db.String(50))
    almuerzo = db.Column(db.Float)
    horas = db.Column(db.Float)
    tarea = db.Column(db.Text)
    cliente = db.Column(db.Text)
    comentarios = db.Column(db.Text)

# ─── Inicialización de la base de datos ─────────
with app.app_context():
    db.create_all()
    if not User.query.filter(db.func.lower(User.username) == 'guillermo gutierrez').first():
        superadmin = User(username='guillermo gutierrez', password='0000', role='superadmin')
        db.session.add(superadmin)
        db.session.commit()

# ─── Rutas ──────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
def inicio():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']

        user = User.query.filter(
            db.func.lower(User.username) == username,
            User.password == password
        ).first()

        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        fecha = request.form['fecha']
        entrada = request.form['entrada']
        salida = request.form['salida']
        almuerzo = float(request.form['almuerzo'])
        tarea = request.form['tarea']
        cliente = request.form['cliente']
        comentarios = request.form['comentarios']

        formato_hora = "%H:%M"
        try:
            t_entrada = datetime.strptime(entrada, formato_hora)
            t_salida = datetime.strptime(salida, formato_hora)
            horas_trabajadas = (t_salida - t_entrada - timedelta(hours=almuerzo)).total_seconds() / 3600
        except ValueError:
            flash("Error en el formato de hora. Use HH:MM")
            return redirect(url_for('dashboard'))

        nuevo_registro = Registro(
            user_id=session['user_id'],
            fecha=fecha,
            entrada=entrada,
            salida=salida,
            almuerzo=almuerzo,
            horas=round(horas_trabajadas, 2),
            tarea=tarea,
            cliente=cliente,
            comentarios=comentarios
        )
        db.session.add(nuevo_registro)
        db.session.commit()
        flash('Registro guardado exitosamente')

    filtros = request.args
    registros_query = Registro.query.filter_by(user_id=session['user_id'])

    if 'fecha' in filtros:
        registros_query = registros_query.filter_by(fecha=filtros['fecha'])

    registros = registros_query.order_by(Registro.fecha.desc()).all()
    total_horas = sum([r.horas for r in registros if r.horas])

    return render_template('dashboard.html',
                           username=session['username'],
                           role=session['role'],
                           registros=registros,
                           total_horas=round(total_horas, 2))



@app.route('/exportar_excel')
def exportar_excel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    with sqlite3.connect(DATABASE) as conn:
        df = pd.read_sql_query("SELECT fecha, entrada, salida, almuerzo, horas, tarea FROM registros WHERE user_id = ?", conn, params=(user_id,))

    archivo = f"registros_{session['username']}.xlsx"
    df.to_excel(archivo, index=False)
    return send_file(archivo, as_attachment=True)

@app.route('/editar_registro/<int:id>', methods=['GET', 'POST'])
def editar_registro(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            fecha = request.form['fecha']
            horas = request.form['horas']
            tarea = request.form['tarea']
            cursor.execute("UPDATE registros SET fecha = ?, horas = ?, tarea = ? WHERE id = ?",
                           (fecha, horas, tarea, id))
            conn.commit()
            return redirect(url_for('admin') if session['role'] == 'superadmin' else url_for('dashboard'))

        cursor.execute("SELECT fecha, horas, tarea FROM registros WHERE id = ?", (id,))
        registro = cursor.fetchone()

    return render_template('editar_registro.html', registro=registro, id=id)

@app.route('/borrar_registro/<int:id>', methods=['POST'])
def borrar_registro(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM registros WHERE id = ?", (id,))
        conn.commit()
    return redirect(url_for('admin') if session['role'] == 'superadmin' else url_for('dashboard'))

@app.route('/crear_admin', methods=['GET', 'POST'])
def crear_admin():
    if 'user_id' not in session or session['role'] != 'superadmin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password')
        confirmar = request.form.get('confirmar_password')

        if not username or not password or not confirmar:
            flash('Todos los campos son obligatorios.')
            return render_template('crear_admin.html')

        if password != confirmar:
            flash('Las contraseñas no coinciden.')
            return render_template('crear_admin.html')

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                               (username, password, 'admin'))
                conn.commit()
                flash('Administrador creado correctamente')
            except sqlite3.IntegrityError:
                flash('Ese nombre de usuario ya existe.')

    return render_template('crear_admin.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or session['role'] not in ['admin', 'superadmin']:
        return redirect(url_for('login'))

    filtro_usuario = request.form.get('filtro_usuario') if request.method == 'POST' else None

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id, username FROM users")
        usuarios = cursor.fetchall()

        if filtro_usuario:
            cursor.execute('''
                SELECT registros.id, users.username, registros.fecha, registros.horas, registros.tarea
                FROM registros
                JOIN users ON registros.user_id = users.id
                WHERE users.id = ?
                ORDER BY registros.fecha DESC
            ''', (filtro_usuario,))
        else:
            cursor.execute('''
                SELECT registros.id, users.username, registros.fecha, registros.horas, registros.tarea
                FROM registros
                JOIN users ON registros.user_id = users.id
                ORDER BY registros.fecha DESC
            ''')

        registros = cursor.fetchall()

    return render_template('admin.html', registros=registros, usuarios=usuarios, 
                       filtro_usuario=filtro_usuario,
                       username=session['username'], role=session['role'])


@app.route('/cambiar_password', methods=['GET', 'POST'])
def cambiar_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nueva = request.form['nueva']
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (nueva, session['user_id']))
            conn.commit()
        flash('Contraseña actualizada')

    return render_template('cambiar_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/crear_usuario', methods=['GET', 'POST'])
def crear_usuario():
    if 'user_id' not in session or session['role'] not in ['admin', 'superadmin']:
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        confirmar = request.form['confirmar_password']

    if password != confirmar:
        flash('Las contraseñas no coinciden.')
        return render_template('crear_usuario.html')

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (username, password, 'usuario'))
            conn.commit()
            flash('Usuario creado exitosamente.')
        except sqlite3.IntegrityError:
            flash('Ese nombre de usuario ya existe.')


    return render_template('crear_usuario.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        confirmar = request.form['confirmar_password']

        if password != confirmar:
            flash('Las contraseñas no coinciden.')
            return render_template('registro.html')

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                               (username, password, 'usuario'))
                conn.commit()
                flash('Usuario creado exitosamente. Ahora podés iniciar sesión.')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Ese nombre de usuario ya existe.')

    return render_template('registro.html')

@app.route('/usuarios')
def listar_usuarios():
    if 'user_id' not in session or session['role'] not in ['admin', 'superadmin']:

        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users")
        usuarios = cursor.fetchall()

    return render_template('usuarios.html', usuarios=usuarios)


if __name__ == '__main__':
    import os
    if not os.path.exists(DATABASE):
        init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)


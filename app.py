from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_sesiones'

DATABASE = 'database.db'

# Crear base de datos si no existe
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL UNIQUE,
                            password TEXT NOT NULL,
                            role TEXT NOT NULL)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    fecha TEXT,
                    entrada TEXT,
                    salida TEXT,
                    almuerzo REAL,
                    horas REAL,
                    tarea TEXT,
                    cliente TEXT,
                    comentarios TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id))''')

        # Crear superusuario si no existe
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = ?", ('guillermo gutierrez',))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           ('guillermo gutierrez', '0000', 'superadmin'))
            conn.commit()


@app.route('/', methods=['GET', 'POST'])
def inicio():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, role FROM users WHERE LOWER(username) = ? AND password = ?", (username, password))
            user = cursor.fetchone()

            if user:
                session['user_id'] = user[0]
                session['username'] = username
                session['role'] = user[1]
                return redirect(url_for('dashboard'))
            else:
                flash('Usuario o contraseña incorrectos')

    return render_template('inicio.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password'] 

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, role FROM users WHERE LOWER(username) = ? AND password = ?", (username, password))
            user = cursor.fetchone()

            if user:
                session['user_id'] = user[0]
                session['username'] = username
                session['role'] = user[1]
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

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO registros (user_id, fecha, entrada, salida, almuerzo, horas, tarea, cliente, comentarios) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (session['user_id'], fecha, entrada, salida, almuerzo, round(horas_trabajadas, 2), tarea, cliente, comentarios))

            conn.commit()
        flash('Registro guardado exitosamente')

    filtros = request.args
    query = "SELECT fecha, entrada, salida, almuerzo, horas, tarea, cliente, comentarios, id FROM registros WHERE user_id = ?"
    params = [session['user_id']]

    if 'fecha' in filtros:
        query += " AND fecha = ?"
        params.append(filtros['fecha'])

    query += " ORDER BY fecha DESC"

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        registros = cursor.fetchall()
        total_horas = sum([r[4] for r in registros])

    return render_template('dashboard.html', username=session['username'], role=session['role'], registros=registros, total_horas=round(total_horas, 2))


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


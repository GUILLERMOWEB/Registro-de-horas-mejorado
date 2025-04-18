from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import pandas as pd
from io import BytesIO
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook

def convertir_hora_a_decimal(hora_str):
    try:
        return float(int(hora_str.strip()))
    except ValueError:
        return 0.0



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
    tarea = db.Column(db.Text)
    almuerzo = db.Column(db.Float)
    comentarios = db.Column(db.Text)
    cliente = db.Column(db.Text)
    

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
        almuerzo = convertir_hora_a_decimal(request.form['almuerzo'])
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

    role = session.get('role')

    if role in ['admin', 'superadmin']:
        registros = Registro.query.all()
    else:
        registros = Registro.query.filter_by(user_id=session['user_id']).all()

    df = pd.DataFrame([{
        'usuario': r.user.username,
        'fecha': r.fecha,
        'entrada': r.entrada,
        'salida': r.salida,
        'almuerzo': r.almuerzo,
        'horas': r.horas,
        'tarea': r.tarea
    } for r in registros])

    archivo = BytesIO()
    with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Registros')
        ws = writer.sheets['Registros']

        # ✅ Filtros automáticos
        ws.auto_filter.ref = ws.dimensions

        # ✅ Ajuste automático del ancho de columnas
        for col_num, column_cells in enumerate(ws.columns, 1):
            max_length = 0
            for cell in column_cells:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            adjusted_width = (max_length + 2)
            column_letter = get_column_letter(col_num)
            ws.column_dimensions[column_letter].width = adjusted_width

    archivo.seek(0)
    return send_file(archivo, as_attachment=True, download_name=f"registros_{session['username']}.xlsx")


@app.route('/editar_registro/<int:id>', methods=['GET', 'POST'])
def editar_registro(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    registro = Registro.query.get_or_404(id)

    if request.method == 'POST':
        registro.fecha = request.form['fecha']       
        registro.entrada = request.form['entrada']
        registro.salida = request.form['salida']
        registro.tarea = request.form['tarea']
        registro.almuerzo = request.form['almuerzo']
        registro.comentarios = request.form['comentarios']
        registro.cliente = request.form['cliente']
        
        db.session.commit()
        return redirect(url_for('admin') if session['role'] == 'superadmin' else url_for('dashboard'))

    return render_template('editar_registro.html', registro=registro, id=id)

@app.route('/borrar_registro/<int:id>', methods=['POST'])
def borrar_registro(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    registro = Registro.query.get_or_404(id)
    db.session.delete(registro)
    db.session.commit()
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

        if User.query.filter_by(username=username).first():
            flash('Ese nombre de usuario ya existe.')
        else:
            nuevo_admin = User(username=username, password=password, role='admin')
            db.session.add(nuevo_admin)
            db.session.commit()
            flash('Administrador creado correctamente')

    return render_template('crear_admin.html')


@app.route('/administrator', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or session['role'] not in ['admin', 'superadmin']:
        return redirect(url_for('login'))

    filtro_usuario = request.form.get('filtro_usuario') if request.method == 'POST' else None

    usuarios = User.query.with_entities(User.id, User.username).all()

    if filtro_usuario:
        registros = db.session.query(Registro, User).join(User).filter(User.id == filtro_usuario).order_by(Registro.fecha.desc()).all()
    else:
        registros = db.session.query(Registro, User).join(User).order_by(Registro.fecha.desc()).all()

    return render_template('admin.html', registros=registros, usuarios=usuarios,
                           filtro_usuario=filtro_usuario,
                           username=session['username'], role=session['role'])


@app.route('/cambiar_password', methods=['GET', 'POST'])
def cambiar_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nueva = request.form['nueva']
        confirmar = request.form['confirmar']  # Se agrega para la comparación de contraseñas

        if nueva != confirmar:
            flash('Las contraseñas no coinciden.')
            return render_template('cambiar_password.html')

        # Si las contraseñas coinciden, actualizarla en la base de datos
        user = User.query.get(session['user_id'])
        user.password = nueva
        db.session.commit()
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

        if User.query.filter_by(username=username).first():
            flash('Ese nombre de usuario ya existe.')
        else:
            nuevo_usuario = User(username=username, password=password, role='usuario')
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('Usuario creado exitosamente.')

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

        if User.query.filter_by(username=username).first():
            flash('Ese nombre de usuario ya existe.')
        else:
            nuevo_usuario = User(username=username, password=password, role='usuario')
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('Usuario creado exitosamente. Ahora podés iniciar sesión.')
            return redirect(url_for('login'))

    return render_template('registro.html')

@app.route('/usuarios')
def listar_usuarios():
    if 'user_id' not in session or session['role'] not in ['admin', 'superadmin']:
        return redirect(url_for('login'))

    usuarios = User.query.with_entities(User.id, User.username, User.role).all()
    return render_template('usuarios.html', usuarios=usuarios)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

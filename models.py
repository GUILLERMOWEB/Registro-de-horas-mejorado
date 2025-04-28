from flask_sqlalchemy import SQLAlchemy

# Creamos una instancia de SQLAlchemy aquí, pero NO la inicializamos
# La inicialización se hará en app.py
db = SQLAlchemy()

# -----------------------------
# MODELO DE REGISTRO DE HORAS
# -----------------------------
class RegistroHoras(db.Model):
    __tablename__ = 'registros'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora_entrada = db.Column(db.Time, nullable=False)
    hora_salida = db.Column(db.Time, nullable=False)
    horas_almuerzo = db.Column(db.Float, nullable=False, default=0.0)
    horas_trabajadas = db.Column(db.Float, nullable=False, default=0.0)
    horas_viaje_ida = db.Column(db.Float, nullable=True, default=0.0)
    horas_viaje_vuelta = db.Column(db.Float, nullable=True, default=0.0)
    km_ida = db.Column(db.Float, nullable=True, default=0.0)
    km_vuelta = db.Column(db.Float, nullable=True, default=0.0)
    cliente = db.Column(db.String(255), nullable=True)
    comentarios = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<RegistroHoras {self.fecha} - Usuario {self.user_id}>'

# -----------------------------
# MODELO DE CLIENTES
# -----------------------------
class ClienteModel(db.Model):
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    direccion = db.Column(db.String(255), nullable=False)
    telefono = db.Column(db.String(20), nullable=True)

    def __repr__(self):
        return f'<Cliente {self.nombre}>'

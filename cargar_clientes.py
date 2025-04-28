from flask_sqlalchemy import SQLAlchemy

# Esto lo usará el app.py
db = SQLAlchemy()

class ClienteModel(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    direccion = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f'<Cliente {self.nombre}>'

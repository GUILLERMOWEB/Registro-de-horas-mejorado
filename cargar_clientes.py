from app import db, ClienteModel

# Usar el contexto de la aplicación para ejecutar el código de la base de datos
with app.app_context():
    clientes = [
        "Acme Corp", 
        "Globex", 
        "Initech", 
        "Umbrella", 
        "Stark Industries", 
        "Wayne Enterprises"
    ]

    # Agregar clientes solo si no existen en la base de datos
    for nombre in clientes:
        if not Cliente.query.filter_by(nombre=nombre).first():
            db.session.add(Cliente(nombre=nombre))

    db.session.commit()  # Guardar los cambios en la base de datos
    print("Clientes cargados con éxito.")

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_cambiar_en_produccion_2024')
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def conectar_db():
    return pymysql.connect(
        host='127.0.0.1',
        user='root',
        password='',
        database='bd_tesis_juarez',
        cursorclass=pymysql.cursors.DictCursor
    )

def extension_valida(nombre_archivo):
    return (
        '.' in nombre_archivo and
        nombre_archivo.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS
    )

def guardar_imagen(archivo, prefijo, fallback):
    if archivo and archivo.filename and extension_valida(archivo.filename):
        nombre = f"{prefijo}_{archivo.filename}"
        archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre))
        return nombre
    return fallback

def login_requerido(f):
    from functools import wraps
    @wraps(f)
    def decorado(*args, **kwargs):
        if 'vendedor_id' not in session:
            flash('Debes iniciar sesión para acceder a esa página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorado

@app.route('/')
def bienvenida():
    if 'vendedor_id' in session:
        return redirect(url_for('inicio'))
    return render_template('bienvenida.html')

@app.route('/inicio')
def inicio():
    conexion = conectar_db()
    with conexion.cursor() as cursor:
        cursor.execute("SELECT * FROM categorias ORDER BY nombre_categoria ASC")
        categorias = cursor.fetchall()
        cursor.execute("SELECT * FROM negocios ORDER BY nombre_negocio ASC")
        resultados = cursor.fetchall()
    conexion.close()
    return render_template(
        'index.html',
        categorias=categorias,
        resultados=resultados,
        vendedor_logueado='vendedor_id' in session
    )

@app.route('/buscar', methods=['POST'])
def buscar():
    colonia_texto = request.form.get('colonia', '').strip().upper()
    categoria_id  = request.form.get('categoria', '0')

    conexion = conectar_db()
    with conexion.cursor() as cursor:
        query      = "SELECT * FROM negocios WHERE 1=1"
        parametros = []

        if colonia_texto:
            query += " AND nombre_colonia LIKE %s"
            parametros.append(f"%{colonia_texto}%")

        if categoria_id and categoria_id != '0':
            query += " AND id_categoria = %s"
            parametros.append(categoria_id)

        query += " ORDER BY nombre_negocio ASC"
        cursor.execute(query, parametros)
        resultados = cursor.fetchall()

        cursor.execute("SELECT * FROM categorias ORDER BY nombre_categoria ASC")
        categorias = cursor.fetchall()

    conexion.close()
    return render_template(
        'index.html',
        resultados=resultados,
        categorias=categorias,
        busqueda=True,
        vendedor_logueado='vendedor_id' in session
    )

@app.route('/negocio/<int:id>')
def ver_negocio(id):
    conexion = conectar_db()
    with conexion.cursor() as cursor:
        cursor.execute("SELECT * FROM negocios WHERE id_negocio = %s", (id,))
        negocio = cursor.fetchone()
        if not negocio:
            conexion.close()
            flash('Este negocio no existe o fue eliminado.', 'warning')
            return redirect(url_for('inicio'))
        cursor.execute(
            "SELECT * FROM productos WHERE id_negocio = %s ORDER BY nombre_producto ASC",
            (id,)
        )
        productos = cursor.fetchall()
    conexion.close()
    return render_template('catalogo.html', negocio=negocio, productos=productos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'vendedor_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        correo     = request.form.get('correo', '').strip().lower()
        contrasena = request.form.get('contrasena', '')
        accion     = request.form.get('accion')

        if not correo or not contrasena:
            flash('Completa todos los campos.', 'danger')
            return render_template('login.html')

        if len(contrasena) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return render_template('login.html')

        conexion = conectar_db()
        with conexion.cursor() as cursor:
            if accion == 'registro':
                cursor.execute(
                    "SELECT id_vendedor FROM usuarios_vendedores WHERE correo = %s", (correo,))
                if cursor.fetchone():
                    flash('Ese correo ya está registrado. Intenta iniciar sesión.', 'warning')
                else:
                    hash_contra = generate_password_hash(contrasena)
                    cursor.execute(
                        "INSERT INTO usuarios_vendedores (correo, contrasena) VALUES (%s, %s)",
                        (correo, hash_contra))
                    conexion.commit()
                    flash('¡Cuenta creada! Ahora inicia sesión.', 'success')

            elif accion == 'login':
                cursor.execute(
                    "SELECT * FROM usuarios_vendedores WHERE correo = %s", (correo,))
                usuario = cursor.fetchone()
                if usuario and check_password_hash(usuario['contrasena'], contrasena):
                    session.clear()
                    session['vendedor_id'] = usuario['id_vendedor']
                    session.permanent = True
                    flash('¡Bienvenido de vuelta!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Correo o contraseña incorrectos.', 'danger')
        conexion.close()

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('bienvenida'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_requerido
def dashboard():
    vendedor_id = session['vendedor_id']
    conexion    = conectar_db()

    if request.method == 'POST':
        nombre      = request.form.get('nombre_negocio', '').strip()
        telefono    = request.form.get('telefono', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        colonia     = request.form.get('colonia', '').strip().upper()
        categoria   = request.form.get('categoria')
        tema        = request.form.get('tema_color', 'primary')
        horario     = request.form.get('horario', '').strip()
        direccion   = request.form.get('direccion', '').strip()
        logo        = request.files.get('logo')

        if not nombre or not telefono or not colonia or not categoria:
            flash('Nombre, teléfono, colonia y categoría son obligatorios.', 'danger')
        else:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM negocios WHERE id_vendedor = %s", (vendedor_id,))
                negocio_actual = cursor.fetchone()

                logo_actual = negocio_actual['ruta_logo'] if negocio_actual else 'default_logo.png'
                nombre_logo = guardar_imagen(logo, f"logo_{vendedor_id}", logo_actual)

                if negocio_actual:
                    cursor.execute("""
                        UPDATE negocios
                        SET nombre_negocio=%s, telefono=%s, descripcion=%s,
                            nombre_colonia=%s, id_categoria=%s, tema_color=%s,
                            ruta_logo=%s, horario=%s, direccion=%s
                        WHERE id_vendedor=%s
                    """, (nombre, telefono, descripcion, colonia,
                          categoria, tema, nombre_logo, horario, direccion, vendedor_id))
                else:
                    cursor.execute("""
                        INSERT INTO negocios
                            (id_vendedor, nombre_colonia, id_categoria, nombre_negocio,
                             telefono, descripcion, tema_color, ruta_logo, horario, direccion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (vendedor_id, colonia, categoria, nombre,
                          telefono, descripcion, tema, nombre_logo, horario, direccion))

                conexion.commit()
                flash('¡Datos del negocio guardados correctamente!', 'success')

    with conexion.cursor() as cursor:
        cursor.execute("SELECT * FROM negocios WHERE id_vendedor = %s", (vendedor_id,))
        mi_negocio = cursor.fetchone()
        cursor.execute("SELECT * FROM categorias ORDER BY nombre_categoria ASC")
        categorias = cursor.fetchall()
        mis_productos = []
        if mi_negocio:
            cursor.execute(
                "SELECT * FROM productos WHERE id_negocio = %s ORDER BY nombre_producto ASC",
                (mi_negocio['id_negocio'],))
            mis_productos = cursor.fetchall()

    conexion.close()
    return render_template(
        'dashboard.html',
        negocio=mi_negocio,
        categorias=categorias,
        productos=mis_productos
    )

@app.route('/agregar_producto', methods=['POST'])
@login_requerido
def agregar_producto():
    nombre_prod = request.form.get('nombre_producto', '').strip()
    precio_raw  = request.form.get('precio', '').strip()
    foto        = request.files.get('foto')

    if not nombre_prod or not precio_raw:
        flash('El nombre y el precio del producto son obligatorios.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        precio = float(precio_raw)
        if precio < 0:
            raise ValueError
    except ValueError:
        flash('El precio debe ser un número válido mayor a 0.', 'danger')
        return redirect(url_for('dashboard'))

    conexion = conectar_db()
    with conexion.cursor() as cursor:
        cursor.execute(
            "SELECT id_negocio FROM negocios WHERE id_vendedor = %s", (session['vendedor_id'],))
        negocio = cursor.fetchone()

        if not negocio:
            flash('Primero debes configurar tu negocio.', 'warning')
            conexion.close()
            return redirect(url_for('dashboard'))

        nombre_foto = guardar_imagen(foto, f"prod_{negocio['id_negocio']}", 'default_producto.png')

        cursor.execute(
            "INSERT INTO productos (id_negocio, nombre_producto, precio, ruta_imagen) VALUES (%s, %s, %s, %s)",
            (negocio['id_negocio'], nombre_prod, precio, nombre_foto))
        conexion.commit()
        flash(f'Producto "{nombre_prod}" agregado correctamente.', 'success')

    conexion.close()
    return redirect(url_for('dashboard'))

@app.route('/eliminar_producto/<int:id>')
@login_requerido
def eliminar_producto(id):
    conexion = conectar_db()
    with conexion.cursor() as cursor:
        cursor.execute("""
            SELECT p.id_producto, p.nombre_producto
            FROM productos p
            JOIN negocios n ON p.id_negocio = n.id_negocio
            WHERE p.id_producto = %s AND n.id_vendedor = %s
        """, (id, session['vendedor_id']))
        producto = cursor.fetchone()

        if producto:
            cursor.execute("DELETE FROM productos WHERE id_producto = %s", (id,))
            conexion.commit()
            flash(f'Producto "{producto["nombre_producto"]}" eliminado.', 'success')
        else:
            flash('No tienes permiso para eliminar ese producto.', 'danger')

    conexion.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
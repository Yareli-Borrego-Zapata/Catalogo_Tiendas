from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_la_tesis_juarez'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def conectar_db():
    return pymysql.connect(
        host='127.0.0.1',
        user='root',
        password='',
        database='bd_tesis_juarez',
        cursorclass=pymysql.cursors.DictCursor
    )

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
        # Modificado para traer todos los negocios y mostrarlos inicialmente
        cursor.execute("SELECT * FROM negocios")
        resultados = cursor.fetchall()
    conexion.close()
    
    vendedor_logueado = 'vendedor_id' in session
    return render_template('index.html', categorias=categorias, vendedor_logueado=vendedor_logueado, resultados=resultados)

@app.route('/buscar', methods=['POST'])
def buscar():
    colonia_texto = request.form.get('colonia', '').strip().upper()
    categoria_id = request.form.get('categoria')
    
    conexion = conectar_db()
    with conexion.cursor() as cursor:
        query = "SELECT * FROM negocios WHERE 1=1"
        parametros = []
        
        if colonia_texto:
            query += " AND nombre_colonia LIKE %s"
            parametros.append(f"%{colonia_texto}%")
        if categoria_id and categoria_id != '0':
            query += " AND id_categoria = %s"
            parametros.append(categoria_id)
            
        cursor.execute(query, parametros)
        resultados = cursor.fetchall()
        
        cursor.execute("SELECT * FROM categorias ORDER BY nombre_categoria ASC")
        categorias = cursor.fetchall()
        
    conexion.close()
    
    vendedor_logueado = 'vendedor_id' in session
    return render_template('index.html', resultados=resultados, categorias=categorias, busqueda=True, vendedor_logueado=vendedor_logueado)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'vendedor_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        accion = request.form['accion']
        
        conexion = conectar_db()
        with conexion.cursor() as cursor:
            if accion == 'registro':
                cursor.execute("SELECT id_vendedor FROM usuarios_vendedores WHERE correo = %s", (correo,))
                if cursor.fetchone():
                    flash('El correo ya está registrado.', 'danger')
                else:
                    hash_contra = generate_password_hash(contrasena)
                    cursor.execute("INSERT INTO usuarios_vendedores (correo, contrasena) VALUES (%s, %s)", (correo, hash_contra))
                    conexion.commit()
                    flash('Registro exitoso. Ahora inicia sesión.', 'success')
            
            elif accion == 'login':
                cursor.execute("SELECT * FROM usuarios_vendedores WHERE correo = %s", (correo,))
                usuario = cursor.fetchone()
                if usuario and check_password_hash(usuario['contrasena'], contrasena):
                    session['vendedor_id'] = usuario['id_vendedor']
                    return redirect(url_for('inicio'))
                else:
                    flash('Correo o contraseña incorrectos.', 'danger')
        conexion.close()
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'vendedor_id' not in session:
        return redirect(url_for('login'))
        
    conexion = conectar_db()
    vendedor_id = session['vendedor_id']
    
    if request.method == 'POST':
        nombre = request.form['nombre_negocio']
        telefono = request.form['telefono']
        descripcion = request.form['descripcion']
        colonia = request.form['colonia'].strip().upper()
        categoria = request.form['categoria']
        tema = request.form['tema_color']
        logo = request.files['logo'] # Recibimos el logo
        
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM negocios WHERE id_vendedor = %s", (vendedor_id,))
            negocio = cursor.fetchone()
            
            # Lógica para guardar el logo
            nombre_logo = negocio['ruta_logo'] if negocio else 'default_logo.png'
            if logo:
                # Usamos el ID del vendedor para nombrar el logo de forma única
                nombre_logo = f"logo_{vendedor_id}_{logo.filename}"
                logo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_logo))

            if negocio:
                cursor.execute("""
                    UPDATE negocios SET nombre_negocio=%s, telefono=%s, descripcion=%s, nombre_colonia=%s, id_categoria=%s, tema_color=%s, ruta_logo=%s
                    WHERE id_vendedor=%s""", (nombre, telefono, descripcion, colonia, categoria, tema, nombre_logo, vendedor_id))
            else:
                cursor.execute("""
                    INSERT INTO negocios (id_vendedor, nombre_colonia, id_categoria, nombre_negocio, telefono, descripcion, tema_color, ruta_logo) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", (vendedor_id, colonia, categoria, nombre, telefono, descripcion, tema, nombre_logo))
            conexion.commit()
            flash('Datos del negocio guardados.', 'success')
            
    with conexion.cursor() as cursor:
        cursor.execute("SELECT * FROM negocios WHERE id_vendedor = %s", (vendedor_id,))
        mi_negocio = cursor.fetchone()
        
        cursor.execute("SELECT * FROM categorias ORDER BY nombre_categoria ASC")
        categorias = cursor.fetchall()
        
        mis_productos = []
        if mi_negocio:
            cursor.execute("SELECT * FROM productos WHERE id_negocio = %s", (mi_negocio['id_negocio'],))
            mis_productos = cursor.fetchall()
            
    conexion.close()
    return render_template('dashboard.html', negocio=mi_negocio, categorias=categorias, productos=mis_productos)

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    if 'vendedor_id' not in session:
        return redirect(url_for('login'))
        
    nombre_prod = request.form['nombre_producto']
    precio = request.form['precio']
    foto = request.files['foto']
    
    conexion = conectar_db()
    with conexion.cursor() as cursor:
        cursor.execute("SELECT id_negocio FROM negocios WHERE id_vendedor = %s", (session['vendedor_id'],))
        negocio = cursor.fetchone()
        
        if negocio:
            nombre_foto = 'default_producto.png'
            if foto:
                nombre_foto = f"prod_{negocio['id_negocio']}_{foto.filename}"
                foto.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_foto))
                
            cursor.execute("INSERT INTO productos (id_negocio, nombre_producto, precio, ruta_imagen) VALUES (%s, %s, %s, %s)",
                           (negocio['id_negocio'], nombre_prod, precio, nombre_foto))
            conexion.commit()
    conexion.close()
    return redirect(url_for('dashboard'))

@app.route('/eliminar_producto/<int:id>')
def eliminar_producto(id):
    conexion = conectar_db()
    with conexion.cursor() as cursor:
        cursor.execute("DELETE FROM productos WHERE id_producto = %s", (id,))
        conexion.commit()
    conexion.close()
    return redirect(url_for('dashboard'))

@app.route('/negocio/<int:id>')
def ver_negocio(id):
    conexion = conectar_db()
    with conexion.cursor() as cursor:
        cursor.execute("SELECT * FROM negocios WHERE id_negocio = %s", (id,))
        negocio = cursor.fetchone()
        cursor.execute("SELECT * FROM productos WHERE id_negocio = %s", (id,))
        productos = cursor.fetchall()
    conexion.close()
    return render_template('catalogo.html', negocio=negocio, productos=productos)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('bienvenida'))

if __name__ == '__main__':
    app.run(debug=True)
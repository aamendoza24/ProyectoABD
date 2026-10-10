import bcrypt
from datetime import datetime, timedelta
from app.utils.db import get_db_connection
from app.repositories.empleado_repository import EmpleadoRepository
from app.repositories.usuario_repository import UsuarioRepository

class AdminService:
    """Maneja la lógica transaccional atómica para la creación y manipulación de Empleados y sus Cuentas"""

    @staticmethod
    def crear_empleado_y_usuario(datos_empleado, datos_usuario, admin_id, ip_address):
        """Envuelve la creación de Empleado, Usuario y Log en una única transacción"""
        nombre_completo = datos_empleado.get('nombre')
        cargo_id = datos_empleado.get('cargo_id')
        
        username = datos_usuario.get('username')
        email = datos_usuario.get('email')
        password = datos_usuario.get('password')
        role = datos_usuario.get('role')
        is_active = datos_usuario.get('is_active')
        
        if not all([nombre_completo, cargo_id, username, email, password, role]):
            raise ValueError("Todos los campos principales son obligatorios.")

        # Validamos unicidad de username/email preventivamente
        existente = EmpleadoRepository.obtener_usuario_cruzado_existente(username, email)
        if existente:
            raise ValueError("El nombre de usuario o correo electrónico ya está en uso.")

        conn = get_db_connection()
        try:
            # 1. Crear Empleado
            empleado_id = EmpleadoRepository.crear_empleado(conn, nombre_completo, cargo_id)
            
            # 2. Hash Password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # 3. Crear Usuario asociado
            created_at_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user_id = UsuarioRepository.crear_usuario(
                conn, username, email, hashed_password, role, is_active, empleado_id, created_at_str
            )
            
            # 4. Registrar Actividad
            desc = f"Cuenta creada por administrador (ID: {admin_id})"
            UsuarioRepository.registrar_actividad(conn, user_id, "Cuenta Creada", desc, ip_address)
            
            conn.commit()
            return True, "Empleado añadido exitosamente"
        except Exception as e:
            conn.rollback()
            raise Exception(f"No se pudo guardar el registro: {str(e)}")
        finally:
            conn.close()

    @staticmethod
    def editar_empleado_y_usuario(datos_empleado, datos_usuario, admin_id, ip_address):
        empleado_id = datos_empleado.get('empleado_id')
        nombre_completo = datos_empleado.get('nombre')
        cargo_id = datos_empleado.get('cargo_id')
        
        username = datos_usuario.get('username')
        email = datos_usuario.get('email')
        password = datos_usuario.get('password') # Puede ser None
        role = datos_usuario.get('role')
        is_active = datos_usuario.get('is_active')

        if not all([empleado_id, nombre_completo, cargo_id, username, email, role]):
            raise ValueError("Todos los campos excepto la contraseña son obligatorios.")

        # Verificar unicidad (excluyendo el que se está editando)
        existente = EmpleadoRepository.obtener_usuario_cruzado_existente(username, email, empleado_id)
        if existente:
            raise ValueError("El nombre de usuario o correo electrónico ya está en uso por otro empleado.")

        conn = get_db_connection()
        try:
            # 1. Editar Empleado
            EmpleadoRepository.actualizar_empleado(conn, empleado_id, nombre_completo, cargo_id)
            
            # 2. Verificar existencia del usuario o si se tiene que crear uno nuevo on-the-fly
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE IDEmpleado = ?", (empleado_id,))
            user_result = cursor.fetchone()
            
            hashed_password = None
            if password:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            if user_result:
                user_id = user_result[0]
                UsuarioRepository.actualizar_usuario(conn, user_id, username, email, role, is_active, hashed_password)
                desc = f"Cuenta actualizada por administrador (ID: {admin_id})"
                UsuarioRepository.registrar_actividad(conn, user_id, "Cuenta Actualizada", desc, ip_address)
            else:
                # Si no existía un usuario para este empleado, crearlo
                fallback_hash = bcrypt.hashpw("changeme123".encode('utf-8'), bcrypt.gensalt())
                user_id = UsuarioRepository.crear_usuario(
                    conn, username, email, hashed_password or fallback_hash, role, is_active, empleado_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                desc = f"Cuenta creada por administrador (ID: {admin_id}) durante edición"
                UsuarioRepository.registrar_actividad(conn, user_id, "Cuenta Creada", desc, ip_address)
            
            conn.commit()
            return True, "Empleado actualizado exitosamente"
        except Exception as e:
            conn.rollback()
            raise Exception(f"No se pudo actualizar el registro: {str(e)}")
        finally:
            conn.close()

    @staticmethod
    def eliminar_empleado_completo(empleado_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE IDEmpleado = ?", (empleado_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id = user_result[0]
                UsuarioRepository.eliminar_log_y_usuario_por_id(conn, user_id)
                
            EmpleadoRepository.eliminar_empleado(conn, empleado_id)
            conn.commit()
            return True, "Empleado eliminado exitosamente"
        except Exception as e:
            conn.rollback()
            raise Exception(str(e))
        finally:
            conn.close()

    @staticmethod
    def alternar_estado_usuario(empleado_id, is_active_bool, admin_id, ip_address):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE IDEmpleado = ?", (empleado_id,))
            user_result = cursor.fetchone()
            
            if not user_result:
                raise ValueError("Usuario no encontrado")
                
            user_id = user_result[0]
            cursor.execute("UPDATE usuarios SET is_active = ? WHERE id = ?", (is_active_bool, user_id))
            
            tipo = "Cuenta Activada" if is_active_bool else "Cuenta Desactivada"
            UsuarioRepository.registrar_actividad(conn, user_id, tipo, f"Acción realizada por administrador (ID: {admin_id})", ip_address)
            
            conn.commit()
            return True, ("Empleado habilitado exitosamente" if is_active_bool else "Empleado deshabilitado exitosamente")
        except Exception as e:
            conn.rollback()
            raise Exception(str(e))
        finally:
            conn.close()

    @staticmethod
    def alternar_bloqueo_usuario(empleado_id, is_locked_bool, admin_id, ip_address):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE IDEmpleado = ?", (empleado_id,))
            user_result = cursor.fetchone()
            
            if not user_result:
                raise ValueError("Usuario no encontrado")
                
            user_id = user_result[0]
            
            if is_locked_bool:
                locked_until = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    UPDATE usuarios 
                    SET account_locked = 1, locked_until = ?, failed_login_attempts = 5
                    WHERE id = ?
                """, (locked_until, user_id))
                tipo = "Cuenta Bloqueada"
            else:
                cursor.execute("""
                    UPDATE usuarios 
                    SET account_locked = 0, locked_until = NULL, failed_login_attempts = 0
                    WHERE id = ?
                """, (user_id,))
                tipo = "Cuenta Desbloqueada"
                
            UsuarioRepository.registrar_actividad(conn, user_id, tipo, f"Acción realizada por administrador (ID: {admin_id})", ip_address)
            conn.commit()
            
            return True, ("Empleado bloqueado exitosamente" if is_locked_bool else "Empleado desbloqueado exitosamente")
        except Exception as e:
            conn.rollback()
            raise Exception(str(e))
        finally:
            conn.close()

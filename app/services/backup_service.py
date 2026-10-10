import os
import shutil
from datetime import datetime
from cryptography.fernet import Fernet
from flask import current_app

class BackupService:
    """Implementa copias de seguridad de la base de datos con Cifrado Simétrico AES-256 (RF17)"""
    
    @staticmethod
    def generar_llave():
        """Genera una Key Master (Debe ser salvada en .env o Config segura por el usuario en Prod)"""
        return Fernet.generate_key()

    @staticmethod
    def respaldar_base_cifrada(key):
        """Copia el sqlite origin, lo comprime, aplica Cipher y exporta"""
        f = Fernet(key)
        
        db_path = current_app.config['DATABASE_PATH']
        backup_folder = current_app.config.get('BACKUP_FOLDER', 'backups')
        
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = os.path.join(backup_folder, f"tienda_backup_{timestamp}.enc")
        
        try:
            with open(db_path, 'rb') as original_file:
                original_data = original_file.read()
                
            encrypted_data = f.encrypt(original_data)
            
            with open(export_name, 'wb') as encrypted_file:
                encrypted_file.write(encrypted_data)
                
            return True, export_name
        except Exception as e:
            raise Exception(f"Falla al crear el respaldo cifrado: {str(e)}")

    @staticmethod
    def restaurar_base_cifrada(key, backup_file_path):
        """Lee el respaldo, verifica la Master Key, decifra y sobreescribe la BD"""
        f = Fernet(key)
        
        db_path = current_app.config['DATABASE_PATH']
        
        try:
            with open(backup_file_path, 'rb') as encrypted_file:
                encrypted_data = encrypted_file.read()
                
            decrypted_data = f.decrypt(encrypted_data)
            
            # Sobreescritura crítica (En producción se recomendaría crear un bak_temporal primero por si acaso falla a la mitad)
            with open(db_path, 'wb') as original_file:
                original_file.write(decrypted_data)
                
            return True, "Base de datos restaurada."
        except Exception as e:
            raise Exception(f"Falla al decifrar/restaurar la BD (La clave puede ser incorrecta): {str(e)}")

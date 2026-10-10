#!/usr/bin/env python3
"""
Script para optimizar las fuentes de la aplicación
Elimina formatos innecesarios y mantiene solo woff2 para mejor rendimiento
"""

import os
import shutil

def optimize_fonts():
    """Optimiza las fuentes eliminando formatos innecesarios"""
    
    # Rutas de las fuentes
    fontawesome_path = "app/static/fonts/fontawesome"
    simple_line_path = "app/static/fonts/simple-line-icons"
    
    # Formatos a mantener (solo woff2 para mejor rendimiento)
    keep_formats = ['.woff2']
    
    # Formatos a eliminar
    remove_formats = ['.eot', '.svg', '.ttf', '.woff']
    
    print("🔧 Optimizando fuentes...")
    
    # Optimizar FontAwesome
    if os.path.exists(fontawesome_path):
        print(f"📁 Procesando FontAwesome en {fontawesome_path}")
        for filename in os.listdir(fontawesome_path):
            file_path = os.path.join(fontawesome_path, filename)
            if os.path.isfile(file_path):
                # Verificar si es un formato a eliminar
                should_remove = any(filename.endswith(ext) for ext in remove_formats)
                if should_remove:
                    try:
                        os.remove(file_path)
                        print(f"  ❌ Eliminado: {filename}")
                    except Exception as e:
                        print(f"  ⚠️ Error eliminando {filename}: {e}")
                elif any(filename.endswith(ext) for ext in keep_formats):
                    print(f"  ✅ Mantenido: {filename}")
    
    # Optimizar Simple Line Icons
    if os.path.exists(simple_line_path):
        print(f"📁 Procesando Simple Line Icons en {simple_line_path}")
        for filename in os.listdir(simple_line_path):
            file_path = os.path.join(simple_line_path, filename)
            if os.path.isfile(file_path):
                # Verificar si es un formato a eliminar
                should_remove = any(filename.endswith(ext) for ext in remove_formats)
                if should_remove:
                    try:
                        os.remove(file_path)
                        print(f"  ❌ Eliminado: {filename}")
                    except Exception as e:
                        print(f"  ⚠️ Error eliminando {filename}: {e}")
                elif any(filename.endswith(ext) for ext in keep_formats):
                    print(f"  ✅ Mantenido: {filename}")
    
    print("✅ Optimización de fuentes completada!")
    print("\n📊 Resumen de optimizaciones:")
    print("  • Solo se mantienen archivos .woff2 (formato más eficiente)")
    print("  • Se eliminaron formatos .eot, .svg, .ttf, .woff")
    print("  • Reducción significativa en tamaño de archivos")
    print("  • Mejor rendimiento de carga")

if __name__ == "__main__":
    optimize_fonts() 
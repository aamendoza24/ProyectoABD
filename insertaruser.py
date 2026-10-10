import sqlite3

def eliminar_producto():
    try:
        conexion = sqlite3.connect("library.db")
        cursor = conexion.cursor()

        cursor.execute("DELETE FROM Stock_Sucursal")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'Stock_Sucursal'")
        conexion.commit()

        print(f"Stock_Sucursal eliminado correctamente.")
    except Exception as e:
        print(f"Error al eliminar Stock_Sucursal: {e}")
    finally:
        cursor.close()
        conexion.close()

# Llamada de ejemplo
eliminar_producto()

# generar_hash.py
import bcrypt

usuarios = {
    "pruebacoq": "123456",
    
}
print("🔐 HASHES REALES PARA SQL SERVER\n" + "="*50)
for user, pwd in usuarios.items():
    hash_real = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print(f"Usuario: {user}")
    print(f"Contraseña: {pwd}")
    print(f"Hash: {hash_real}\n")

# Esto mantiene la ventana abierta hasta que pulses Enter
input("✅ Presiona Enter para salir...")
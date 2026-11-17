"""
Script Lanzador de la Aplicación Web de Netflix (Local).
Verifica requisitos, inicia el servidor FastAPI en Uvicorn y abre automáticamente el navegador.

Uso:
    python run_app.py
"""

import sys
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from config import PARQUET_FILES, SERVER_HOST, SERVER_PORT

def verify_environment():
    print("=" * 70)
    print("NETFLIX GLOBAL ANALYTICS & DYNAMIC RECOMMENDER - LANZADOR")
    print("=" * 70)
    
    # 1. Verificar si existen los parquets analíticos
    master_p = PARQUET_FILES["master"]
    hubs_p = PARQUET_FILES["hubs"]
    
    if not master_p.exists() or not hubs_p.exists():
        print("[!] No se encontraron los archivos Parquet procesados. Ejecutando pipeline inicial...")
        import subprocess
        subprocess.run([sys.executable, "main.py", "--all"], check=True)
    else:
        print(f"[OK] Catálogo maestro detectado: {master_p.name} ({master_p.stat().st_size / (1024**2):.1f} MB)")
        print(f"[OK] Matriz de decisión de Hubs detectada: {hubs_p.name}")

def main():
    verify_environment()
    
    import uvicorn
    url = f"http://{SERVER_HOST}:{SERVER_PORT}"
    print(f"\n[*] Servidor disponible en: {url}")
    print("[*] Presiona Ctrl + C en la terminal para detener el servidor.\n")
    
    # Abrir navegador tras 1.2 segundos
    import threading
    def open_browser():
        time.sleep(1.2)
        print(f"[✓] Abriendo navegador en {url}...")
        webbrowser.open(url)
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run("server:app", host=SERVER_HOST, port=SERVER_PORT, log_level="info", reload=False)

if __name__ == "__main__":
    main()


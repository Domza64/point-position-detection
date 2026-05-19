import os
import sys
import subprocess
import time
import pandas as pd

# Adjust import path to find Completer module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from Completer.completer import PointCloudCompleter

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VISUALIZER_DIR = os.path.join(BASE_DIR, "Visualizer")
CONFIG_PATH = os.path.join(VISUALIZER_DIR, "config.txt")
TEST_IMAGES_DIR = os.path.join(VISUALIZER_DIR, "TestImages")

def load_config():
    config = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        config[key.strip().lower()] = val.strip()
        except Exception as e:
            print(f"[-] Greška pri čitanju config.txt: {e}")
    return config

def save_config(config):
    try:
        # Read existing file to keep comments, or overwrite if missing
        lines = []
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        # Update values
        new_lines = []
        updated_keys = set()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _ = stripped.split("=", 1)
                key_clean = key.strip().lower()
                if key_clean in config:
                    new_lines.append(f"{key.strip()} = {config[key_clean]}\n")
                    updated_keys.add(key_clean)
                    continue
            new_lines.append(line)
            
        # Add keys that weren't present
        for key, val in config.items():
            if key not in updated_keys:
                new_lines.append(f"{key} = {val}\n")
                
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"[-] Greška pri spremanju config.txt: {e}")

def run_completion(dataset_name):
    print("\n" + "="*50)
    print(f"   POKRETANJE POINT CLOUD COMPLETERA - {dataset_name.upper()}")
    print("="*50)
    
    # 1. Determine input CSV path
    config = load_config()
    key = f"{dataset_name.lower()}_csv_path"
    
    csv_path = None
    if key in config and config[key]:
        val = config[key]
        if os.path.isabs(val):
            csv_path = val
        else:
            csv_path = os.path.abspath(os.path.join(BASE_DIR, val))
            if not os.path.exists(csv_path):
                alt_path = os.path.abspath(os.path.join(VISUALIZER_DIR, val))
                if os.path.exists(alt_path):
                    csv_path = alt_path
            
    # Default path if none specified
    if not csv_path or not os.path.exists(csv_path):
        csv_path = os.path.join(TEST_IMAGES_DIR, dataset_name, "points.csv")
        if not os.path.exists(csv_path):
            outer_default = os.path.join(BASE_DIR, "TestImages", dataset_name, "points.csv")
            if os.path.exists(outer_default):
                csv_path = outer_default
        
    print(f"[+] Tražim ulaznu CSV datoteku na: {csv_path}")
    
    # Check if raw CSV file exists
    if not os.path.exists(csv_path):
        print(f"[-] OPREZ: Nije pronađena CSV datoteka na putanji: {csv_path}")
        print("    Provjerite je li vaš kolega izvezao skenirane točke u tu datoteku.")
        print("    Generiram sintetičke (mock) točke kako biste mogli vidjeti rad algoritma za popunjavanje...")
        
        # Generate some synthetic points to simulate the input
        from Visualizer.server import VisualizerHTTPHandler
        # Instantiate a mock handler to access the synthetic points generator
        handler = VisualizerHTTPHandler
        # We need mock dataset config to generate
        import random
        # Just create a simple dummy DataFrame of 500 points
        data = []
        for _ in range(500):
            x = random.uniform(-30, 30)
            y = random.uniform(-30, 30)
            z = random.uniform(80, 140)
            data.append([x, y, z, 240, 240, 240])
        df = pd.DataFrame(data, columns=['X', 'Y', 'Z', 'R', 'G', 'B'])
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        df.to_csv(csv_path, index=False)
        print(f"[+] Privremena datoteka stvorena s 500 mock točaka.")
    
    # 2. Read points
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[-] Greška prilikom čitanja CSV datoteke: {e}")
        return
        
    # 3. Process with Completer
    try:
        completer = PointCloudCompleter(dataset_name)
        completed_df = completer.complete(df)
    except Exception as e:
        print(f"[-] Greška tijekom izvođenja algoritma completiona: {e}")
        return
        
    # 4. Save output
    # We save it back to the exact path the visualizer will read (points.csv)
    # The visualizer will notice the updated modification date and automatically compile it on refresh!
    try:
        # Make a backup of the original if it was a real scan
        original_backup = csv_path.replace(".csv", "_original.csv")
        if not os.path.exists(original_backup) and os.path.exists(csv_path):
            os.rename(csv_path, original_backup)
            print(f"[+] Napravljena sigurnosna kopija izvornih točaka: {os.path.basename(original_backup)}")
            
        completed_df.to_csv(csv_path, index=False)
        print(f"[+] Uspješno snimljen cjeloviti oblak točaka (uključujući skrivene strane) na: {csv_path}")
        print("[+] Napomena: Vizualizator će automatski učitati ove točke prilikom sljedećeg osvježavanja stranice.")
    except Exception as e:
        print(f"[-] Greška pri spremanju završenog oblaka: {e}")

def main():
    active_dataset = "box"
    server_process = None
    
    while True:
        # Check active dataset status
        config = load_config()
        key = f"{active_dataset.lower()}_csv_path"
        csv_path = config.get(key, f"TestImages/{active_dataset.capitalize()}/points.csv")
        
        abs_csv_path = csv_path if os.path.isabs(csv_path) else os.path.join(VISUALIZER_DIR, csv_path)
        if not os.path.exists(abs_csv_path):
            alt_abs = csv_path if os.path.isabs(csv_path) else os.path.join(BASE_DIR, csv_path)
            if os.path.exists(alt_abs):
                abs_csv_path = alt_abs
        csv_exists = os.path.exists(abs_csv_path)
        
        # CLI print
        print("\n" + "="*60)
        print("          3DMegaMind - STEM Games 2026 Orchestrator")
        print("="*60)
        print(f"  [>] AKTIVNI DATASET:    {active_dataset.upper()}")
        print(f"  [>] Putanja do CSV-a:   {csv_path}")
        print(f"  [>] Status CSV datoteke: {'[ PRONAĐENO ]' if csv_exists else '[- NEDOSTAJE -]'}")
        print("-"*60)
        print("  1. Odaberi aktivni dataset (Box, Entrance, Statue, Fountain)")
        print("  2. Nadopuni nedostajuće strane (Pokreni Point Cloud Completer)")
        print("  3. Pokreni/Ponovno pokreni 3D Visualizer Server (port 8000)")
        print("  4. Prikaz uputa za formatiranje i preciznost")
        print("  5. Izračunaj poziciju kamere iz 2D-3D točaka (PnP Solver)")
        print("  6. Izlaz")
        print("="*60)
        
        choice = input("Odaberite opciju (1-6): ").strip()
        
        if choice == "1":
            print("\nOdaberite dataset:")
            print("1) Box (Kocka)")
            print("2) Entrance (Ulaz/Hodnik)")
            print("3) Statue (Kip)")
            print("4) Fountain (Fontana)")
            ds_choice = input("Unos (1-4): ").strip()
            
            mapping = {"1": "box", "2": "entrance", "3": "statue", "4": "fountain"}
            if ds_choice in mapping:
                active_dataset = mapping[ds_choice]
                print(f"[+] Dataset promijenjen u: {active_dataset.upper()}")
            else:
                print("[-] Nevaljan izbor.")
                
        elif choice == "2":
            run_completion(active_dataset)
            input("\nPritisnite Enter za nastavak...")
            
        elif choice == "3":
            # Start or restart server
            print("[+] Pokrećem 3D Visualizer HTTP poslužitelj...")
            if server_process:
                print("[+] Zaustavljam prethodno pokrenuti server...")
                try:
                    server_process.terminate()
                    server_process.wait(timeout=3)
                except Exception as e:
                    pass
            
            server_script = os.path.join(VISUALIZER_DIR, "server.py")
            server_process = subprocess.Popen(
                [sys.executable, server_script],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            time.sleep(1.5) # Wait for server bind
            print("[+] Server uspješno pokrenut na: http://localhost:8000")
            print("[+] Otvorite ovaj link u pregledniku kako biste vidjeli 3D model.")
            input("\nPritisnite Enter za povratak na izbornik (server će ostati pokrenut)...")
            
        elif choice == "4":
            print("\n" + "-"*50)
            print("   PRECIZNOST PODATAKA I FORMAT CSV DATOTEKE")
            print("-"*50)
            print("1. PRECIZNOST:")
            print("   - Točke se učitavaju i renderiraju u 32-bitnom decimalnom formatu (Float32).")
            print("   - To omogućuje sub-milimetarsku preciznost (do 7 značajnih znamenki).")
            print("   - Nema gubitka koordinatne točnosti u grafičkom prikazu.")
            print("\n2. FORMAT CSV-a:")
            print("   - CSV mora sadržavati stupce X, Y, Z (i opcionalno R, G, B za boju).")
            print("   - Ako RGB nedostaje, sustav boji točke u gradijent po visini ili dubini kamere.")
            print("\n3. NEURALNA NADOPUNA STRANA (Completer):")
            print("   - Box: popunjava svih 6 stranica kocke uklapanjem 3D kvadra.")
            print("   - Entrance: zrcali točke s lijeve na desnu stranu koristeći bilateralnu simetriju.")
            print("   - Fountain: koristi rotacijsku simetriju (360 stupnjeva) oko središta fontane.")
            print("   - Statue: pronalazi glavnu ravninu simetrije preko PCA analize i preslikava leđa kipa.")
            print("-"*50)
            input("\nPritisnite Enter za nastavak...")
            
        elif choice == "5":
            # Run PnP solver
            # Determine directory (self-contained first, then fallback to outer)
            dataset_dir = os.path.join(TEST_IMAGES_DIR, active_dataset.capitalize())
            if not os.path.exists(dataset_dir):
                dataset_dir = os.path.join(BASE_DIR, "TestImages", active_dataset.capitalize())
            
            if not os.path.exists(dataset_dir):
                print(f"[-] Mapa za dataset {active_dataset} nije pronađena na putanji {dataset_dir}")
            else:
                try:
                    from PnP.pnp_solver import interactive_cli
                    interactive_cli(active_dataset, dataset_dir)
                except Exception as e:
                    print(f"[-] Greška prilikom pokretanja PnP solvera: {e}")
            input("\nPritisnite Enter za nastavak...")
 
        elif choice == "6":
            if server_process:
                print("[+] Zaustavljam Visualizer poslužitelj...")
                server_process.terminate()
            print("[+] Hvala što ste koristili 3DMegaMind! Doviđenja.")
            break
        else:
            print("[-] Nevaljan izbor, pokušajte ponovno.")

if __name__ == "__main__":
    main()

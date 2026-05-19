import os
import shutil
import numpy as np
import pandas as pd

def transform_point_cloud():
    # 1. Copy fountain.csv to objekt.csv if objekt.csv does not exist yet in the working directory
    source_csv = os.path.join("TestImages", "Fountain", "fountain.csv")
    if not os.path.exists("objekt.csv"):
        if os.path.exists(source_csv):
            print(f"[+] Kopiram {source_csv} u objekt.csv...")
            shutil.copy(source_csv, "objekt.csv")
        else:
            print("[-] Pogreška: Nije pronađen izvorni fountain.csv!")
            return

    # Učitaj objekt.csv
    print("[~] Učitavam objekt.csv...")
    df = pd.read_csv("objekt.csv")
    
    # Izdvoji koordinate
    pts = df[['X', 'Y', 'Z']].values
    
    # 2. Izračunaj centroid (centar)
    centroid = np.mean(pts, axis=0)
    print(f"[+] Izračunani centroid objekta: X={centroid[0]:.4f}, Y={centroid[1]:.4f}, Z={centroid[2]:.4f}")
    
    # 3. Rotacijska matrica za rotaciju od 90 stupnjeva oko X osi (desni koordinatni sustav)
    # R_x(90 deg) = [[1, 0, 0], [0, cos(90), -sin(90)], [0, sin(90), cos(90)]]
    theta = np.radians(90.0)
    c, s = np.cos(theta), np.sin(theta)
    
    # Zbog numeričke preciznosti koristimo egzaktne vrijednosti: cos(90)=0, sin(90)=1
    R = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0]
    ])
    
    # Centriranje točaka, rotacija oko centroida, i translacija na ishodište (0,0,0)
    # Ovo uspravlja objekt i postavlja ga točno na pravo mjesto u središtu meta (checkerboarda).
    # P_new = R * (P - centroid) + t
    # Ako želimo da centar objekta bude na ishodištu, t = [0, 0, 0]
    # Ako želimo pomaknuti po dubini/visini, možemo dodati pomak. 
    # Za postavljanje na ishodište (gdje je meta):
    t = np.array([0.0, 0.0, 0.0])
    
    # Primjena rotacije i translacije
    pts_centered = pts - centroid
    pts_rotated = pts_centered @ R.T + t
    
    # 4. Formiranje 4x4 Homogene transformacijske matrice H
    # P_new = R * P + (t - R * centroid)
    translation_vector = t - R @ centroid
    
    H = np.zeros((4, 4))
    H[0:3, 0:3] = R
    H[0:3, 3] = translation_vector
    H[3, 3] = 1.0
    
    print("\n[+] 4x4 Homogena Matrica Transformacije (H):")
    print(np.array2string(H, formatter={'float_kind':lambda x: f"{x:12.6f}"}))
    
    # Ažuriraj stupce u DataFrameu
    df_transformed = df.copy()
    df_transformed['X'] = pts_rotated[:, 0]
    df_transformed['Y'] = pts_rotated[:, 1]
    df_transformed['Z'] = pts_rotated[:, 2]
    
    # 5. Spremi transformirani oblak
    output_filename = "transformirani_objekt.csv"
    df_transformed.to_csv(output_filename, index=False)
    print(f"\n[+] USPJEH: Transformirani oblak točaka spremljen u: {output_filename}")
    print(f"    Broj točaka: {len(df_transformed)}")

if __name__ == "__main__":
    transform_point_cloud()

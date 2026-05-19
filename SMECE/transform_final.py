import os
import numpy as np
import pandas as pd

def transform_point_cloud_final():
    # 1. Učitaj originalni backup (fountain2.csv je već skaliran sa 100)
    source_backup = os.path.join("TestImages", "Fountain", "fountain2.csv")
    if not os.path.exists(source_backup):
        print(f"[-] Pogreška: Nije pronađen backup {source_backup}")
        return
        
    print("[~] Učitavam originalni backup (fountain2.csv)...")
    df = pd.read_csv(source_backup)
    
    # Koordinate točaka (već su skalirane u fountain2.csv)
    pts = df[['X', 'Y', 'Z']].values
    
    # 2. Izračunaj centroid originalnog oblaka (skaliranog)
    centroid = np.mean(pts, axis=0)
    print(f"[+] Centroid originalnog objekta: X={centroid[0]:.4f}, Y={centroid[1]:.4f}, Z={centroid[2]:.4f}")
    
    # 3. Kombinirana rotacija: Rx(90 deg) pa Rz(180 deg)
    # R_x(90) = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
    # R_z(180) = [[-1, 0, 0], [0, -1, 0], [0, 0, 1]]
    # R = R_z(180) * R_x(90)
    R_x = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0]
    ])
    
    R_z = np.array([
        [-1.0, 0.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, 1.0]
    ])
    
    R = R_z @ R_x
    
    # Translacija centroida na ishodište (t = [0, 0, 0])
    t = np.array([0.0, 0.0, 0.0])
    
    # Primijeni transformaciju: P_new = R * (P - centroid) + t
    pts_centered = pts - centroid
    pts_transformed = pts_centered @ R.T + t
    
    # 4. Formiranje 4x4 Homogene transformacijske matrice H
    # P_new = R * P + (t - R * centroid)
    translation_vector = t - R @ centroid
    
    H = np.zeros((4, 4))
    H[0:3, 0:3] = R
    H[0:3, 3] = translation_vector
    H[3, 3] = 1.0
    
    print("\n[+] 4x4 Homogena Matrica Transformacije (H):")
    print(np.array2string(H, formatter={'float_kind':lambda x: f"{x:12.6f}"}))
    
    # Ažuriraj stupce
    df_transformed = df.copy()
    df_transformed['X'] = pts_transformed[:, 0]
    df_transformed['Y'] = pts_transformed[:, 1]
    df_transformed['Z'] = pts_transformed[:, 2]
    
    # Spremi rezultate
    df_transformed.to_csv("transformirani_objekt.csv", index=False)
    df_transformed.to_csv(os.path.join("TestImages", "Fountain", "fountain.csv"), index=False)
    df_transformed.to_csv(os.path.join("Visualizer", "fountain.csv"), index=False)
    
    print(f"\n[+] Datoteke su uspješno spremljene!")
    print(f"    Ukupan broj točaka: {len(df_transformed)}")

if __name__ == "__main__":
    transform_point_cloud_final()

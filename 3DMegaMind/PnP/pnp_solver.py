import os
import re
import sys
import subprocess

# Ensure numpy and opencv-python are installed
try:
    import numpy as np
    import cv2
except ImportError:
    print("[!] Modul 'numpy' ili 'opencv-python' nedostaje.")
    choice = input("[?] Želite li ih automatski instalirati putem pip-a? (y/n): ").strip().lower()
    if choice == 'y':
        print("[~] Instaliram numpy i opencv-python...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy", "opencv-python"])
        import numpy as np
        import cv2
        print("[+] Instalacija uspješna!")
    else:
        print("[-] Nemoguće pokrenuti PnP solver bez potrebnih biblioteka.")
        sys.exit(1)

class CameraPoseSolver:
    def __init__(self, dataset_dir):
        self.dataset_dir = dataset_dir
        self.k_matrix = self.load_k_matrix()

    def load_k_matrix(self):
        k_path = os.path.join(self.dataset_dir, "K.txt")
        if not os.path.exists(k_path):
            raise FileNotFoundError(f"Matrica K nije pronađena na putanji: {k_path}")
        
        try:
            with open(k_path, "r", encoding="utf-8") as f:
                content = f.read()
            nums = [float(x) for x in re.findall(r'[\d.]+', content)]
            if len(nums) >= 9:
                return np.array([
                    [nums[0], nums[1], nums[2]],
                    [nums[3], nums[4], nums[5]],
                    [nums[6], nums[7], nums[8]]
                ], dtype=np.float64)
            else:
                raise ValueError("Format u K.txt ne sadrži 9 vrijednosti za 3x3 matricu.")
        except Exception as e:
            print(f"[-] Greška prilikom čitanja K.txt: {e}")
            raise

    def solve_pose(self, object_points, image_points):
        """
        Rješava PnP problem za učitane 2D-3D korespondencije.
        
        object_points: list/array od N parova 3D koordinata [X, Y, Z]
        image_points: list/array od N parova 2D piksela [u, v]
        """
        pts_3d = np.array(object_points, dtype=np.float64)
        pts_2d = np.array(image_points, dtype=np.float64)
        
        if len(pts_3d) < 4:
            raise ValueError("Potrebno je definirati najmanje 4 korespodentne točke.")

        # Solve Perspective-n-Point
        # Use EPNP for 4-5 points to avoid DLT 6-point initial guess requirement, otherwise use ITERATIVE
        pnp_flag = cv2.SOLVEPNP_EPNP if len(pts_3d) < 6 else cv2.SOLVEPNP_ITERATIVE
        success, rvec, tvec = cv2.solvePnP(pts_3d, pts_2d, self.k_matrix, distCoeffs=None, flags=pnp_flag)
        if not success:
            raise RuntimeError("PnP algoritam nije uspio konvergirati.")

        # Convert rotation vector to 3x3 rotation matrix R
        R, _ = cv2.Rodrigues(rvec)

        # Camera center in world space: C = -R^T * T
        C = -R.T @ tvec
        C = C.flatten()

        # Extract direction vectors and convert to left-handed format expected by project datasets:
        # F_dataset = r3 (Optical axis)
        # R_dataset = -r1 (Negative horizontal axis)
        # U_dataset = -r2 (Negative vertical axis, pointing UP since OpenCV Y points DOWN)
        F = R.T[:, 2]
        Right = -R.T[:, 0]
        Up = -R.T[:, 1]

        # Normalize to be safe
        F /= np.linalg.norm(F)
        Right /= np.linalg.norm(Right)
        Up /= np.linalg.norm(Up)

        return {
            "position": C,
            "forward": F,
            "right": Right,
            "up": Up
        }

    def save_camera_to_input_file(self, camera_id, pose):
        """
        Sprema/nadodaje izračunatu kameru u input.txt datoteku dataset-a.
        """
        # Find prefix (e.g. Fountain -> fountainInput.txt, Statue -> statueInput.txt)
        dataset_name = os.path.basename(self.dataset_dir)
        input_filename = f"{dataset_name.lower()}Input.txt"
        input_path = os.path.join(self.dataset_dir, input_filename)

        camera_block = (
            f"\n{camera_id})\n"
            f"CamPosition:\tX={pose['position'][0]:.6f} Y={pose['position'][1]:.6f} Z={pose['position'][2]:.6f}\n"
            f"CamForward:\tX={pose['forward'][0]:.3f} Y={pose['forward'][1]:.3f} Z={pose['forward'][2]:.3f}\n"
            f"CamRight:\tX={pose['right'][0]:.3f} Y={pose['right'][1]:.3f} Z={pose['right'][2]:.3f}\n"
            f"CamUp:\t\tX={pose['up'][0]:.3f} Y={pose['up'][1]:.3f} Z={pose['up'][2]:.3f}\n"
        )

        try:
            # If file exists, read it to verify if camera_id already exists and should be overwritten
            existing_blocks = {}
            if os.path.exists(input_path):
                with open(input_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Split by camera IDs
                blocks = re.split(r'\n\s*(\d+)\)\s*\n', '\n' + content)
                # First element is prefix before any camera ID (usually empty)
                prefix = blocks[0].strip()
                for i in range(1, len(blocks), 2):
                    if i + 1 < len(blocks):
                        existing_blocks[int(blocks[i])] = blocks[i+1].strip()

            # Overwrite or add
            existing_blocks[int(camera_id)] = (
                f"CamPosition:\tX={pose['position'][0]:.6f} Y={pose['position'][1]:.6f} Z={pose['position'][2]:.6f}\n"
                f"CamForward:\tX={pose['forward'][0]:.3f} Y={pose['forward'][1]:.3f} Z={pose['forward'][2]:.3f}\n"
                f"CamRight:\tX={pose['right'][0]:.3f} Y={pose['right'][1]:.3f} Z={pose['right'][2]:.3f}\n"
                f"CamUp:\t\tX={pose['up'][0]:.3f} Y={pose['up'][1]:.3f} Z={pose['up'][2]:.3f}"
            )

            # Recompile file contents in sorted order
            new_content = ""
            for cid in sorted(existing_blocks.keys()):
                new_content += f"\n{cid})\n{existing_blocks[cid]}\n"

            with open(input_path, "w", encoding="utf-8") as f:
                f.write(new_content.strip() + "\n")

            print(f"[+] Uspješno spremljena Camera {camera_id} u {input_path}")
            return input_path
        except Exception as e:
            print(f"[-] Greška prilikom pisanja u input datoteku: {e}")
            raise

def interactive_cli(dataset_name, dataset_dir):
    print("\n" + "="*50)
    print(f"   PnP SOLVER - PRORAČUN POZICIJE KAMERE ({dataset_name.upper()})")
    print("="*50)
    
    try:
        solver = CameraPoseSolver(dataset_dir)
    except Exception as e:
        print(f"[-] Nije moguće učitati matricu K: {e}")
        return

    print(f"[+] Matrica K uspješno učitana:")
    print(solver.k_matrix)
    print("\nUpute:")
    print("Za proračun su vam potrebne koordinate 4 točke koje možete prepoznati")
    print("i u 3D oblaku točaka (X, Y, Z) i na 2D slici (pikseli u, v).")
    
    camera_id = input("\n[?] Unesite ID kamere / broj slike (npr. 1 za fountain1.jpg): ").strip()
    if not camera_id.isdigit():
        print("[-] Nevaljan ID kamere.")
        return

    object_pts = []
    image_pts = []
    
    print("\nUnos točaka (potrebno je unijeti točno 4 točke):")
    for i in range(1, 5):
        print(f"\n--- TOČKA {i} ---")
        # 3D Coordinates
        try:
            x3d = float(input(f"  Unesite 3D koordinate X (iz oblaka): ").strip())
            y3d = float(input(f"  Unesite 3D koordinate Y (iz oblaka): ").strip())
            z3d = float(input(f"  Unesite 3D koordinate Z (iz oblaka): ").strip())
            
            # 2D Pixels
            u2d = float(input(f"  Unesite 2D koordinatu u (vodoravni piksel na slici): ").strip())
            v2d = float(input(f"  Unesite 2D koordinatu v (okomiti piksel na slici): ").strip())
        except ValueError:
            print("[-] Nevaljan unos broja. Molimo pokušajte ponovno.")
            return
            
        object_pts.append([x3d, y3d, z3d])
        image_pts.append([u2d, v2d])

    # Run Solver
    print("\n[~] Računam vanjske parametre kamere...")
    try:
        pose = solver.solve_pose(object_pts, image_pts)
        print("\n[+] PRORAČUN USPJEŠAN!")
        print(f"  Pozicija: X={pose['position'][0]:.4f} Y={pose['position'][1]:.4f} Z={pose['position'][2]:.4f}")
        print(f"  Forward:  X={pose['forward'][0]:.3f} Y={pose['forward'][1]:.3f} Z={pose['forward'][2]:.3f}")
        print(f"  Right:    X={pose['right'][0]:.3f} Y={pose['right'][1]:.3f} Z={pose['right'][2]:.3f}")
        print(f"  Up:       X={pose['up'][0]:.3f} Y={pose['up'][1]:.3f} Z={pose['up'][2]:.3f}")
        
        save_choice = input("\n[?] Želite li spremiti ove podatke u input datoteku? (y/n): ").strip().lower()
        if save_choice == 'y':
            solver.save_camera_to_input_file(camera_id, pose)
    except Exception as e:
        print(f"[-] Greška tijekom proračuna: {e}")

if __name__ == "__main__":
    # Test execution
    if len(sys.argv) > 2:
        interactive_cli(sys.argv[1], sys.argv[2])
    else:
        print("Pokrenite PnP solver preko 3DMegaMind orkestratora.")

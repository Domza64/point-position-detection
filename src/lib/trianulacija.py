import re
import numpy as np

# ── 1. PARSER ───────────────────────────────────────────────
def parse_camera_file(txt_path):
    cameras = []
    with open(txt_path, 'r') as f:
        content = f.read()
    blocks = re.split(r'\d+\)\s*\n', content)
    blocks = [b.strip() for b in blocks if 'CamPosition' in b]
    for block in blocks:
        def get_xyz(label):
            m = re.search(label + r'\s*X=([-\d.]+)\s+Y=([-\d.]+)\s+Z=([-\d.]+)', block)
            return np.array([float(m.group(1)), float(m.group(2)), float(m.group(3))]) if m else None
        right = get_xyz('CamRight:')
        if right is None: right = get_xyz('CamRight')
        up = get_xyz('CamUp:')
        if up is None: up = get_xyz('CamUp')
        cameras.append({
            'position': get_xyz('CamPosition:'),
            'forward':  get_xyz('CamForward:'),
            'right':    right,
            'up':       up,
        })
    return cameras

# ── 2. RAY (PDF formula) ─────────────────────────────────────
def get_ray(px, py, cam, res_x=1920, res_y=1080):
    coeff_right = (2.0 * (px - res_x / 2.0 + 0.5) / res_x)
    coeff_up    = (-2.0 * (py - res_y / 2.0 + 0.5) / res_y) * res_y / res_x
    direction   = cam['forward'] + coeff_right * cam['right'] + coeff_up * cam['up']
    return cam['position'].copy(), direction / np.linalg.norm(direction)

def get_ray_from_camera(px, py, cam, res_x=1920, res_y=1080):
    origin = cam["origin"]
    forward = cam["forward"]
    right = cam["right"]
    up = cam["up"]

    # normalizirani screen coords (-1 do 1)
    nx = (2 * px / res_x - 1)
    ny = (1 - 2 * py / res_y)

    direction = (
        forward
        + nx * right
        + ny * up
    )

    direction = direction / np.linalg.norm(direction)

    return origin, direction
# ── 3. TRIANGULACIJA ─────────────────────────────────────────
def triangulate(o1, d1, o2, d2):
    w0 = o1 - o2
    a, b, c = np.dot(d1,d1), np.dot(d1,d2), np.dot(d2,d2)
    d, e    = np.dot(d1,w0), np.dot(d2,w0)
    denom   = a*c - b*b
    if abs(denom) < 1e-6: return None, 999999
    t1 = (b*e - c*d) / denom
    t2 = (a*e - b*d) / denom
    p1 = o1 + t1*d1
    p2 = o2 + t2*d2
    return (p1+p2)/2.0, np.linalg.norm(p1-p2)

def triangulate_points(camera_params, points_pixels, res_x=1920, res_y=1080):
    results = []

    for i, pt_pixels in enumerate(points_pixels):
        rays = []

        for j, (px, py) in enumerate(pt_pixels):
            cam = camera_params[j]
            o, d = get_ray_from_camera(px, py, cam, res_x, res_y)
            rays.append((o, d))

        pairs = [(0,1),(0,2),(1,2)]
        best_pt, best_err, best_pair = None, float('inf'), None

        for a, b in pairs:
            pt, err = triangulate(
                rays[a][0], rays[a][1],
                rays[b][0], rays[b][1]
            )

            if pt is not None and err < best_err:
                best_pt, best_err, best_pair = pt, err, (a, b)

        results.append({
            'point_3d': best_pt,
            'error': best_err,
            'pair': best_pair
        })

        if best_pt is not None:
            rounded = np.round(best_pt).astype(int)
            print(f"Točka {i+1} (greška={best_err:.2f}): "
                  f"X={rounded[0]} Y={rounded[1]} Z={rounded[2]}")

    return results

import numpy as np

def load_3d_points(file_path):
    points = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("X"):
                continue  # preskoči header

            x, y, z = map(float, line.split())
            points.append(np.array([x, y, z]))

    return points
# ── 4. GLAVNI DIO ────────────────────────────────────────────
cameras = parse_camera_file('./StemGames2026_ProjectTask/TestImages/Box/boxInput.txt')
print(f"Učitano {len(cameras)} kamera")

points_pixels = load_3d_points(FILPATH IDE OVDJE)
slika_indeksi = [6, 7, 8]  # koje kamere koristimo (0-based, dakle slike 7,8,9)

# ── 5. TRIANGULACIJA ─────────────────────────────────────────
print("\nFINALNI REZULTATI:")
print("=" * 50)

sve_tocke = []

for i, pt_pixels in enumerate(points_pixels):
    rays = []
    for j, (px, py) in enumerate(pt_pixels):
        cam = cameras[slika_indeksi[j]]
        o, d = get_ray(px, py, cam)
        rays.append((o, d))

    # Probaj sve parove, uzmi najbolji (najmanja greška)
    pairs = [(0,1), (0,2), (1,2)]
    best_pt, best_err, best_pair = None, 999999, None
    for a, b in pairs:
        pt, err = triangulate(rays[a][0], rays[a][1], rays[b][0], rays[b][1])
        if pt is not None and err < best_err:
            best_pt, best_err, best_pair = pt, err, (slika_indeksi[a]+1, slika_indeksi[b]+1)

    rounded = np.round(best_pt).astype(int)
    sve_tocke.append(best_pt)
    print(f"Točka {i+1} (par slika {best_pair[0]}-{best_pair[1]}, greška={best_err:.2f}):")
    print(f"  X={rounded[0]}  Y={rounded[1]}  Z={rounded[2]}")
    print()

# ── 6. SPREMI ────────────────────────────────────────────────
sve_tocke = np.array(sve_tocke)
np.savetxt('./manualne_tocke_3d.txt', sve_tocke, fmt='%.2f', header='X Y Z', comments='')
print("Spremljeno: manualne_tocke_3d.txt")
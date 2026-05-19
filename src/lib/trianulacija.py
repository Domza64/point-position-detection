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

# ── 4. TRIANGULACIJA TRACKOVA ──────────────────────────────────
def triangulate_track(views_dict, cameras, res_x=1920, res_y=1080):
    img_indices = list(views_dict.keys())
    if len(img_indices) < 2:
        return None, float('inf')
    rays = []
    for idx in img_indices:
        px, py = views_dict[idx]
        cam = cameras[idx]
        o, d = get_ray(px, py, cam, res_x, res_y)
        rays.append((o, d))
        
    best_pt, best_err = None, float('inf')
    for i in range(len(rays)):
        for j in range(i+1, len(rays)):
            pt, err = triangulate(rays[i][0], rays[i][1], rays[j][0], rays[j][1])
            if pt is not None and err < best_err:
                best_pt, best_err = pt, err
                
    return best_pt, best_err

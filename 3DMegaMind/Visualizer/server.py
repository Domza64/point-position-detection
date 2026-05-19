import http.server
import socketserver
import json
import os
import re
import struct
import urllib.parse

PORT = 8000
VISUALIZER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(VISUALIZER_DIR)

# Parent project folder first, fallback to self-contained path
TEST_IMAGES_DIR = os.path.join(PROJECT_DIR, "TestImages")
if not os.path.exists(TEST_IMAGES_DIR):
    TEST_IMAGES_DIR = os.path.join(VISUALIZER_DIR, "TestImages")

def load_config():
    config = {}
    config_path = os.path.join(VISUALIZER_DIR, "config.txt")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        config[key.strip().lower()] = val.strip()
        except Exception as e:
            print(f"Error reading config.txt: {e}")
    return config

class VisualizerHTTPHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[HTTP] {fmt % args}")

    def serve_static_file(self, rel_path):
        """Serve a file from the static/ directory."""
        import mimetypes
        file_path = os.path.join(VISUALIZER_DIR, "static", rel_path.lstrip("/"))
        if not os.path.isfile(file_path):
            self.send_error(404, f"File not found: {rel_path}")
            return
        mime, _ = mimetypes.guess_type(file_path)
        mime = mime or "application/octet-stream"
        with open(file_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            parsed_url = urllib.parse.urlparse(self.path)
            path = parsed_url.path

            # Handle API routes
            if path == "/api/datasets":
                self.get_datasets()
            elif path.startswith("/api/dataset/") and path.endswith("/cameras"):
                dataset_name = path.split("/")[-2]
                self.get_dataset_cameras(dataset_name)
            elif path.startswith("/api/dataset/") and path.endswith("/points"):
                dataset_name = path.split("/")[-2]
                self.get_dataset_points(dataset_name)
            elif path.startswith("/images/"):
                self.serve_image(path)
            elif path == "/" or path == "":
                self.serve_static_file("/index.html")
            else:
                self.serve_static_file(path)
        except Exception as e:
            with open("crash_log.txt", "a") as f:
                f.write(f"CRASH: {e}\n")
                import traceback
                traceback.print_exc(file=f)
            print(f"[ERROR] do_GET crashed: {e}")

    def get_datasets(self):
        datasets = []
        if not os.path.exists(TEST_IMAGES_DIR):
            self.send_error_response(404, f"TestImages directory not found at {TEST_IMAGES_DIR}")
            return
            
        for name in os.listdir(TEST_IMAGES_DIR):
            dir_path = os.path.join(TEST_IMAGES_DIR, name)
            if os.path.isdir(dir_path):
                # Determine images extension and resolution
                img_ext = "png"
                res_x, res_y = 1920, 1080
                
                # Check for K.txt
                k_path = os.path.join(dir_path, "K.txt")
                has_k = os.path.exists(k_path)
                
                # Check for input camera file
                cam_file = None
                for f in os.listdir(dir_path):
                    if f.lower().endswith("input.txt"):
                        cam_file = f
                        break
                
                # Fountain is special
                if name.lower() == "fountain":
                    img_ext = "jpg"
                    res_x, res_y = 3072, 2048
                
                datasets.append({
                    "name": name,
                    "hasCameras": cam_file is not None,
                    "cameraFile": cam_file,
                    "hasK": has_k,
                    "imageExtension": img_ext,
                    "resolution": {"width": res_x, "height": res_y}
                })
                
        self.send_json_response(datasets)

    def get_dataset_cameras(self, dataset_name):
        dataset_dir = os.path.join(TEST_IMAGES_DIR, dataset_name)
        if not os.path.exists(dataset_dir):
            self.send_error_response(404, f"Dataset {dataset_name} not found")
            return
            
        # Parse K.txt if exists
        k_matrix = None
        k_path = os.path.join(dataset_dir, "K.txt")
        if os.path.exists(k_path):
            try:
                with open(k_path, "r", encoding="utf-8") as f:
                    k_content = f.read()
                # Find numbers inside brackets or lines
                # K = [fx 0 cx; 0 fy cy; 0 0 1]
                nums = re.findall(r'[\d.]+', k_content)
                if len(nums) >= 9:
                    k_matrix = {
                        "fx": float(nums[0]),
                        "fy": float(nums[4]),
                        "cx": float(nums[2]),
                        "cy": float(nums[5])
                    }
            except Exception as e:
                print(f"Error parsing K.txt: {e}")

        # Find camera input file
        cam_file = None
        for f in os.listdir(dataset_dir):
            if f.lower().endswith("input.txt"):
                cam_file = f
                break
                
        cameras = []
        if cam_file:
            cam_path = os.path.join(dataset_dir, cam_file)
            cameras = self.parse_camera_file(cam_path)
            
        self.send_json_response({
            "dataset": dataset_name,
            "cameras": cameras,
            "K": k_matrix
        })

    def get_dataset_points(self, dataset_name):
        dataset_dir = os.path.join(TEST_IMAGES_DIR, dataset_name)
        if not os.path.exists(dataset_dir):
            self.send_error_response(404, f"Dataset {dataset_name} not found")
            return
            
        # Check custom CSV path in config.txt
        config = load_config()
        key = f"{dataset_name.lower()}_csv_path"
        
        csv_path = None
        if key in config and config[key]:
            # Resolve path (can be absolute or relative to PROJECT_DIR first)
            val = config[key]
            if os.path.isabs(val):
                csv_path = val
            else:
                csv_path = os.path.abspath(os.path.join(PROJECT_DIR, val))
                if not os.path.exists(csv_path):
                    alt_path = os.path.abspath(os.path.join(VISUALIZER_DIR, val))
                    if os.path.exists(alt_path):
                        csv_path = alt_path
                
        # If no custom CSV configured or file doesn't exist, fallback to default points.csv in dataset folder
        if not csv_path or not os.path.exists(csv_path):
            csv_path = os.path.join(dataset_dir, "points.csv")
            if not os.path.exists(csv_path):
                outer_default = os.path.join(PROJECT_DIR, "TestImages", dataset_name, "points.csv")
                if os.path.exists(outer_default):
                    csv_path = outer_default
            
        # Determine cache binary path
        # If using custom CSV, save cache inside dataset folder as custom_cache.bin
        if csv_path != os.path.join(dataset_dir, "points.csv"):
            bin_path = os.path.join(dataset_dir, "custom_cache.bin")
        else:
            bin_path = os.path.join(dataset_dir, "points.bin")
            
        # Compile if CSV exists and binary is missing or stale
        recompile = False
        if os.path.exists(csv_path):
            if not os.path.exists(bin_path):
                recompile = True
            elif os.path.getmtime(csv_path) > os.path.getmtime(bin_path):
                recompile = True
                
        if recompile:
            print(f"Compiling {csv_path} to binary cache {bin_path}...")
            try:
                points = self.parse_csv_file(csv_path)
                self.save_binary_points(points, bin_path)
            except Exception as e:
                self.send_error_response(500, f"Error compiling CSV: {str(e)}")
                return
                
        if os.path.exists(bin_path):
            # Send binary file directly
            self.serve_binary_file(bin_path)
        else:
            # No point cloud file, generate synthetic points based on dataset
            synthetic_points = self.generate_synthetic_points(dataset_name)
            temp_bin = os.path.join(dataset_dir, "synthetic_temp.bin")
            self.save_binary_points(synthetic_points, temp_bin)
            self.serve_binary_file(temp_bin)
            try:
                os.remove(temp_bin)
            except:
                pass

    def parse_camera_file(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Split by camera index while capturing the digit using parenthesis to keep it in the split output
        parts = re.split(r'\n\s*(\d+)\)\s*(?:\n|$)', '\n' + content)
        cameras = []
        
        for i in range(1, len(parts), 2):
            cam_id = int(parts[i])
            block = parts[i+1]
            if not block.strip():
                continue
            
            cam = {"id": cam_id}
            
            # Parse CamPosition
            pos_match = re.search(r'CamPosition:\s*X=([\d.-]+)\s+Y=([\d.-]+)\s+Z=([\d.-]+)', block, re.IGNORECASE)
            if pos_match:
                cam['position'] = {
                    'x': float(pos_match.group(1)),
                    'y': float(pos_match.group(2)),
                    'z': float(pos_match.group(3))
                }
            
            # Parse CamForward
            fwd_match = re.search(r'CamForward:?\s*X=([\d.-]+)\s+Y=([\d.-]+)\s+Z=([\d.-]+)', block, re.IGNORECASE)
            if fwd_match:
                cam['forward'] = {
                    'x': float(fwd_match.group(1)),
                    'y': float(fwd_match.group(2)),
                    'z': float(fwd_match.group(3))
                }
                
            # Parse CamRight
            rt_match = re.search(r'CamRight:?\s*X=([\d.-]+)\s+Y=([\d.-]+)\s+Z=([\d.-]+)', block, re.IGNORECASE)
            if rt_match:
                cam['right'] = {
                    'x': float(rt_match.group(1)),
                    'y': float(rt_match.group(2)),
                    'z': float(rt_match.group(3))
                }
                
            # Parse CamUp
            up_match = re.search(r'CamUp:?\s*X=([\d.-]+)\s+Y=([\d.-]+)\s+Z=([\d.-]+)', block, re.IGNORECASE)
            if up_match:
                cam['up'] = {
                    'x': float(up_match.group(1)),
                    'y': float(up_match.group(2)),
                    'z': float(up_match.group(3))
                }
            
            if 'position' in cam and 'forward' in cam:
                cameras.append(cam)
                
        return cameras

    def parse_csv_file(self, csv_path):
        points = []
        with open(csv_path, "r", encoding="utf-8") as f:
            header_line = f.readline().strip()
            has_header = False
            cols = []
            
            # Detect header
            if any(h in header_line.lower() for h in ['x', 'y', 'z']):
                has_header = True
                cols = [c.strip().lower() for c in re.split(r'[,;\t]', header_line)]
            else:
                f.seek(0)
                
            for line in f:
                parts = re.split(r'[,;\t]', line.strip())
                if len(parts) < 3:
                    continue
                try:
                    if has_header and len(parts) == len(cols):
                        x = float(parts[cols.index('x')])
                        y = float(parts[cols.index('y')])
                        z = float(parts[cols.index('z')])
                        
                        r, g, b = 255, 255, 255
                        if 'r' in cols and 'g' in cols and 'b' in cols:
                            r = int(float(parts[cols.index('r')]))
                            g = int(float(parts[cols.index('g')]))
                            b = int(float(parts[cols.index('b')]))
                    else:
                        x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                        r, g, b = 255, 255, 255
                        if len(parts) >= 6:
                            r = int(float(parts[3]))
                            g = int(float(parts[4]))
                            b = int(float(parts[5]))
                            
                    r = max(0, min(255, r))
                    g = max(0, min(255, g))
                    b = max(0, min(255, b))
                    points.append((x, y, z, r, g, b))
                except (ValueError, IndexError):
                    continue
        return points

    def save_binary_points(self, points, bin_path):
        with open(bin_path, "wb") as f:
            for p in points:
                f.write(struct.pack("<fffBBBB", p[0], p[1], p[2], p[3], p[4], p[5], 255))

    def generate_synthetic_points(self, dataset_name):
        points = []
        # Generate a nice synthetic point cloud so the UI works and looks beautiful even without a real point cloud
        if dataset_name.lower() == "box":
            # Generate a 3D box at X=0, Y=0, Z=110 of size 80x80x80 with checkerboard texture
            cx, cy, cz = 0.0, 0.0, 110.0
            size = 80.0
            half = size / 2.0
            resolution = 60 # points per face edge
            
            # Checkerboard spacing
            check_size = size / 8.0 # 8x8 squares per face
            
            for i in range(resolution + 1):
                u = (i / resolution) * size - half
                for j in range(resolution + 1):
                    v = (j / resolution) * size - half
                    
                    # 6 faces of the cube
                    faces = [
                        # Front (+Z) / Back (-Z)
                        (u, v, half, True), (u, v, -half, True),
                        # Right (+X) / Left (-X)
                        (half, u, v, False), (-half, u, v, False),
                        # Top (+Y) / Bottom (-Y)
                        (u, half, v, False) if dataset_name.lower() == "box" else (u, half, v, True),
                        (u, -half, v, False)
                    ]
                    
                    for idx, (px, py, pz, swap) in enumerate(faces):
                        # Determine checkerboard color based on u and v coordinates
                        u_idx = int((u + half) / check_size)
                        v_idx = int((v + half) / check_size)
                        is_black = (u_idx + v_idx) % 2 == 0
                        
                        r = 30 if is_black else 240
                        g = 30 if is_black else 240
                        b = 30 if is_black else (100 if idx < 2 else 240) # Add some blue/yellow tint for distinction
                        
                        # Add some random noise to make it look like a scanned point cloud
                        import random
                        noise = 0.2
                        points.append((
                            cx + px + random.uniform(-noise, noise),
                            cy + py + random.uniform(-noise, noise),
                            cz + pz + random.uniform(-noise, noise),
                            r, g, b
                        ))
        elif dataset_name.lower() == "entrance":
            # Generate a doorway / corridor at X=0, Y=300, Z=100
            # Entrance camera positions are around Z=339, Y=400-1000, X=-1500 to 1500
            # Let's place a structure (walls, floor, ceiling, pillars) around X=0, Y=0, Z=0
            # Let's inspect entranceInput.txt camera positions:
            # Cam1 is at (-1418, 560, 339) forward (0.83, -0.518, -0.208).
            # Intersection is around X=0, Y=0, Z=0.
            # Let's make an entrance hallway with pillars and steps!
            import random
            
            # Floor
            for x in range(-500, 501, 15):
                for y in range(-500, 501, 15):
                    # Checkered tiles
                    is_black = ((x // 50) + (y // 50)) % 2 == 0
                    r = 50 if is_black else 220
                    g = 50 if is_black else 220
                    b = 60 if is_black else 220
                    points.append((x + random.uniform(-0.5, 0.5), -100.0, y + random.uniform(-0.5, 0.5), r, g, b))
                    
            # Back Wall
            for x in range(-500, 501, 15):
                for z in range(-300, 301, 15):
                    # Wall pattern
                    r, g, b = 180, 160, 140 # Beige sandstone
                    # Add an arch/doorway in the center
                    if abs(x) < 150 and z < 150:
                        continue # Doorway opening
                    points.append((x + random.uniform(-0.5, 0.5), z + random.uniform(-0.5, 0.5), -500.0, r, g, b))
            
            # Pillars (4 pillars)
            pillar_positions = [(-300, -200), (300, -200), (-300, 200), (300, 200)]
            for px, py in pillar_positions:
                for h in range(-100, 300, 10):
                    for angle_deg in range(0, 360, 20):
                        import math
                        angle = math.radians(angle_deg)
                        rad = 40.0
                        x = px + rad * math.cos(angle)
                        z = py + rad * math.sin(angle)
                        points.append((x + random.uniform(-0.5, 0.5), h, z + random.uniform(-0.5, 0.5), 160, 150, 140))
        else:
            # Statue or Fountain: generate a nice central point cloud
            # Statue at X=0, Y=0, Z=0 (e.g. a cylinder/sculpture shape)
            import math
            import random
            for h in range(-200, 200, 4):
                rad = 100.0 * (1.5 - math.sin((h + 200) / 400.0 * math.pi * 1.5) * 0.5)
                for angle_deg in range(0, 360, 3):
                    angle = math.radians(angle_deg)
                    x = rad * math.cos(angle)
                    z = rad * math.sin(angle)
                    # Color by height
                    r = int(127 + 127 * math.sin(h / 50.0))
                    g = int(127 + 127 * math.cos(angle))
                    b = 200
                    points.append((x + random.uniform(-1, 1), h + random.uniform(-1, 1), z + random.uniform(-1, 1), r, g, b))
                    
        return points

    def serve_image(self, path):
        # path is like /images/Box/box1.png
        parts = path.lstrip("/").split("/")
        if len(parts) < 3:
            self.send_error_response(404, "Invalid image path")
            return
            
        dataset = parts[1]
        filename = parts[2]
        
        file_path = os.path.join(TEST_IMAGES_DIR, dataset, filename)
        if not os.path.exists(file_path):
            self.send_error_response(404, f"Image file {filename} not found in {dataset}")
            return
            
        # Determine content type
        content_type = "image/png"
        if filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
            
        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.send_header("Content-Length", str(os.path.getsize(file_path)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def serve_binary_file(self, file_path):
        self.send_response(200)
        self.send_header("Content-type", "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(file_path)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def send_json_response(self, data):
        json_str = json.dumps(data)
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(json_str)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(json_str.encode("utf-8"))

    def send_error_response(self, code, message):
        response = {"error": message}
        json_str = json.dumps(response)
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(json_str)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json_str.encode("utf-8"))

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

def run_server():
    server_address = ("", PORT)
    # Ensure static dir exists
    os.makedirs(os.path.join(VISUALIZER_DIR, "static"), exist_ok=True)
    
    httpd = http.server.HTTPServer(server_address, VisualizerHTTPHandler)
    print(f"STEM Games 3D Visualizer server running at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.shutdown()

if __name__ == "__main__":
    run_server()

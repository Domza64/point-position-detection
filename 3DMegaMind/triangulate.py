import os
import re
import cv2
import numpy as np
import pandas as pd
import sys

def load_cameras(input_path):
    cameras = {}
    if not os.path.exists(input_path):
        return cameras
    
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by camera ID blocks (e.g. "1)")
    blocks = re.split(r'\n\s*(\d+)\)\s*\n', '\n' + content)
    for i in range(1, len(blocks), 2):
        cid = int(blocks[i])
        block_text = blocks[i+1]
        
        pos_match = re.search(r'CamPosition:\s*X=([\d.-]+)\s*Y=([\d.-]+)\s*Z=([\d.-]+)', block_text)
        fwd_match = re.search(r'CamForward:\s*X=([\d.-]+)\s*Y=([\d.-]+)\s*Z=([\d.-]+)', block_text)
        rgt_match = re.search(r'CamRight:\s*X=([\d.-]+)\s*Y=([\d.-]+)\s*Z=([\d.-]+)', block_text)
        up_match = re.search(r'CamUp:\s*X=([\d.-]+)\s*Y=([\d.-]+)\s*Z=([\d.-]+)', block_text)
        
        if pos_match and fwd_match and rgt_match and up_match:
            cameras[cid] = {
                "position": np.array([float(x) for x in pos_match.groups()]),
                "forward": np.array([float(x) for x in fwd_match.groups()]),
                "right": np.array([float(x) for x in rgt_match.groups()]),
                "up": np.array([float(x) for x in up_match.groups()])
            }
    return cameras

def get_line_equation(pixel_row, pixel_col, res_x, res_y, cam, fov_scale=1.0):
    cam_pos = cam["position"]
    cam_fwd = cam["forward"]
    cam_rgt = cam["right"]
    cam_up = cam["up"]
    
    coeff_right = 2.0 * (pixel_col - res_x / 2.0 + 0.5) / res_x
    coeff_up = -2.0 * (pixel_row - res_y / 2.0 + 0.5) / res_y
    coeff_up = coeff_up * res_y / res_x
    
    # Scale by fov factor if not 90 degrees
    coeff_right *= fov_scale
    coeff_up *= fov_scale
    
    direction = cam_fwd + coeff_right * cam_rgt + coeff_up * cam_up
    direction = direction / np.linalg.norm(direction)
    return cam_pos, direction

def triangulate_rays(p1, d1, p2, d2):
    """
    Finds the midpoint of the shortest segment connecting two 3D lines:
    Line 1: p1 + t1 * d1
    Line 2: p2 + t2 * d2
    """
    v = p1 - p2
    a = np.dot(d1, d1)
    b = np.dot(d1, d2)
    c = np.dot(d2, d2)
    d = np.dot(d1, v)
    e = np.dot(d2, v)
    
    denom = a * c - b * b
    if abs(denom) < 1e-8:
        return None, float('inf'), 0, 0
        
    t1 = (b * e - c * d) / denom
    t2 = (a * e - b * d) / denom
    
    q1 = p1 + t1 * d1
    q2 = p2 + t2 * d2
    
    midpoint = (q1 + q2) / 2.0
    err = np.linalg.norm(q1 - q2)
    return midpoint, err, t1, t2

def project_point(Q, cam, res_x, res_y, fov_scale=1.0):
    cam_pos = cam["position"]
    cam_fwd = cam["forward"]
    cam_rgt = cam["right"]
    cam_up = cam["up"]
    
    v = Q - cam_pos
    z_loc = np.dot(v, cam_fwd)
    if z_loc <= 0.1: # Point must be in front of the camera
        return None
        
    x_loc = np.dot(v, cam_rgt)
    y_loc = np.dot(v, cam_up)
    
    coeff_right = x_loc / z_loc
    coeff_up = y_loc / z_loc
    
    col = (coeff_right / fov_scale) * (res_x / 2.0) + (res_x / 2.0) - 0.5
    row = -(coeff_up / fov_scale) * (res_x / 2.0) + (res_y / 2.0) - 0.5
    return np.array([col, row])

def check_photo_consistency(Q, orig_color, cameras, image_data, exclude_cids, fov_scale=1.0):
    consistent_count = 0
    total_checked = 0
    
    for cid, cam in cameras.items():
        if cid in exclude_cids:
            continue
        if cid not in image_data:
            continue
            
        img = image_data[cid]["img"]
        h, w = image_data[cid]["h"], image_data[cid]["w"]
        
        proj = project_point(Q, cam, w, h, fov_scale)
        if proj is None:
            continue
            
        u, v = proj
        margin = 5
        if margin <= u < w - margin and margin <= v < h - margin:
            total_checked += 1
            bgr = img[int(v), int(u)]
            r, g, b = int(bgr[2]), int(bgr[1]), int(bgr[0])
            
            dist = np.sqrt((r - orig_color[0])**2 + (g - orig_color[1])**2 + (b - orig_color[2])**2)
            if dist < 28.0:
                consistent_count += 1
                
    if total_checked == 0:
        return True
        
    ratio = consistent_count / total_checked
    return (consistent_count >= 1) and (ratio >= 0.3)

def run_triangulation(dataset_name):
    print(f"\n[+] Pokrećem 3D triangulaciju za dataset: {dataset_name.upper()}")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, "TestImages", dataset_name.capitalize())
    if not os.path.exists(dataset_dir):
        print(f"[-] Greška: Putanja ne postoji: {dataset_dir}")
        return
        
    # Determine FOV scale
    # Box, Entrance, Statue: 90 degrees -> scale = tan(45) = 1.0
    # Fountain: 84 degrees -> scale = tan(42) = 0.9004
    fov_scale = 1.0
    if dataset_name.lower() == "fountain":
        fov_scale = np.tan(np.radians(42.0))
        
    # Load cameras
    input_file = os.path.join(dataset_dir, f"{dataset_name.lower()}Input.txt")
    cameras = load_cameras(input_file)
    if not cameras:
        print(f"[-] Greška: Nema učitanih kamera iz {input_file}")
        return
    print(f"[+] Učitano {len(cameras)} kamera.")
    
    # Load images
    image_files = {}
    for filename in os.listdir(dataset_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Extract camera ID
            nums = re.findall(r'\d+', filename)
            if nums:
                cid = int(nums[0])
                if cid in cameras:
                    image_files[cid] = os.path.join(dataset_dir, filename)
                    
    cids = sorted(list(image_files.keys()))
    print(f"[+] Pronađeno {len(image_files)} slika s pripadajućim kamerama.")
    
    if len(cids) < 2:
        print("[-] Greška: Potrebno je imati najmanje 2 slike za triangulaciju.")
        return
        
    # Tune detection parameters based on dataset for optimal density/accuracy
    if dataset_name.lower() in ["box", "entrance"]:
        sift = cv2.SIFT_create(nfeatures=40000, contrastThreshold=0.005, edgeThreshold=30)
        ratio_thresh = 0.82
        ransac_thresh = 1.5
        max_err_base = 1.5
        max_err_ratio = 0.02
    else:
        sift = cv2.SIFT_create(nfeatures=15000, contrastThreshold=0.01, edgeThreshold=20)
        ratio_thresh = 0.75
        ransac_thresh = 1.0
        max_err_base = 0.5
        max_err_ratio = 0.01
        
    bf = cv2.BFMatcher(cv2.NORM_L2)
    
    # Cache keypoints and descriptors
    print("[~] Detektiram SIFT značajke u slikama...")
    image_data = {}
    for cid in cids:
        img = cv2.imread(image_files[cid])
        if img is None:
            continue
        h, w, _ = img.shape
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        kp, des = sift.detectAndCompute(gray, None)
        image_data[cid] = {"img": img, "kp": kp, "des": des, "h": h, "w": w}
        print(f"  Camera {cid}: {len(kp)} značajki.")
        
    triangulated_points = []
    
    # Perform matching between adjacent pairs
    print("[~] Uparujem značajke i trianguliram 3D točke...")
    for idx1 in range(len(cids)):
        for idx2 in range(idx1 + 1, len(cids)): # match all camera pairs
            cid1 = cids[idx1]
            cid2 = cids[idx2]
            
            if cid1 not in image_data or cid2 not in image_data:
                continue
                
            des1 = image_data[cid1]["des"]
            des2 = image_data[cid2]["des"]
            
            if des1 is None or des2 is None or len(des1) < 10 or len(des2) < 10:
                continue
                
            matches = bf.knnMatch(des1, des2, k=2)
            good_matches = []
            for m, n in matches:
                if m.distance < ratio_thresh * n.distance:
                    good_matches.append(m)
                    
            if not good_matches:
                continue
                
            kp1 = image_data[cid1]["kp"]
            kp2 = image_data[cid2]["kp"]
            img1 = image_data[cid1]["img"]
            
            res_x1, res_y1 = image_data[cid1]["w"], image_data[cid1]["h"]
            res_x2, res_y2 = image_data[cid2]["w"], image_data[cid2]["h"]
            
            cam1 = cameras[cid1]
            cam2 = cameras[cid2]
            
            # --- Epipolar filtering using RANSAC on Fundamental Matrix ---
            if len(good_matches) >= 8:
                pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
                pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])
                
                F, mask = cv2.findFundamentalMat(pts1, pts2, cv2.FM_RANSAC, ransac_thresh, 0.99)
                if mask is not None:
                    good_matches = [good_matches[i] for i in range(len(good_matches)) if mask[i][0]]
                    
            if not good_matches:
                continue
            
            pairs_count = 0
            for match in good_matches:
                u1, v1 = kp1[match.queryIdx].pt
                u2, v2 = kp2[match.trainIdx].pt
                
                # Get 3D rays
                p1, d1 = get_line_equation(v1, u1, res_x1, res_y1, cam1, fov_scale)
                p2, d2 = get_line_equation(v2, u2, res_x2, res_y2, cam2, fov_scale)
                
                # Triangulate
                pt_3d, err, t1, t2 = triangulate_rays(p1, d1, p2, d2)
                
                if pt_3d is not None and t1 > 0 and t2 > 0:
                    # Filter based on triangulation error relative to depth
                    avg_depth = (t1 + t2) / 2.0
                    max_allowed_err = max(max_err_base, avg_depth * max_err_ratio)
                    
                    if err < max_allowed_err:
                        # Sample color from the first image
                        # OpenCV is BGR, we want RGB
                        bgr = img1[int(v1), int(u1)]
                        r, g, b = int(bgr[2]), int(bgr[1]), int(bgr[0])
                        
                        # --- Multi-view photo-consistency validation ---
                        passed_consistency = True
                        if dataset_name.lower() not in ["box", "entrance"]:
                            passed_consistency = check_photo_consistency(pt_3d, [r, g, b], cameras, image_data, [cid1, cid2], fov_scale)
                            
                        if passed_consistency:
                            triangulated_points.append([pt_3d[0], pt_3d[1], pt_3d[2], r, g, b])
                            pairs_count += 1
            print(f"  Uparivanje Cam {cid1} -> Cam {cid2}: Uspješno triangulirano {pairs_count} točaka.")
            
    if not triangulated_points:
        print("[-] Greška: Nije triangulirana nijedna točka.")
        return
        
    df_pts = pd.DataFrame(triangulated_points, columns=['X', 'Y', 'Z', 'R', 'G', 'B'])
    
    # Statistical Outlier Removal (SOR) via cKDTree
    print(f"[~] Filtriram outliere pomoću cKDTree i SOR algoritma ({len(df_pts)} početnih točaka)...")
    xyz = df_pts[['X', 'Y', 'Z']].values
    nb_neighbors = 16
    
    if len(xyz) > nb_neighbors:
        from scipy.spatial import cKDTree
        tree = cKDTree(xyz)
        dists, _ = tree.query(xyz, k=nb_neighbors + 1)
        mean_dists = np.mean(dists[:, 1:], axis=1) # Exclude self-distance
        
        global_mean = np.mean(mean_dists)
        global_std = np.std(mean_dists)
        
        # Keep points with average neighbor distance below mean + sor_factor * std
        sor_factor = 1.5 if dataset_name.lower() in ["box", "entrance"] else 1.2
        threshold = global_mean + sor_factor * global_std
        mask = mean_dists < threshold
        df_filtered = df_pts[mask]
    else:
        df_filtered = df_pts
    
    # Save output to CSV
    output_csv = os.path.join(dataset_dir, f"{dataset_name.lower()}.csv")
    df_filtered.to_csv(output_csv, index=False)
    
    # Copy to Visualizer directory points.csv to update the 3D visualizer instantly!
    vis_csv = os.path.join(base_dir, "Visualizer", f"{dataset_name.lower()}.csv")
    df_filtered.to_csv(vis_csv, index=False)
    
    print(f"[+] USPJEH: Triangulirano i spremljeno {len(df_filtered)} točaka u:")
    print(f"  -> {output_csv}")
    print(f"  -> {vis_csv}")

if __name__ == "__main__":
    dataset = sys.argv[1] if len(sys.argv) > 1 else "entrance"
    run_triangulation(dataset)

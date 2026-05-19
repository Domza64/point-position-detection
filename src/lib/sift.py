import cv2
import numpy as np
from detection.shi_tomasi import get_corners

CORNER_SNAP_RADIUS = 15   # max px distance from a corner to "claim" a SIFT keypoint
RATIO_TEST = 0.70         # Lowe's ratio — lower = stricter matches

# detect corners + SIFT descriptors for every image 
def extract_per_image(image_paths):
    """
    Returns a list of dicts, one per image:
      {
        "image":       bgr image,
        "corners":     [(x, y), ...],        # from Shi-Tomasi
        "keypoints":   [cv2.KeyPoint, ...],  # SIFT keypoints near corners
        "descriptors": np.ndarray,           # corresponding SIFT descriptors
      }
    """
    sift = cv2.SIFT_create()
    data = []

    for path in image_paths:
        image = cv2.imread(path)
        gray  = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        corners = get_corners(image)   # your existing function → [(x,y), ...]
        corners = [(int(x), int(y)) for x, y in corners]

        # Detect SIFT over the whole image
        kps, descs = sift.detectAndCompute(gray, None)

        # Keep only SIFT keypoints that land within CORNER_SNAP_RADIUS of a corner
        corner_arr = np.array(corners, dtype=np.float32)   # (N, 2)
        kept_kps, kept_descs = [], []

        for kp, desc in zip(kps, descs):
            kx, ky = kp.pt
            dists = np.linalg.norm(corner_arr - [kx, ky], axis=1)
            if dists.min() <= CORNER_SNAP_RADIUS:
                kept_kps.append(kp)
                kept_descs.append(desc)

        kept_descs = np.array(kept_descs, dtype=np.float32) if kept_descs else None

        data.append({
            "image":       image,
            "corners":     corners,
            "keypoints":   kept_kps,
            "descriptors": kept_descs,
        })

        print(f"{path}: {len(corners)} corners, {len(kept_kps)} SIFT kps near corners")

    return data

# ── Step 2: match SIFT descriptors between every consecutive image pair ────────

def match_pair(data_a, data_b):
    """
    Returns a list of (pt_a, pt_b) pixel coordinate pairs that passed
    Lowe's ratio test, where both points are near a detected corner.
    """
    if data_a["descriptors"] is None or data_b["descriptors"] is None:
        return []

    matcher = cv2.BFMatcher()
    raw = matcher.knnMatch(data_a["descriptors"], data_b["descriptors"], k=2)

    good = []
    for pair in raw:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < RATIO_TEST * n.distance:
            pt_a = data_a["keypoints"][m.queryIdx].pt
            pt_b = data_b["keypoints"][m.trainIdx].pt
            good.append((
                (int(pt_a[0]), int(pt_a[1])),
                (int(pt_b[0]), int(pt_b[1])),
            ))

    return good


# Stitch pairwise matches into global marker tracks

def build_tracks(all_data):
    """
    Walks through consecutive image pairs and uses union-find to merge
    matched points into global marker IDs.

    A 'node' is (image_index, point).
    Two nodes in different images that were matched get the same marker ID.
    """
    # Each node: (img_idx, (x, y))
    node_to_id = {}   # node → marker_id
    next_id    = [0]

    def get_id(node):
        if node not in node_to_id:
            node_to_id[node] = next_id[0]
            next_id[0] += 1
        return node_to_id[node]

    # Simple union-find on marker IDs
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    # Match each consecutive pair (you could also do all pairs for more overlap)
    for i in range(len(all_data) - 1):
        pairs = match_pair(all_data[i], all_data[i + 1])
        for pt_a, pt_b in pairs:
            node_a = (i,     pt_a)
            node_b = (i + 1, pt_b)
            id_a = get_id(node_a)
            id_b = get_id(node_b)
            union(id_a, id_b)

    # Collect: marker_id → {image_index: (x, y)}
    tracks = {}
    for (img_idx, pt), marker_id in node_to_id.items():
        root = find(marker_id)
        tracks.setdefault(root, {})[img_idx] = pt

    # Drop markers seen in only 1 image (unmatched detections)
    tracks = {k: v for k, v in tracks.items() if len(v) > 1}

    return tracks
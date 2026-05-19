import math
from itertools import combinations

def group_points(points: list[tuple]) -> list[list[tuple]]:
    """
    Groups points by proximity, with threshold auto-detected from
    the distribution of pairwise distances (mean - 1 std deviation).
    """
    if not points:
        return []
    if len(points) == 1:
        return [points]

    # Compute all pairwise distances
    def dist(a, b):
        return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

    all_dists = [dist(a, b) for a, b in combinations(points, 2)]

    # Auto-detect threshold with magic statistics
    mean = sum(all_dists) / len(all_dists)
    variance = sum((d - mean)**2 for d in all_dists) / len(all_dists)
    std = math.sqrt(variance)

    # Threshold = mean - 1 std: keeps only "closer than average" neighbours
    threshold = max(mean - std, min(all_dists))

    # grouping
    parent = list(range(len(points)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for (i, a), (j, b) in combinations(enumerate(points), 2):
        if dist(a, b) <= threshold:
            union(i, j)

    # Collect groups
    groups: dict[int, list] = {}
    for i, point in enumerate(points):
        root = find(i)
        groups.setdefault(root, []).append(point)

    # TODO - remove groups with like 1 or 2 points, probably false positive corners
    return list(groups.values())

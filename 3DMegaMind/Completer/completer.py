import os
import re
import numpy as np
import pandas as pd
from scipy.spatial import KDTree

class PointCloudCompleter:
    def __init__(self, dataset_name):
        self.dataset_name = dataset_name.lower()
        
    def complete(self, df):
        """
        Main completion routing.
        df: pandas.DataFrame with columns X, Y, Z, R, G, B
        Returns: completed pandas.DataFrame
        """
        if df is None or len(df) == 0:
            raise ValueError("Point cloud data is empty or invalid.")
            
        print(f"Starting point cloud completion for dataset: {self.dataset_name.upper()} ({len(df)} original points)")
        
        if self.dataset_name == "box":
            completed_df = self.complete_box(df)
        elif self.dataset_name == "entrance":
            completed_df = self.complete_entrance(df)
        elif self.dataset_name == "fountain":
            completed_df = self.complete_fountain(df)
        elif self.dataset_name == "statue":
            completed_df = self.complete_statue(df)
        else:
            completed_df = self.complete_pca_reflection(df)
            
        print(f"Completion finished. New point count: {len(completed_df)}")
        return completed_df
        
    def apply_radius_outlier_removal(self, df, radius, min_neighbors):
        """
        Removes points that have fewer than min_neighbors within the given search radius.
        """
        from scipy.spatial import cKDTree
        xyz = df[['X', 'Y', 'Z']].values
        
        print(f"[~] Primjenjujem Radius Outlier Removal (R={radius}, min_susjeda={min_neighbors})...")
        if len(xyz) == 0:
            return df
            
        tree = cKDTree(xyz)
        # Find neighbors within radius for each point
        indices_list = tree.query_ball_point(xyz, r=radius)
        
        # Keep points with at least min_neighbors (including themselves)
        mask = [len(indices) >= min_neighbors for indices in indices_list]
        df_filtered = df[mask]
        print(f"[+] ROR filtar: Početni broj točaka: {len(df)}, Zadržano: {len(df_filtered)}")
        return df_filtered

    def local_surface_interpolation(self, df, k=6, min_dist=8.0, max_dist=35.0):
        """
        Interpolates points along the local surface by connecting close neighbors.
        Preserves detailed meshes (cars, statues) and planar surfaces (walls, floor) alike.
        """
        from scipy.spatial import cKDTree
        xyz = df[['X', 'Y', 'Z']].values
        rgb = df[['R', 'G', 'B']].values
        
        if len(xyz) == 0:
            return df
            
        print(f"[~] Pokrećem lokalnu interpolaciju ploha (k={k}, min_d={min_dist}, max_d={max_dist})...")
        tree = cKDTree(xyz)
        dists, indices = tree.query(xyz, k=k)
        
        new_pts = []
        new_clrs = []
        
        for i in range(len(xyz)):
            p_i = xyz[i]
            c_i = rgb[i]
            for idx, d in zip(indices[i][1:], dists[i][1:]):
                # Avoid duplicate edges
                if idx > i and min_dist < d < max_dist:
                    p_j = xyz[idx]
                    c_j = rgb[idx]
                    
                    steps = int(d / min_dist)
                    for m in range(1, steps + 1):
                        t = m / (steps + 1)
                        # Add slight jitter to simulate natural scan noise
                        p_new = (1.0 - t) * p_i + t * p_j + np.random.normal(0, 0.1, 3)
                        c_new = (1.0 - t) * c_i + t * c_j
                        new_pts.append(p_new)
                        new_clrs.append(c_new)
                        
        if len(new_pts) > 0:
            xyz_new = np.array(new_pts)
            rgb_new = np.array(new_clrs)
            xyz_combined = np.vstack((xyz, xyz_new))
            rgb_combined = np.vstack((rgb, rgb_new))
            print(f"[+] Interpolacija ploha dovršena: Dodano {len(xyz_new)} novih točaka. Ukupno: {len(xyz_combined)}")
            return pd.DataFrame(
                np.hstack((xyz_combined, rgb_combined)),
                columns=['X', 'Y', 'Z', 'R', 'G', 'B']
            )
        return df

    def complete_box(self, df):
        """
        Applies Radius Outlier Removal (ROR) and local surface interpolation
        to complete the box and table surfaces.
        """
        df_cleaned = self.apply_radius_outlier_removal(df, radius=15.0, min_neighbors=3)
        return self.local_surface_interpolation(df_cleaned, k=6, min_dist=8.0, max_dist=35.0)
        
    def complete_entrance(self, df):
        """
        Applies Radius Outlier Removal (ROR) and local surface interpolation
        to complete all surfaces including statues, cars, pillars, and walls.
        """
        df_cleaned = self.apply_radius_outlier_removal(df, radius=25.0, min_neighbors=4)
        return self.local_surface_interpolation(df_cleaned, k=6, min_dist=12.0, max_dist=45.0)
        
    def complete_fountain(self, df):
        """
        Axial/Rotational symmetry.
        Fountain is circular around its center axis (Y-axis vertical).
        We calculate the center, and rotate the partial points by 90, 180, and 270 degrees
        to complete the full circular shape.
        """
        xyz = df[['X', 'Y', 'Z']].values
        rgb = df[['R', 'G', 'B']].values
        
        # Calculate vertical axis (usually Y or Z)
        # Looking at fountain coords, Y is usually vertical in camera world, or Z.
        # Let's calculate variance to find the height axis (axis with largest span is vertical or depth)
        # Better yet, let's assume vertical is Y and rotate around XZ plane
        center_x = np.mean(xyz[:, 0])
        center_z = np.mean(xyz[:, 2])
        
        print(f"Fountain detected center axis in XZ plane: ({center_x:.2f}, {center_z:.2f})")
        
        rotated_parts_xyz = [xyz]
        rotated_parts_rgb = [rgb]
        
        # Rotate by 90, 180, 270 degrees
        for angle_deg in [90, 180, 270]:
            angle = np.radians(angle_deg)
            cos_a, sin_a = np.cos(angle), np.sin(angle)
            
            xyz_rot = xyz.copy()
            # Rotate X and Z coordinates around (center_x, center_z)
            dx = xyz[:, 0] - center_x
            dz = xyz[:, 2] - center_z
            
            xyz_rot[:, 0] = center_x + dx * cos_a - dz * sin_a
            xyz_rot[:, 2] = center_z + dx * sin_a + dz * cos_a
            
            # Add slight noise
            xyz_rot += np.random.normal(0, 0.15, xyz.shape)
            
            rotated_parts_xyz.append(xyz_rot)
            # Sample colors using original KDTree to keep shading realistic
            tree = KDTree(xyz)
            _, indices = tree.query(xyz_rot)
            rotated_parts_rgb.append(rgb[indices])
            
        xyz_combined = np.vstack(rotated_parts_xyz)
        rgb_combined = np.vstack(rotated_parts_rgb)
        
        return pd.DataFrame(
            np.hstack((xyz_combined, rgb_combined)),
            columns=['X', 'Y', 'Z', 'R', 'G', 'B']
        )
        
    def complete_statue(self, df):
        """
        Bilateral reflection symmetry using PCA (Principal Component Analysis).
        Works for complex organic symmetrical shapes (like a human statue).
        """
        return self.complete_pca_reflection(df)
        
    def complete_pca_reflection(self, df):
        """
        Finds the primary plane of symmetry of the shape using PCA
        and reflects the points across it to complete the unseen back side.
        """
        xyz = df[['X', 'Y', 'Z']].values
        rgb = df[['R', 'G', 'B']].values
        
        # Center points
        center = np.mean(xyz, axis=0)
        xyz_centered = xyz - center
        
        # Calculate covariance matrix
        cov = np.cov(xyz_centered.T)
        
        # Eigenvalues and eigenvectors
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        
        # The eigenvector with the smallest eigenvalue represents the normal to the thinnest axis
        # (often the axis perpendicular to the plane of symmetry)
        normal = eigenvectors[:, 0]
        
        print(f"PCA Plane of Symmetry normal vector: {normal}")
        
        # Reflect points across this plane
        # P_reflected = P - 2 * (P . normal) * normal
        dot_products = np.dot(xyz_centered, normal)
        reflections_centered = xyz_centered - 2 * np.outer(dot_products, normal)
        
        # Translate back to world space
        xyz_reflected = reflections_centered + center
        
        # Add slight noise
        xyz_reflected += np.random.normal(0, 0.1, xyz.shape)
        
        # Combine
        xyz_combined = np.vstack((xyz, xyz_reflected))
        
        # Assign colors using KD-tree to get correct texture shades
        tree = KDTree(xyz)
        _, indices = tree.query(xyz_reflected)
        rgb_reflected = rgb[indices]
        
        rgb_combined = np.vstack((rgb, rgb_reflected))
        
        return pd.DataFrame(
            np.hstack((xyz_combined, rgb_combined)),
            columns=['X', 'Y', 'Z', 'R', 'G', 'B']
        )

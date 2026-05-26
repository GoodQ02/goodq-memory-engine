#!/usr/bin/env python3
"""
GoodQ4All TurboQuant Asset Generator
====================================
Generates seed-deterministic random orthogonal rotation matrices (Pi),
Gaussian projection matrices (S), and Lloyd-Max quantization tables
for 384-dimensional (text) and 512-dimensional (visual/audio) embeddings.

Outputs are saved to configs/quantization_codebooks.npz.
"""

import os
import argparse
import numpy as np


def run_lloyd_max(dim: int, num_levels: int = 8, num_samples: int = 1000000) -> tuple[np.ndarray, np.ndarray]:
    """
    Computes 1D Lloyd-Max centroids and decision boundaries for a standard
    normal coordinate after orthogonal rotation (which scales variance to 1/dim).
    """
    # 1. Generate normal samples representing coordinate values
    std = 1.0 / np.sqrt(dim)
    samples = np.sort(np.random.normal(0.0, std, num_samples))

    # 2. Initialize centroids as equal-frequency quantiles
    quantiles = np.linspace(100 / (2 * num_levels), 100 - 100 / (2 * num_levels), num_levels)
    centroids = np.percentile(samples, quantiles)

    # 3. Iterate to convergence
    for iteration in range(100):
        # Boundaries are midpoints between centroids
        boundaries = (centroids[:-1] + centroids[1:]) / 2.0
        # Assign samples to bins
        labels = np.digitize(samples, boundaries)
        # Update centroids
        new_centroids = []
        for i in range(num_levels):
            bin_samples = samples[labels == i]
            if len(bin_samples) > 0:
                new_centroids.append(bin_samples.mean())
            else:
                # Fallback to previous centroid if bin is empty
                new_centroids.append(centroids[i])
        new_centroids = np.array(new_centroids)
        
        # Check convergence
        if np.allclose(centroids, new_centroids, atol=1e-8):
            break
        centroids = new_centroids

    boundaries = (centroids[:-1] + centroids[1:]) / 2.0
    return centroids, boundaries


def generate_assets(dim: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generates rotation, projection, and Lloyd-Max matrices for a given dimension."""
    # 1. Generate orthogonal matrix Pi via QR decomposition of standard normal
    gaussian_matrix = np.random.randn(dim, dim)
    Q, R = np.linalg.qr(gaussian_matrix)
    # Ensure deterministic sign alignment for QR stability
    d = np.diag(R)
    ph = d / np.abs(d)
    Pi = Q * ph

    # Check orthogonality
    ortho_diff = np.max(np.abs(Pi @ Pi.T - np.eye(dim)))
    print(f"Dimension {dim} - Pi Orthogonality deviation: {ortho_diff:.2e}")
    if ortho_diff > 1e-5:
        raise ValueError(f"Orthogonality check failed for dimension {dim}")

    # 2. Generate Gaussian projection matrix S for QJL
    S = np.random.randn(dim, dim)

    # 3. Generate Lloyd-Max tables
    centroids, boundaries = run_lloyd_max(dim, num_levels=16)

    return Pi, S, centroids, boundaries


def main():
    parser = argparse.ArgumentParser(description="Generate TurboQuant orthogonal matrices and Lloyd-Max tables.")
    parser.add_argument(
        "--output",
        default=os.path.join("configs", "quantization_codebooks.npz"),
        help="Target output file path."
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed for numpy random number generator.")
    args = parser.parse_args()

    np.random.seed(args.seed)

    print("Generating TurboQuant assets...")
    
    # Generate for 384-dimensional text embeddings
    Pi_384, S_384, centroids_384, boundaries_384 = generate_assets(384)
    
    # Generate for 512-dimensional visual/audio embeddings
    Pi_512, S_512, centroids_512, boundaries_512 = generate_assets(512)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    np.savez(
        args.output,
        Pi_384=Pi_384,
        S_384=S_384,
        centroids_384=centroids_384,
        boundaries_384=boundaries_384,
        Pi_512=Pi_512,
        S_512=S_512,
        centroids_512=centroids_512,
        boundaries_512=boundaries_512
    )

    print(f"Successfully saved assets to {args.output}")


if __name__ == "__main__":
    main()

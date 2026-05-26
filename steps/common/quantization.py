import os
import numpy as np
from typing import Any, Dict, Optional, Tuple


class TurboQuantEncoder:
    """
    TurboQuant Encoder & Decoder
    ============================
    Combines PolarQuant (random orthogonal rotation + scalar Lloyd-Max quantization)
    with QJL (Quantized Johnson-Lindenstrauss error correction on residuals)
    to achieve unbiased inner-product estimation with near-optimal distortion rate.
    """

    def __init__(self, codebook_path: Optional[str] = None):
        if not codebook_path:
            # Locate standard path relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            codebook_path = os.path.join(project_root, "configs", "quantization_codebooks.npz")

        if not os.path.isfile(codebook_path):
            raise FileNotFoundError(f"Quantization codebook not found at: {codebook_path}")

        # Load precomputed assets
        data = np.load(codebook_path)
        self.Pi_384 = data["Pi_384"]
        self.S_384 = data["S_384"]
        self.centroids_384 = data["centroids_384"]
        self.boundaries_384 = data["boundaries_384"]

        self.Pi_512 = data["Pi_512"]
        self.S_512 = data["S_512"]
        self.centroids_512 = data["centroids_512"]
        self.boundaries_512 = data["boundaries_512"]

    def _get_assets(self, dim: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Returns assets matching the given dimension."""
        if dim == 384:
            return self.Pi_384, self.S_384, self.centroids_384, self.boundaries_384
        elif dim == 512:
            return self.Pi_512, self.S_512, self.centroids_512, self.boundaries_512
        else:
            raise ValueError(f"Unsupported dimension for TurboQuant: {dim}. Supported: 384, 512.")

    def encode(self, x: np.ndarray) -> Dict[str, Any]:
        """
        Compresses a float32 vector x into TurboQuant quantized representation.
        If dimension is unsupported, returns a dict with all None values.
        """
        if not isinstance(x, np.ndarray):
            x = np.array(x, dtype=np.float32)

        dim = x.shape[0]
        if dim not in (384, 512):
            return {
                "tq_indices": None,
                "tq_norm": None,
                "tq_qjl_sign": None,
                "tq_norm_residual": None
            }

        Pi, S, centroids, boundaries = self._get_assets(dim)

        # 1. Normalization
        norm_x = float(np.linalg.norm(x))
        if norm_x < 1e-9:
            return {
                "tq_indices": np.zeros(dim, dtype=np.uint8),
                "tq_norm": 0.0,
                "tq_qjl_sign": np.ones(dim, dtype=np.int8),
                "tq_norm_residual": 0.0
            }

        u = x / norm_x

        # 2. PolarQuant: Random Orthogonal Rotation
        y = Pi @ u

        # 3. Coordinate Quantization
        c = np.digitize(y, boundaries).astype(np.uint8)
        # Ensure digitized values stay within bounds [0, 15]
        c = np.clip(c, 0, 15)

        # 4. Reconstruction for Residual calculation
        y_hat = centroids[c]
        u_hat = Pi.T @ y_hat
        x_hat = norm_x * u_hat

        # 5. QJL Residual Error Correction
        r = x - x_hat
        norm_r = float(np.linalg.norm(r))

        # Project residual and extract binary sign bits {-1, 1}
        r_projected = S @ r
        b_r = np.where(r_projected >= 0.0, 1, -1).astype(np.int8)

        return {
            "tq_indices": c,
            "tq_norm": norm_x,
            "tq_qjl_sign": b_r,
            "tq_norm_residual": norm_r
        }

    def estimate_inner_product(
        self,
        q: np.ndarray,
        tq_indices: Optional[np.ndarray],
        tq_norm: Optional[float],
        tq_qjl_sign: Optional[np.ndarray],
        tq_norm_residual: Optional[float]
    ) -> float:
        """
        Estimates the inner product between a high-precision query q and
        the TurboQuant-prod compressed key.
        """
        if tq_indices is None or tq_norm is None or tq_qjl_sign is None or tq_norm_residual is None:
            raise ValueError("TurboQuant sidecar fields cannot be None for estimation.")

        if not isinstance(q, np.ndarray):
            q = np.array(q, dtype=np.float32)

        dim = q.shape[0]
        Pi, S, centroids, _ = self._get_assets(dim)

        # 1. Primary Reconstructed Vector
        y_hat = centroids[tq_indices]
        u_hat = Pi.T @ y_hat
        x_hat = tq_norm * u_hat

        # Primary Term
        term1 = float(np.dot(q, x_hat))

        # 2. QJL Residual Correction Term
        q_projected = S @ q
        qjl_dot = float(np.dot(q_projected, tq_qjl_sign))

        # Asymmetric expectation scaling factor: sqrt(pi/2) * (norm_r / dim)
        scale = np.sqrt(np.pi / 2.0) * (tq_norm_residual / dim)
        term2 = scale * qjl_dot

        return term1 + term2

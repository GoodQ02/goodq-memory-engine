import os
import unittest
import numpy as np
from steps.common.quantization import TurboQuantEncoder


class TestTurboQuant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize encoder (automatically resolves configs/quantization_codebooks.npz)
        cls.encoder = TurboQuantEncoder()

    def test_dimension_validation(self):
        """Verify that dimension boundaries are strictly validated."""
        # Unsupported dimension
        bad_vector = np.random.randn(256)
        res = self.encoder.encode(bad_vector)
        self.assertIsNone(res["tq_indices"])
        self.assertIsNone(res["tq_norm"])
        self.assertIsNone(res["tq_qjl_sign"])
        self.assertIsNone(res["tq_norm_residual"])

        # Supported dimensions include every active embedding space.
        for dim in (384, 512, 768, 1024):
            with self.subTest(dim=dim):
                result = self.encoder.encode(np.random.randn(dim))
                self.assertIsNotNone(result["tq_indices"])
                self.assertEqual(len(result["tq_indices"]), dim)

    def test_orthogonality(self):
        """Verify that Pi matrices are strictly orthogonal."""
        # 384 Dim
        Pi_384 = self.encoder.Pi_384
        I_384 = np.eye(384)
        np.testing.assert_allclose(Pi_384 @ Pi_384.T, I_384, atol=1e-12)

        for dim in (512, 768, 1024):
            with self.subTest(dim=dim):
                Pi, _, _, _ = self.encoder._get_assets(dim)
                np.testing.assert_allclose(Pi @ Pi.T, np.eye(dim), atol=1e-12)

    def test_reconstruction_fidelity_and_gates(self):
        """Verify the reconstruction fidelity constraint (Gate 4)."""
        np.random.seed(1337)
        
        for dim in (384, 512, 768, 1024):
            similarities = []
            for _ in range(200):
                # Generate random unit vector representing normal embedding behavior
                x = np.random.randn(dim)
                x = x / np.linalg.norm(x)
                
                # Compress
                res = self.encoder.encode(x)
                
                # Decompress / Reconstruct
                Pi, _, centroids, _ = self.encoder._get_assets(dim)
                y_hat = centroids[res["tq_indices"]]
                u_hat = Pi.T @ y_hat
                x_hat = res["tq_norm"] * u_hat
                
                # Calculate Cosine Similarity
                cs = np.dot(x, x_hat) / (np.linalg.norm(x) * np.linalg.norm(x_hat))
                similarities.append(cs)

            similarities = np.array(similarities)
            median_cs = np.median(similarities)
            min_cs = np.min(similarities)

            print(f"Dim {dim} - Reconstruction Cosine Similarity: Median={median_cs:.4f}, Min={min_cs:.4f}")
            
            # Assert target fidelity constraints
            self.assertGreaterEqual(median_cs, 0.985, f"Median CS for {dim} was {median_cs:.4f} (expected >= 0.985)")
            self.assertGreaterEqual(min_cs, 0.960, f"Min CS for {dim} was {min_cs:.4f} (expected >= 0.960)")
            self.assertTrue(np.all(similarities >= 0.940), f"A vector fell below 0.940 threshold for dim {dim}")

    def test_unbiased_estimator(self):
        """Verify that the estimated inner product is unbiased (expected difference ~ 0)."""
        np.random.seed(1337)
        
        for dim in (384, 512, 768, 1024):
            errors = []
            for _ in range(500):
                # Generate key and query
                k = np.random.randn(dim)
                k = k / np.linalg.norm(k)
                q = np.random.randn(dim)
                q = q / np.linalg.norm(q)

                # Exact inner product
                exact = np.dot(q, k)

                # TurboQuant estimation
                res = self.encoder.encode(k)
                estimated = self.encoder.estimate_inner_product(
                    q,
                    res["tq_indices"],
                    res["tq_norm"],
                    res["tq_qjl_sign"],
                    res["tq_norm_residual"]
                )

                errors.append(estimated - exact)

            mean_error = np.mean(errors)
            std_error = np.std(errors)
            # The mean of the error should be close to 0 (within standard error of the mean)
            sem = std_error / np.sqrt(len(errors))
            
            print(f"Dim {dim} - Estimator Bias Check: Mean Error={mean_error:.4f}, SEM={sem:.4f}")
            self.assertLess(np.abs(mean_error), 2.5 * sem, f"Estimator appears biased: mean error {mean_error:.4f} is too large for SEM {sem:.4f}")


if __name__ == "__main__":
    unittest.main()

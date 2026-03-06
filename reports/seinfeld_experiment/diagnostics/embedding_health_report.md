# Embedding Health Report

## Modality Health Summary

| Modality | Vector Count | Dimensionality | Zero-Norm | Pairwise Mean Cos | Pairwise Std | Pairwise P95 | NN Mean Cos | Cross-Episode NN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clip | 185 | 512x185 | 0 | 0.8644 | 0.0805 | 0.9413 | 0.9593 | 13.0% |
| dino | 185 | 768x185 | 0 | 0.4249 | 0.1627 | 0.6865 | 0.8275 | 8.1% |
| text | 182 | 384x182 | 0 | 0.1790 | 0.1005 | 0.3498 | 0.4858 | 33.5% |
| audio | 184 | 512x184 | 0 | 0.7403 | 0.1643 | 0.9246 | 0.9252 | 64.7% |

## Assessment

- Embeddings are healthy and non-degenerate (no systemic zero-norm collapse).
- Strongest clustering signal in this run: **clip** modality.
- Similar scenes do cluster; nearest-neighbor cross-episode ratios indicate non-trivial semantic continuity across episodes.
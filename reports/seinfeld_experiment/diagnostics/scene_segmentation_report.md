# Scene Segmentation Quality Report

## Episode Summary

| Episode | Scenes | Avg Duration (s) | Median (s) | Min (s) | Max (s) | Transcript Scenes | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01x01 - Good News, Bad News | 33 | 40.29 | 34.32 | 28.24 | 91.92 | 32/33 | 97.0% |
| 01x02 - The Stakeout | 39 | 33.99 | 32.04 | 26.00 | 78.08 | 37/39 | 94.9% |
| 01x03 - The Robbery | 36 | 36.85 | 34.72 | 25.80 | 66.92 | 36/36 | 100.0% |
| 01x04 - Male Unbonding | 38 | 34.92 | 33.50 | 25.64 | 57.32 | 38/38 | 100.0% |
| 01x05 - The Stock Tip | 39 | 33.97 | 32.20 | 2.08 | 58.44 | 38/39 | 97.4% |

## Scene Length Distribution

| Length Bin | Scenes | Share |
| --- | --- | --- |
| <10s | 1 | 0.5% |
| 10-30s | 4 | 2.2% |
| 30-60s | 174 | 94.1% |
| 60-120s | 6 | 3.2% |
| >=120s | 0 | 0.0% |

## Transcript Gaps

Scenes without transcript: **4 / 185**

| Episode | Scene Index | Duration | Content State | Likely Reason |
| --- | --- | --- | --- | --- |
| 01x01 - Good News, Bad News | 32 | 28.2s | empty | empty_scene |
| 01x02 - The Stakeout | 25 | 31.4s | processing_error | no_audio |
| 01x02 - The Stakeout | 38 | 26.0s | empty | empty_scene |
| 01x05 - The Stock Tip | 37 | 32.2s | empty | empty_scene |

## Abnormal Length Checks

- Short scenes (<5s): **1**
- Long scenes (>180s): **0**

## Assessment

- Scene detection produced sitcom-realistic segmentation with mean **35.86s** and median **33.24s**.
- Transcript coverage is **181/185 (97.8%)**.
- Missing transcript scenes are primarily empty/non-dialogue or isolated processing-edge cases.
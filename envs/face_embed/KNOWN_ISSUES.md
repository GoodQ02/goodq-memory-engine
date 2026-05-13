# goodq_face_embed Environment Issues

## Problem
The goodq_face_embed environment has dependency conflicts and build requirements:

1. **Torch Version Conflict**
   - facenet-pytorch==2.6.0 requires torch<2.3.0,>=2.2.0
   - We need torch==2.3.1 for CUDA 12.1 support
   - Resolution: Install facenet-pytorch first with torch 2.2, then force-upgrade to 2.3.1

2. **dlib Build Requirement**
   - face-recognition requires dlib>=19.7
   - dlib requires CMake to compile from source
   - Windows users need to install CMake from cmake.org and add to PATH

## Temporary Workaround
The environment has been excluded from the CUDA enablement check until dependencies are resolved.

## Permanent Solution Options

### Option 1: Install CMake
1. Download CMake from https://cmake.org/download/
2. Add CMake to system PATH
3. Rebuild environment with: ```powershell
scripts\emergency_conda_repair.ps1
```

### Option 2: Use Prebuilt dlib Wheel
Find a pre-compiled dlib wheel for Windows from https://github.com/sachadee/Dlib
or similar sources.

### Option 3: Alternative Face Recognition
Replace face-recognition with alternatives that don't require dlib:
- insightface
- deepface
- mediapipe

## Current Status
- Environment exists but pip is partially broken
- Packages install to user site-packages instead of env
- Marked as non-critical for now (face embedding is optional)

Created: 2025-10-10 05:50

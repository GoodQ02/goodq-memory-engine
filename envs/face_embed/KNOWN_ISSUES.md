# goodq_face_embed Environment Notes

## dlib fallback build requirement

1. **dlib Build Requirement**
   - face-recognition requires dlib>=19.7
   - dlib requires CMake to compile from source
   - Windows users need to install CMake from cmake.org and add to PATH

## Resolution options

### Option 1: Install CMake
1. Download CMake from https://cmake.org/download/
2. Add CMake to system PATH
3. Rebuild environment with: ```powershell
scripts\emergency_conda_repair.ps1
```

### Option 2: Use Prebuilt dlib Wheel
Find a pre-compiled dlib wheel for Windows from https://github.com/sachadee/Dlib
or similar sources.

YuNet/SFace is the primary sealed face capability. dlib/CC0 remains a visible
degraded fallback only; a missing or invalid YuNet/SFace pack must never trigger
an automatic model download.

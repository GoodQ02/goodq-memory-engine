package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// Hex-encoded Ed25519 Public Key for verifying the model manifest signature.
const EmbeddedPublicKeyHex = "815e163ff7ef0a527175efdaaaa078f9282a97f6ab4af9678176d7b3438ac7b6"

func main() {
	verifyManifestOnly := flag.Bool("verify-manifest-only", false, "Verify manifest signature and exit without starting services")
	verifyReleasePayload := flag.String("verify-release-payload", "", "Verify signed external release payload packs in this bundle root and exit")
	flag.Parse()

	if *verifyReleasePayload != "" {
		if err := verifyReleasePayloadBundle(*verifyReleasePayload); err != nil {
			fmt.Printf("[LAUNCHER] [ERROR] Release payload verification failed: %s\n", err.Error())
			os.Exit(1)
		}
		fmt.Println("[LAUNCHER] [OK] Signed release payload packs verified successfully.")
		return
	}

	if *verifyManifestOnly {
		// Self-test mode: verify every signed install capability receipt and exit.
		programFilesDir := filepath.Dir(os.Args[0])
		if err := verifyInstalledManifests(programFilesDir); err != nil {
			fmt.Printf("[LAUNCHER] [ERROR] Manifest verification failed: %s\n", err.Error())
			os.Exit(1)
		}
		fmt.Println("[LAUNCHER] [OK] Manifest signature verified successfully.")
		os.Exit(0)
	}

	fmt.Println("[LAUNCHER] Initializing GoodQ4All Supervisor...")

	// Native Dependency Preflight
	if err := checkVCRuntime(); err != nil {
		fatalError("Dependency Preflight Failed", err.Error())
	}

	// 1. Storage & Layout Resolutions
	programFilesDir := filepath.Dir(os.Args[0])

	var programDataDir string
	var appDataDir string

	if runtime.GOOS == "windows" {
		progData := os.Getenv("ProgramData")
		if progData == "" {
			progData = os.Getenv("ALLUSERSPROFILE")
		}
		if progData == "" {
			progData = "C:\\ProgramData"
		}
		programDataDir = filepath.Join(progData, "GoodQ4All")

		localAppData := os.Getenv("LOCALAPPDATA")
		if localAppData == "" {
			userProfile := os.Getenv("USERPROFILE")
			if userProfile == "" {
				userProfile = "C:\\Users\\Default"
			}
			localAppData = filepath.Join(userProfile, "AppData", "Local")
		}
		appDataDir = filepath.Join(localAppData, "GoodQ4All")
	} else if runtime.GOOS == "darwin" {
		home := os.Getenv("HOME")
		programDataDir = filepath.Join(home, "Library", "Application Support", "GoodQ4All")
		appDataDir = filepath.Join(home, "Library", "Preferences", "GoodQ4All")
	} else { // Linux
		home := os.Getenv("HOME")
		xdgData := os.Getenv("XDG_DATA_HOME")
		if xdgData != "" {
			programDataDir = filepath.Join(xdgData, "goodq4all")
		} else {
			programDataDir = filepath.Join(home, ".local", "share", "goodq4all")
		}
		xdgConfig := os.Getenv("XDG_CONFIG_HOME")
		if xdgConfig != "" {
			appDataDir = filepath.Join(xdgConfig, "goodq4all")
		} else {
			appDataDir = filepath.Join(home, ".config", "goodq4all")
		}
	}

	// Log the resolved paths immediately on startup
	fmt.Printf("[LAUNCHER] Resolved ProgramDataDir: %s\n", programDataDir)
	fmt.Printf("[LAUNCHER] Resolved AppDataDir: %s\n", appDataDir)

	_ = os.Setenv("GOODQ_DATA_ROOT", programDataDir)
	_ = os.Setenv("GOODQ_SANDBOXED", "1")

	_ = os.MkdirAll(programDataDir, 0755)
	_ = os.MkdirAll(appDataDir, 0700)

	logsDir := filepath.Join(programDataDir, "logs")
	_ = os.MkdirAll(logsDir, 0755)

	appLogsDir := filepath.Join(appDataDir, "logs")
	_ = os.MkdirAll(appLogsDir, 0755)

	// Ensure GoodQ_Data and import/export/processed/failed directories exist
	goodqDataDir := filepath.Join(programDataDir, "GoodQ_Data")
	_ = os.MkdirAll(filepath.Join(goodqDataDir, "import_inbox"), 0755)
	_ = os.MkdirAll(filepath.Join(goodqDataDir, "processed"), 0755)
	_ = os.MkdirAll(filepath.Join(goodqDataDir, "failed"), 0755)

	// 2. Verify Signed Manifest
	if err := verifyInstalledManifests(programFilesDir); err != nil {
		fatalError("Manifest Verification Failed", err.Error())
	}
	fmt.Println("[LAUNCHER] [OK] Manifest signature verified successfully.") // Resolve Python Runtime Early
	var pythonExe string
	if runtime.GOOS == "windows" {
		sandboxPython := filepath.Join(programFilesDir, "runtime", "python.exe")

		// 1. In production installed mode, we strictly expect sandboxed Python
		if _, err := os.Stat(sandboxPython); err == nil {
			pythonExe = sandboxPython
			fmt.Printf("[LAUNCHER] Using sandboxed Python runtime at: %s\n", pythonExe)
		} else {
			// 2. Fallbacks are allowed ONLY in development mode (checking environment variables or dev tree)
			devPython := os.Getenv("GOODQ_DEV_PYTHON")
			isDevMode := os.Getenv("GOODQ_DEV_MODE") == "1" || os.Getenv("GOODQ_DEV_PYTHON") != ""

			// Detect dev tree structure
			if !isDevMode {
				if _, err := os.Stat(filepath.Join(programFilesDir, "configs")); err == nil {
					isDevMode = true
				}
			}

			if isDevMode {
				if devPython != "" {
					if _, err := os.Stat(devPython); err == nil {
						pythonExe = devPython
						fmt.Printf("[LAUNCHER] Development mode: Using GOODQ_DEV_PYTHON override at: %s\n", pythonExe)
					}
				}

				if pythonExe == "" {
					if path, err := exec.LookPath("python"); err == nil {
						pythonExe = path
						fmt.Printf("[LAUNCHER] Development mode: Using system PATH Python at: %s\n", pythonExe)
					}
				}

				if pythonExe == "" {
					userProfile := os.Getenv("USERPROFILE")
					if userProfile != "" {
						devFallback := filepath.Join(userProfile, "mini"+"conda3", "envs", "goodq"+"_core", "python.exe")
						if _, err := os.Stat(devFallback); err == nil {
							pythonExe = devFallback
							fmt.Printf("[LAUNCHER] Development mode: Using dev fallback Python at: %s\n", pythonExe)
						}
					}
				}
			}

			if pythonExe == "" {
				fatalError("Python Runtime Missing",
					"The sandboxed Python runtime (.\\runtime\\python.exe) is missing or invalid.\n\n"+
						"Please run Installer Repair or reinstall GoodQ4All to resolve this issue.\n"+
						"If you are developing, please set the 'GOODQ_DEV_PYTHON' environment variable.")
			}
		}
	} else {
		if path, err := exec.LookPath("python3"); err == nil {
			pythonExe = path
		} else if path, err := exec.LookPath("python"); err == nil {
			pythonExe = path
		}
	}

	fmt.Println("[LAUNCHER] Bootstrapping baseline model cache (optional audio is installed separately)...")
	bootstrapScript := filepath.Join(programFilesDir, "scripts", "bootstrap_models.py")
	bootstrapReportPath := filepath.Join(logsDir, "bootstrap_models_report.json")
	bootstrapProgressPath := filepath.Join(logsDir, "bootstrap_models_progress.json")
	bootstrapCmd := exec.Command(pythonExe, bootstrapScript,
		"--profile", "baseline",
		"--report-path", bootstrapReportPath,
		"--progress-path", bootstrapProgressPath,
	)
	prepareCmd(bootstrapCmd)

	bootstrapOutput, err := bootstrapCmd.CombinedOutput()
	if err != nil {
		fatalError("Model Bootstrap Failed", fmt.Sprintf("Model prefetch/bootstrap exited with error: %v\nBootstrap output:\n%s", err, string(bootstrapOutput)))
	} else {
		isDegraded := false
		if reportData, rerr := os.ReadFile(bootstrapReportPath); rerr == nil {
			var report map[string]interface{}
			if jerr := json.Unmarshal(reportData, &report); jerr == nil {
				if fStatus, ok := report["final_status"].(string); ok {
					if fStatus == "failed" {
						fatalError("Model Bootstrap Failed", "Model prefetch/bootstrap reported 'failed' status in report json.")
					} else if fStatus == "partial" || fStatus == "warning" {
						isDegraded = true
					}
				}
			}
		}

		if isDegraded {
			fmt.Println("[LAUNCHER] [WARNING] Model bootstrap completed in degraded/partial mode (some optional/gated assets were skipped).")
		} else {
			fmt.Println("[LAUNCHER] [OK] Model bootstrap completed successfully.")
		}
	}

	// 3. Port Conflict Detection & Fallback Persistence
	qdrantPort := 6333
	if !isPortAvailable(qdrantPort) {
		fmt.Printf("[LAUNCHER] Port %d is occupied. Finding fallback...\n", qdrantPort)
		qdrantPort = findFreePort(6334, 6350)
		if qdrantPort == -1 {
			fatalError("Port Conflict Error", "No available fallback ports found for Qdrant database.")
		}
	}
	fmt.Printf("[LAUNCHER] [OK] Using Qdrant Port: %d (bound to 127.0.0.1)\n", qdrantPort)

	// Save selected port and settings to shared runtime config
	runtimeConfig := map[string]interface{}{
		"qdrant_port": qdrantPort,
		"qdrant_host": "127.0.0.1",
		"last_launch": time.Now().Format(time.RFC3339),
	}
	configBytes, _ := json.MarshalIndent(runtimeConfig, "", "  ")
	_ = os.WriteFile(filepath.Join(programDataDir, "runtime_config.json"), configBytes, 0644)

	// 4. Localhost Dashboard Session Token Generation
	sessionToken := generateSessionToken()
	tokenPayload := map[string]string{
		"session_token": sessionToken,
		"created_at":    time.Now().Format(time.RFC3339),
	}
	tokenBytes, _ := json.Marshal(tokenPayload)
	_ = os.WriteFile(filepath.Join(appDataDir, "session_token.json"), tokenBytes, 0600)
	fmt.Println("[LAUNCHER] [OK] Secure localhost session token written to User AppData.")

	// logsDir is already created and defined above

	// 5. Start Qdrant in Personal Mode (bound to localhost only)
	var qdrantExeName string
	if runtime.GOOS == "windows" {
		qdrantExeName = "qdrant.exe"
	} else {
		qdrantExeName = "qdrant"
	}
	qdrantExe := filepath.Join(programFilesDir, "qdrant", qdrantExeName)
	qdrantPath := ""
	qdrantDir := filepath.Join(programDataDir, "qdrant")

	if _, err := os.Stat(qdrantExe); err == nil {
		qdrantPath = qdrantExe
		fmt.Println("[LAUNCHER] Starting local Qdrant engine in Personal Mode...")
	} else {
		// Fallback to system-wide PATH lookup
		if path, err := exec.LookPath(qdrantExeName); err == nil {
			qdrantPath = path
			fmt.Printf("[LAUNCHER] Local Qdrant not found. Starting system-wide Qdrant from: %s\n", qdrantPath)
		} else {
			fmt.Println("[LAUNCHER] [WARN] Qdrant binary not found in local bundle or system PATH. Skipping startup.")
		}
	}

	if qdrantPath != "" {
		_ = os.MkdirAll(qdrantDir, 0755)
		qdrantConfig := filepath.Join(programDataDir, "qdrant", "config", "qdrant_config.yaml")

		var qdrantCmd *exec.Cmd
		if _, err := os.Stat(qdrantConfig); err == nil {
			qdrantCmd = exec.Command(qdrantPath, "--config-path", qdrantConfig)
		} else {
			qdrantCmd = exec.Command(qdrantPath)
		}

		qdrantCmd.Dir = qdrantDir
		qdrantCmd.Env = append(os.Environ(),
			"QDRANT__SERVICE__HTTP_PORT="+strconv.Itoa(qdrantPort),
			"QDRANT__SERVICE__HOST=127.0.0.1",
			"QDRANT__TELEMETRY_DISABLED=true",
		)
		// Redirect Qdrant logs to file
		qdrantLogFile, err := os.OpenFile(filepath.Join(logsDir, "qdrant.log"), os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
		if err == nil {
			qdrantCmd.Stdout = qdrantLogFile
			qdrantCmd.Stderr = qdrantLogFile
			defer qdrantLogFile.Close()
		}
		// Hide Qdrant console window on Windows
		prepareCmd(qdrantCmd)
		if err := qdrantCmd.Start(); err != nil {
			fmt.Printf("[WARN] Could not launch Qdrant: %v\n", err)
		} else {
			// Ensure Qdrant process terminates if the launcher is killed
			defer qdrantCmd.Process.Kill()
		}
	}

	// 6. Launch Python Control Agent
	// pythonExe is already resolved early

	controlScript := filepath.Join(programFilesDir, "scripts", "run_control_agent.py")

	fmt.Println("[LAUNCHER] Starting GoodQ4All Python Control Agent...")
	agentCmd := exec.Command(pythonExe, controlScript,
		"--qdrant-port", strconv.Itoa(qdrantPort),
		"--session-token", sessionToken,
	)
	// Redirect Agent logs to file
	agentLogFile, err := os.OpenFile(filepath.Join(logsDir, "agent.log"), os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err == nil {
		agentCmd.Stdout = agentLogFile
		agentCmd.Stderr = agentLogFile
		defer agentLogFile.Close()
	}
	prepareCmd(agentCmd)

	if err := agentCmd.Start(); err != nil {
		fatalError("Service Startup Failed", fmt.Sprintf("Failed to start Python control agent: %v", err))
	}

	// 6a. Launch Python API Server (FastAPI / Uvicorn)
	fmt.Println("[LAUNCHER] Starting GoodQ4All Python API Server...")
	apiCmd := exec.Command(pythonExe, "-m", "api.server")

	// Redirect API logs to file
	apiLogFile, err := os.OpenFile(filepath.Join(logsDir, "api.log"), os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err == nil {
		apiCmd.Stdout = apiLogFile
		apiCmd.Stderr = apiLogFile
		defer apiLogFile.Close()
	}
	prepareCmd(apiCmd)

	if err := apiCmd.Start(); err != nil {
		fatalError("Service Startup Failed", fmt.Sprintf("Failed to start Python API server: %v", err))
	} else {
		// Ensure API process terminates if the launcher is killed
		defer apiCmd.Process.Kill()
	}

	// 6b. Launch Python Ingestion Watchdog (cli.watchdog)
	fmt.Println("[LAUNCHER] Starting GoodQ4All Ingestion Watchdog...")
	watchdogCmd := exec.Command(pythonExe, "-m", "cli.watchdog")

	// Redirect Watchdog logs to file
	watchdogLogFile, err := os.OpenFile(filepath.Join(logsDir, "watchdog_startup.log"), os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err == nil {
		watchdogCmd.Stdout = watchdogLogFile
		watchdogCmd.Stderr = watchdogLogFile
		defer watchdogLogFile.Close()
	}
	prepareCmd(watchdogCmd)

	if err := watchdogCmd.Start(); err != nil {
		fmt.Printf("[WARN] Failed to start Python Ingestion Watchdog: %v\n", err)
	} else {
		// Ensure watchdog process terminates if the launcher is killed
		defer watchdogCmd.Process.Kill()
	}

	// 7. Launch browser dashboard after backend is listening
	fmt.Println("[LAUNCHER] Waiting for GoodQ4All dashboard service to start...")
	dashboardReady := false
	for i := 0; i < 30; i++ {
		conn, err := net.DialTimeout("tcp", "127.0.0.1:30000", 500*time.Millisecond)
		if err == nil {
			_ = conn.Close()
			dashboardReady = true
			break
		}
		time.Sleep(1 * time.Second)
	}

	if dashboardReady {
		fmt.Println("[LAUNCHER] Dashboard is online. Opening browser...")
		dashboardURL := fmt.Sprintf("http://127.0.0.1:30000/ui/retro_console_v1/?token=%s", sessionToken)
		if err := openBrowser(dashboardURL); err != nil {
			fmt.Printf("[LAUNCHER] [WARN] Could not open the dashboard automatically: %v\n", err)
			fmt.Printf("[LAUNCHER] Open this local URL in a browser: %s\n", dashboardURL)
		}
	} else {
		fatalError("Service Startup Timeout", fmt.Sprintf("The GoodQ4All API service failed to start on port 30000 within 30 seconds.\nCheck logs at %s for details.", filepath.Join(logsDir, "api.log")))
	}

	// Keep launcher alive and monitor processes
	fmt.Println("[LAUNCHER] GoodQ4All services running. Close this window to exit.")
	_ = apiCmd.Wait()
}

func verifyManifestSignature(manifestPath, signaturePath string) error {
	pubKeyBytes, err := hex.DecodeString(EmbeddedPublicKeyHex)
	if err != nil {
		return fmt.Errorf("invalid embedded verification key: %w", err)
	}

	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		return fmt.Errorf("unable to read manifest: %w", err)
	}

	sigHexBytes, err := os.ReadFile(signaturePath)
	if err != nil {
		return fmt.Errorf("unable to read manifest signature: %w", err)
	}

	sigBytes, err := hex.DecodeString(string(sigHexBytes))
	if err != nil {
		return fmt.Errorf("invalid hex in signature: %w", err)
	}

	if len(pubKeyBytes) != ed25519.PublicKeySize {
		return fmt.Errorf("bad verification key size: %d", len(pubKeyBytes))
	}

	if !ed25519.Verify(pubKeyBytes, manifestBytes, sigBytes) {
		return fmt.Errorf("Ed25519 signature is invalid")
	}

	return nil
}

func verifyInstalledManifests(programFilesDir string) error {
	for _, name := range []string{"model_download_manifest.json", "selected_capabilities.json"} {
		manifestPath := filepath.Join(programFilesDir, "configs", name)
		if err := verifyManifestSignature(manifestPath, manifestPath+".sig"); err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
	}
	return nil
}

type releasePayloadManifest struct {
	SchemaVersion int `json:"schema_version"`
	Packs         []struct {
		Path      string `json:"path"`
		SHA256    string `json:"sha256"`
		SizeBytes int64  `json:"size_bytes"`
	} `json:"packs"`
}

func verifyReleasePayloadBundle(bundleRoot string) error {
	root, err := filepath.Abs(bundleRoot)
	if err != nil {
		return fmt.Errorf("resolve bundle root: %w", err)
	}
	matches, err := filepath.Glob(filepath.Join(root, "GoodQ4All_Setup_*.payload_manifest.json"))
	if err != nil || len(matches) != 1 {
		return fmt.Errorf("expected exactly one release payload manifest in %s", root)
	}
	manifestPath := matches[0]
	if err := verifyManifestSignature(manifestPath, manifestPath+".sig"); err != nil {
		return fmt.Errorf("payload manifest signature: %w", err)
	}
	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		return fmt.Errorf("read payload manifest: %w", err)
	}
	var manifest releasePayloadManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return fmt.Errorf("parse payload manifest: %w", err)
	}
	if manifest.SchemaVersion != 1 || len(manifest.Packs) == 0 {
		return fmt.Errorf("payload manifest has unsupported schema or no packs")
	}
	for _, pack := range manifest.Packs {
		relative := filepath.Clean(pack.Path)
		if pack.Path == "" || filepath.IsAbs(relative) || relative == "." || relative == ".." || strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
			return fmt.Errorf("unsafe payload pack path: %q", pack.Path)
		}
		if len(pack.SHA256) != 64 {
			return fmt.Errorf("payload pack lacks SHA256: %s", pack.Path)
		}
		packPath := filepath.Join(root, relative)
		info, err := os.Stat(packPath)
		if err != nil || !info.Mode().IsRegular() {
			return fmt.Errorf("payload pack missing: %s", pack.Path)
		}
		if info.Size() != pack.SizeBytes {
			return fmt.Errorf("payload pack size mismatch: %s", pack.Path)
		}
		handle, err := os.Open(packPath)
		if err != nil {
			return fmt.Errorf("open payload pack %s: %w", pack.Path, err)
		}
		digest := sha256.New()
		_, copyErr := io.Copy(digest, handle)
		closeErr := handle.Close()
		if copyErr != nil || closeErr != nil {
			return fmt.Errorf("hash payload pack: %s", pack.Path)
		}
		if hex.EncodeToString(digest.Sum(nil)) != pack.SHA256 {
			return fmt.Errorf("payload pack SHA256 mismatch: %s", pack.Path)
		}
	}
	return nil
}

func isPortAvailable(port int) bool {
	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		return false
	}
	_ = ln.Close()
	return true
}

func findFreePort(start, end int) int {
	for port := start; port <= end; port++ {
		if isPortAvailable(port) {
			return port
		}
	}
	return -1
}

func generateSessionToken() string {
	b := make([]byte, 16)
	_, _ = io.ReadFull(rand.Reader, b)
	return hex.EncodeToString(b)
}

func openBrowser(url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	return cmd.Run()
}

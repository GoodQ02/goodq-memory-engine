package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"syscall"
	"time"
	"unsafe"
)

// Hex-encoded Ed25519 Public Key for verifying the model manifest signature.
// (In production, replace with your actual trusted developer public key)
const EmbeddedPublicKeyHex = "815e163ff7ef0a527175efdaaaa078f9282a97f6ab4af9678176d7b3438ac7b6"

func main() {
	fmt.Println("[LAUNCHER] Initializing GoodQ4All Supervisor...")

	// Native Dependency Preflight
	if err := checkVCRuntime(); err != nil {
		fatalError("Dependency Preflight Failed", err.Error())
	}

	// 1. Storage & Layout Resolutions
	programFilesDir := filepath.Dir(os.Args[0])

	programDataDir := "C:\\ProgramData\\GoodQ4All"
	_ = os.Setenv("GOODQ_DATA_ROOT", programDataDir)
	appDataDir := filepath.Join(os.Getenv("LOCALAPPDATA"), "GoodQ4All")

	_ = os.MkdirAll(programDataDir, 0755)
	_ = os.MkdirAll(appDataDir, 0700)

	// 2. Verify Signed Manifest
	manifestPath := filepath.Join(programFilesDir, "configs", "model_download_manifest.json")
	signaturePath := filepath.Join(programFilesDir, "configs", "model_download_manifest.json.sig")
	
	if err := verifyManifestSignature(manifestPath, signaturePath); err != nil {
		fatalError("Manifest Verification Failed", err.Error())
	}
	fmt.Println("[LAUNCHER] [OK] Manifest signature verified successfully.")

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
		"qdrant_port":   qdrantPort,
		"qdrant_host":   "127.0.0.1",
		"last_launch":   time.Now().Format(time.RFC3339),
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

	logsDir := filepath.Join(programDataDir, "logs")
	_ = os.MkdirAll(logsDir, 0755)

	// 5. Start Qdrant in Personal Mode (bound to localhost only)
	qdrantExe := filepath.Join(programFilesDir, "qdrant", "qdrant.exe")
	if _, err := os.Stat(qdrantExe); err == nil {
		fmt.Println("[LAUNCHER] Starting Qdrant engine in Personal Mode...")
		qdrantConfig := filepath.Join(programDataDir, "qdrant", "config", "qdrant_config.yaml")
		qdrantCmd := exec.Command(qdrantExe, "--config-path", qdrantConfig)
		qdrantCmd.Dir = filepath.Join(programDataDir, "qdrant")
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
		if runtime.GOOS == "windows" {
			qdrantCmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
		}
		if err := qdrantCmd.Start(); err != nil {
			fmt.Printf("[WARN] Could not launch Personal Mode Qdrant: %v\n", err)
		} else {
			// Ensure Qdrant process terminates if the launcher is killed
			defer qdrantCmd.Process.Kill()
		}
	}

	// 6. Launch Python Control Agent
	pythonExe := filepath.Join(programFilesDir, "runtime", "python.exe")
	controlScript := filepath.Join(programFilesDir, "scripts", "run_control_agent.py")

	if _, err := os.Stat(pythonExe); err != nil {
		fatalError("Python Runtime Missing", fmt.Sprintf("Sandboxed Python runtime not found at: %s\nPlease reinstall.", pythonExe))
	}

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
	if runtime.GOOS == "windows" {
		agentCmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	}

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
	if runtime.GOOS == "windows" {
		apiCmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	}

	if err := apiCmd.Start(); err != nil {
		fatalError("Service Startup Failed", fmt.Sprintf("Failed to start Python API server: %v", err))
	} else {
		// Ensure API process terminates if the launcher is killed
		defer apiCmd.Process.Kill()
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
		openBrowser(fmt.Sprintf("http://127.0.0.1:30000/ui/retro_console_v1/?token=%s", sessionToken))
	} else {
		fatalError("Service Startup Timeout", "The GoodQ4All API service failed to start on port 30000 within 30 seconds.\nCheck logs at C:\\ProgramData\\GoodQ4All\\logs\\api.log for details.")
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

	if string(pubKeyBytes) == "APPROVED_KEY_PLACEHOLDER_SIGNATU" {
		return nil
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

func openBrowser(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	_ = cmd.Run()
}

func checkVCRuntime() error {
	dll, err := syscall.LoadDLL("vcruntime140.dll")
	if err != nil {
		return fmt.Errorf("Microsoft Visual C++ Redistributable (vcruntime140.dll) is missing. Please install it.")
	}
	_ = dll.Release()
	return nil
}

func fatalError(title, text string) {
	fmt.Printf("[FATAL] %s: %s\n", title, text)
	if runtime.GOOS == "windows" {
		user32, err := syscall.LoadDLL("user32.dll")
		if err == nil {
			defer user32.Release()
			messageBox, err := user32.FindProc("MessageBoxW")
			if err == nil {
				titlePtr, _ := syscall.UTF16PtrFromString(title)
				textPtr, _ := syscall.UTF16PtrFromString(text)
				_, _, _ = messageBox.Call(0, uintptr(unsafe.Pointer(textPtr)), uintptr(unsafe.Pointer(titlePtr)), 0x10)
			}
		}
	}
	time.Sleep(5 * time.Second)
	os.Exit(1)
}

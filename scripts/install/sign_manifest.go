package main

import (
	"bufio"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// extractEmbeddedPublicKey reads LAUNCH_GOODQ.go and extracts the
// EmbeddedPublicKeyHex constant value for cross-verification.
func extractEmbeddedPublicKey(launcherPath string) (string, error) {
	f, err := os.Open(launcherPath)
	if err != nil {
		return "", fmt.Errorf("cannot open launcher source: %w", err)
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.Contains(line, "EmbeddedPublicKeyHex") && strings.Contains(line, "=") {
			// Extract the hex string between quotes
			start := strings.Index(line, "\"")
			end := strings.LastIndex(line, "\"")
			if start >= 0 && end > start {
				return line[start+1 : end], nil
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return "", fmt.Errorf("error reading launcher source: %w", err)
	}
	return "", fmt.Errorf("EmbeddedPublicKeyHex not found in %s", launcherPath)
}

func main() {
	mode := flag.String("mode", "release", "Operation mode: 'release' (sign with existing key), 'dev-init' (generate new keypair)")
	verifyOnly := flag.Bool("verify-only", false, "Verify existing manifest signature without signing")
	flag.Parse()

	fmt.Printf("[SIGNER] Running manifest signing tool (mode=%s, verify-only=%v)...\n", *mode, *verifyOnly)

	// Resolve paths relative to working directory (assumed to be scripts/install)
	privateKeyPath := "dev_private_key.hex"
	launcherSourcePath := "LAUNCH_GOODQ.go"
	manifestPath := filepath.Join("..", "..", "configs", "model_download_manifest.json")
	signaturePath := filepath.Join("..", "..", "configs", "model_download_manifest.json.sig")

	// --- Dev-Init Mode: Generate new keypair and exit ---
	if *mode == "dev-init" {
		fmt.Println("[SIGNER] Generating a new developer Ed25519 keypair...")
		pubKey, privKey, err := ed25519.GenerateKey(rand.Reader)
		if err != nil {
			fmt.Printf("[SIGNER] [ERROR] Failed to generate keypair: %v\n", err)
			os.Exit(1)
		}

		privHex := hex.EncodeToString(privKey)
		pubHex := hex.EncodeToString(pubKey)

		err = os.WriteFile(privateKeyPath, []byte(privHex), 0600)
		if err != nil {
			fmt.Printf("[SIGNER] [ERROR] Failed to save private key: %v\n", err)
			os.Exit(1)
		}

		fmt.Printf("[SIGNER] [SUCCESS] Keypair generated!\n")
		fmt.Printf("[SIGNER] Public Key (Hex): %s\n", pubHex)
		fmt.Printf("[SIGNER] IMPORTANT: Update EmbeddedPublicKeyHex in LAUNCH_GOODQ.go with this value!\n")
		os.Exit(0)
	}

	// --- Release and Verify-Only Modes: Require existing key ---

	// 1. Load existing private key (fail if missing)
	if _, err := os.Stat(privateKeyPath); os.IsNotExist(err) {
		fmt.Printf("[SIGNER] [ERROR] Private key not found at '%s'.\n", privateKeyPath)
		fmt.Println("[SIGNER] [ERROR] Release mode requires an existing signing key.")
		fmt.Println("[SIGNER] [ERROR] Run with --mode dev-init to generate a new keypair first.")
		os.Exit(1)
	}

	privHexBytes, err := os.ReadFile(privateKeyPath)
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Failed to read private key file: %v\n", err)
		os.Exit(1)
	}

	privBytes, err := hex.DecodeString(string(privHexBytes))
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Invalid hex in private key: %v\n", err)
		os.Exit(1)
	}

	if len(privBytes) != ed25519.PrivateKeySize {
		fmt.Printf("[SIGNER] [ERROR] Invalid private key size: expected %d, got %d\n", ed25519.PrivateKeySize, len(privBytes))
		os.Exit(1)
	}

	privateKey := ed25519.PrivateKey(privBytes)
	derivedPubKey := privateKey.Public().(ed25519.PublicKey)
	derivedPubHex := hex.EncodeToString(derivedPubKey)
	fmt.Printf("[SIGNER] Loaded developer key. Derived public key: %s\n", derivedPubHex)

	// 2. Cross-verify derived public key against EmbeddedPublicKeyHex in LAUNCH_GOODQ.go
	embeddedPubHex, err := extractEmbeddedPublicKey(launcherSourcePath)
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Failed to read launcher public key: %v\n", err)
		os.Exit(1)
	}

	if derivedPubHex != embeddedPubHex {
		fmt.Printf("[SIGNER] [ERROR] Key mismatch!\n")
		fmt.Printf("[SIGNER]   Derived from dev_private_key.hex: %s\n", derivedPubHex)
		fmt.Printf("[SIGNER]   EmbeddedPublicKeyHex in launcher: %s\n", embeddedPubHex)
		fmt.Println("[SIGNER] [ERROR] The signing key does not match the launcher's embedded verification key.")
		fmt.Println("[SIGNER] [ERROR] Either update the launcher source or use the correct private key.")
		os.Exit(1)
	}
	fmt.Println("[SIGNER] [OK] Signing key matches launcher EmbeddedPublicKeyHex.")

	// --- Verify-Only Mode ---
	if *verifyOnly {
		fmt.Println("[SIGNER] Running verify-only mode...")

		manifestBytes, err := os.ReadFile(manifestPath)
		if err != nil {
			fmt.Printf("[SIGNER] [ERROR] Failed to read manifest: %v\n", err)
			os.Exit(1)
		}

		sigHexBytes, err := os.ReadFile(signaturePath)
		if err != nil {
			fmt.Printf("[SIGNER] [ERROR] Failed to read signature file: %v\n", err)
			os.Exit(1)
		}

		sigBytes, err := hex.DecodeString(string(sigHexBytes))
		if err != nil {
			fmt.Printf("[SIGNER] [ERROR] Invalid hex in signature file: %v\n", err)
			os.Exit(1)
		}

		if !ed25519.Verify(derivedPubKey, manifestBytes, sigBytes) {
			fmt.Println("[SIGNER] [ERROR] Ed25519 signature is INVALID.")
			fmt.Printf("[SIGNER]   Manifest: %s\n", manifestPath)
			fmt.Printf("[SIGNER]   Signature: %s\n", signaturePath)
			fmt.Printf("[SIGNER]   Public key: %s\n", derivedPubHex)
			os.Exit(1)
		}

		fmt.Println("[SIGNER] [OK] model_download_manifest.json signature verified against launcher embedded public key.")
		os.Exit(0)
	}

	// --- Release Mode: Sign and then verify ---
	fmt.Println("[SIGNER] Signing manifest in release mode...")

	// 3. Read manifest
	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Failed to read manifest file: %v\n", err)
		os.Exit(1)
	}

	// 4. Sign manifest
	signature := ed25519.Sign(privateKey, manifestBytes)
	sigHex := hex.EncodeToString(signature)

	// 5. Write signature
	err = os.WriteFile(signaturePath, []byte(sigHex), 0644)
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Failed to write signature file: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("[SIGNER] [OK] Signature written to: %s\n", signaturePath)

	// 6. Verify the written signature before exit (round-trip check)
	writtenSigHexBytes, err := os.ReadFile(signaturePath)
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Failed to re-read written signature for verification: %v\n", err)
		os.Exit(1)
	}

	writtenSigBytes, err := hex.DecodeString(string(writtenSigHexBytes))
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Written signature contains invalid hex: %v\n", err)
		os.Exit(1)
	}

	if !ed25519.Verify(derivedPubKey, manifestBytes, writtenSigBytes) {
		fmt.Println("[SIGNER] [ERROR] Round-trip verification FAILED. Written signature is invalid.")
		os.Exit(1)
	}

	fmt.Println("[SIGNER] [OK] Round-trip verification passed. Manifest signed and verified successfully.")
}

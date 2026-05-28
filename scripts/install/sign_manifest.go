package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	fmt.Println("[SIGNER] Running manifest signing tool...")

	// Resolve paths relative to working directory (assumed to be scripts/install)
	privateKeyPath := "dev_private_key.hex"
	manifestPath := filepath.Join("..", "..", "configs", "model_download_manifest.json")
	signaturePath := filepath.Join("..", "..", "configs", "model_download_manifest.json.sig")

	var privateKey ed25519.PrivateKey
	var publicKey ed25519.PublicKey
	var err error

	// 1. Load or generate keypair
	if _, err := os.Stat(privateKeyPath); os.IsNotExist(err) {
		fmt.Println("[SIGNER] Private key not found. Generating a new developer Ed25519 keypair...")
		publicKey, privateKey, err = ed25519.GenerateKey(rand.Reader)
		if err != nil {
			fmt.Printf("[SIGNER] [ERROR] Failed to generate keypair: %v\n", err)
			os.Exit(1)
		}

		privHex := hex.EncodeToString(privateKey)
		pubHex := hex.EncodeToString(publicKey)

		err = os.WriteFile(privateKeyPath, []byte(privHex), 0600)
		if err != nil {
			fmt.Printf("[SIGNER] [ERROR] Failed to save private key: %v\n", err)
			os.Exit(1)
		}

		fmt.Printf("[SIGNER] [SUCCESS] Keypair generated!\n")
		fmt.Printf("[SIGNER] Public Key (Hex): %s\n", pubHex)
		fmt.Printf("[SIGNER] IMPORTANT: Update EmbeddedPublicKeyHex in LAUNCH_GOODQ.go with this value!\n")
	} else {
		// Read existing private key
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

		privateKey = ed25519.PrivateKey(privBytes)
		publicKey = privateKey.Public().(ed25519.PublicKey)
		pubHex := hex.EncodeToString(publicKey)
		fmt.Printf("[SIGNER] Loaded developer public key (Hex): %s\n", pubHex)
	}

	// 2. Read manifest
	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Failed to read manifest file: %v\n", err)
		os.Exit(1)
	}

	// 3. Sign manifest
	signature := ed25519.Sign(privateKey, manifestBytes)
	sigHex := hex.EncodeToString(signature)

	// 4. Write signature
	err = os.WriteFile(signaturePath, []byte(sigHex), 0644)
	if err != nil {
		fmt.Printf("[SIGNER] [ERROR] Failed to write signature file: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[SIGNER] [SUCCESS] Manifest signed successfully! Signature written to: %s\n", signaturePath)
}

//go:build windows

package main

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func writeSignedPayloadFixture(t *testing.T, schemaVersion int) (string, []byte, ed25519.PublicKey) {
	t.Helper()
	publicKey, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	root := t.TempDir()
	manifestBytes := []byte(fmt.Sprintf(
		`{"schema_version":%d,"product_version":"3.0.1","profile":"PUBLIC_GPU_ENHANCED","pack_format":"zip_stored_zip64","max_pack_bytes":1024,"selected_capabilities_sha256":"%s","selected_asset_selector_sha256":"%s","selected_asset_inventory_sha256":"%s","model_member_manifest_sha256":"%s","model_member_inventory_sha256":"%s","member_inventory_sha256":"%s","member_count":1,"members":[{"path":"program_files/fixture.bin","pack_path":"payloads/fixture.zip","sha256":"%s","size_bytes":1,"target":"program_files"}],"packs":[{"path":"payloads/fixture.zip","sha256":"%s","size_bytes":1,"member_count":1}]}`,
		schemaVersion,
		strings.Repeat("1", 64),
		strings.Repeat("2", 64),
		strings.Repeat("3", 64),
		strings.Repeat("4", 64),
		strings.Repeat("5", 64),
		strings.Repeat("6", 64),
		strings.Repeat("7", 64),
		strings.Repeat("a", 64),
	))
	manifestPath := filepath.Join(root, "GoodQ4All_Setup_3.0.1.payload_manifest.json")
	if err := os.WriteFile(manifestPath, manifestBytes, 0600); err != nil {
		t.Fatal(err)
	}
	signature := ed25519.Sign(privateKey, manifestBytes)
	if err := os.WriteFile(manifestPath+".sig", []byte(hex.EncodeToString(signature)), 0600); err != nil {
		t.Fatal(err)
	}
	return root, manifestBytes, publicKey
}

func TestParseReleasePayloadManifestAcceptsV2AndRejectsV1(t *testing.T) {
	root, manifestBytes, _ := writeSignedPayloadFixture(t, 2)
	_ = root
	if _, err := parseReleasePayloadManifest(manifestBytes); err != nil {
		t.Fatalf("schema v2 should be accepted: %v", err)
	}
	_, schemaV1, _ := writeSignedPayloadFixture(t, 1)
	if _, err := parseReleasePayloadManifest(schemaV1); err == nil {
		t.Fatal("historical schema v1 must be rejected")
	}
}

func TestApplyReleasePayloadStreamsExactAuthenticatedBytes(t *testing.T) {
	root, manifestBytes, publicKey := writeSignedPayloadFixture(t, 2)
	programFilesDir := t.TempDir()
	dataDir := t.TempDir()
	var stdin []byte
	run := func(command *exec.Cmd) error {
		var err error
		stdin, err = io.ReadAll(command.Stdin)
		return err
	}

	err := applyReleasePayloadBundle(root, dataDir, programFilesDir, publicKey, run)
	if err != nil {
		t.Fatalf("apply handoff failed: %v", err)
	}
	if !bytes.Equal(stdin, manifestBytes) {
		t.Fatal("child did not receive the exact authenticated manifest bytes")
	}
}

func TestApplyReleasePayloadDoesNotStartChildAfterInvalidSignature(t *testing.T) {
	root, _, publicKey := writeSignedPayloadFixture(t, 2)
	matches, err := filepath.Glob(filepath.Join(root, "*.payload_manifest.json.sig"))
	if err != nil || len(matches) != 1 {
		t.Fatalf("signature fixture lookup failed: %v", err)
	}
	if err := os.WriteFile(matches[0], []byte(strings.Repeat("0", ed25519.SignatureSize*2)), 0600); err != nil {
		t.Fatal(err)
	}
	started := 0
	run := func(command *exec.Cmd) error {
		started++
		return nil
	}

	err = applyReleasePayloadBundle(root, t.TempDir(), t.TempDir(), publicKey, run)
	if err == nil {
		t.Fatal("invalid signature should fail apply")
	}
	if started != 0 {
		t.Fatalf("child started %d time(s) after signature failure", started)
	}
}

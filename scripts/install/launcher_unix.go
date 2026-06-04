//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"time"
)

func checkVCRuntime() error {
	// VC Runtime is Windows-only, so this is a no-op on Unix
	return nil
}

func prepareCmd(cmd *exec.Cmd) {
	// No console-window hiding needed on POSIX/macOS
}

func fatalError(title, text string) {
	fmt.Printf("[FATAL] %s: %s\n", title, text)
	time.Sleep(5 * time.Second)
	os.Exit(1)
}

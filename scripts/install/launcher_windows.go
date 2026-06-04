//go:build windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"syscall"
	"time"
	"unsafe"
)

func checkVCRuntime() error {
	dll, err := syscall.LoadDLL("vcruntime140.dll")
	if err != nil {
		return fmt.Errorf("Microsoft Visual C++ Redistributable (vcruntime140.dll) is missing. Please install it.")
	}
	_ = dll.Release()
	return nil
}

func prepareCmd(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
}

func fatalError(title, text string) {
	fmt.Printf("[FATAL] %s: %s\n", title, text)
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
	time.Sleep(5 * time.Second)
	os.Exit(1)
}

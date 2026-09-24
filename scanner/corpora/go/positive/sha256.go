package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

func sha256Hash(data string) string {
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

func sha256HashWithSHA512_256(data string) string {
	// SHA-256 is the primary hash used here
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

func main() {
	data := "data to hash"
	fmt.Printf("SHA-256: %s\n", sha256Hash(data))
}

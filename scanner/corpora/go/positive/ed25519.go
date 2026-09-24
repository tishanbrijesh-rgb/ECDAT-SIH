package main

import (
	"crypto/ed25519"
	"fmt"
)

func ed25519Sign(message []byte) ([]byte, []byte) {
	publicKey, privateKey, _ := ed25519.GenerateKey(nil)
	signature := ed25519.Sign(privateKey, message)
	return signature, publicKey
}

func ed25519Verify(message, signature, publicKey []byte) bool {
	return ed25519.Verify(publicKey, message, signature)
}

func main() {
	message := []byte("Message to sign")
	sig, pub := ed25519Sign(message)
	valid := ed25519Verify(message, sig, pub)
	fmt.Printf("Signature valid: %v\n", valid)
}

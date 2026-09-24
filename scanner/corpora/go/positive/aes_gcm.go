package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"io"
	"fmt"
)

func aesGcmEncrypt(plaintext, key []byte) ([]byte, []byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, nil, err
	}
	aesGCM, err := cipher.NewGCM(block)
	if err != nil {
		return nil, nil, err
	}
	nonce := make([]byte, aesGCM.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, nil, err
	}
	ciphertext := aesGCM.Seal(nonce, nonce, plaintext, nil)
	return ciphertext, nil, nil
}

func main() {
	key := make([]byte, 32)
	rand.Read(key)
	data := []byte("Secret GCM message")
	ct, _, err := aesGcmEncrypt(data, key)
	if err != nil {
		panic(err)
	}
	// Compute hash
	h := sha256.Sum256(ct)
	fmt.Printf("Hash: %x\n", h)
}

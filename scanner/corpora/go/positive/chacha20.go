package main

import (
	"crypto/rand"
	"golang.org/x/crypto/chacha20poly1305"
	"io"
	"fmt"
)

func chacha20Encrypt(plaintext, key []byte) ([]byte, error) {
	aead, err := chacha20poly1305.NewX(key)
	if err != nil {
		return nil, err
	}
	nonce := make([]byte, aead.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, err
	}
	return aead.Seal(nonce, nonce, plaintext, nil), nil
}

func main() {
	key := make([]byte, chacha20poly1305.KeySize)
	rand.Read(key)
	data := []byte("Secret ChaCha20 message")
	ct, err := chacha20Encrypt(data, key)
	if err != nil {
		panic(err)
	}
	fmt.Printf("Ciphertext length: %d\n", len(ct))
}

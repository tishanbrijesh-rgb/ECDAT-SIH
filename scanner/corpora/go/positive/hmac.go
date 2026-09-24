package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"fmt"
)

func hmacSign(key, message []byte) []byte {
	h := hmac.New(sha256.New, key)
	h.Write(message)
	return h.Sum(nil)
}

func hmacVerify(key, message, expectedMAC []byte) bool {
	h := hmac.New(sha256.New, key)
	h.Write(message)
	return hmac.Equal(h.Sum(nil), expectedMAC)
}

func main() {
	key := []byte("my-secret-key")
	msg := []byte("important data")
	mac := hmacSign(key, msg)
	valid := hmacVerify(key, msg, mac)
	fmt.Printf("HMAC valid: %v\n", valid)
}

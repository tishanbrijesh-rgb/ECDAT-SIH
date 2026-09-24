package main

import (
	"crypto/ecdh"
	"crypto/elliptic"
	"crypto/rand"
	"fmt"
)

func ecdhKeyExchange() ([]byte, []byte) {
	privateKey, err := ecdh.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		panic(err)
	}
	publicKey := privateKey.PublicKey()
	peerPublicKey, _ := ecdh.GenerateKey(elliptic.P256(), rand.Reader)
	sharedSecret, _ := privateKey.ECDH(peerPublicKey)
	return publicKey.Bytes(), sharedSecret
}

func main() {
	pub, shared := ecdhKeyExchange()
	fmt.Printf("Shared secret length: %d\n", len(shared))
	_ = pub
}

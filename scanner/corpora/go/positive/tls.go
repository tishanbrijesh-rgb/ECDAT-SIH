package main

import (
	"crypto/tls"
	"fmt"
	"net"
)

func createTLSConn(address string) (*tls.Conn, error) {
	config := &tls.Config{
		MinVersion: tls.VersionTLS12,
		MaxVersion: tls.VersionTLS13,
	}
	conn, err := tls.Dial("tcp", address, config)
	if err != nil {
		return nil, err
	}
	state := conn.ConnectionState()
	fmt.Printf("TLS version: %x\n", state.Version)
	return conn, nil
}

func main() {
	conn, err := createTLSConn("example.com:443")
	if err != nil {
		fmt.Println(err)
		return
	}
	defer conn.Close()
}

/*
 * CryptoService.java — Java Spring Boot service using BouncyCastle crypto.
 *
 * Demonstrates: AES-GCM encryption, RSA-OAEP, ECDSA signing, SHA-256.
 */
package com.ecdat.sample;

import org.bouncycastle.jcajce.provider.symmetric.AES;
import org.bouncycastle.crypto.digests.SHA256Digest;
import org.bouncycastle.crypto.AsymmetricCipherKeyPair;
import org.springframework.security.crypto.encrypt.BouncyCastleAesGcmBytesEncryptor;
import org.springframework.security.crypto.encrypt.AesBytesEncryptor;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.SecureRandom;
import java.security.spec.ECGenParameterSpec;
import java.util.Base64;

public class CryptoService {

    private static final String AES_SECRET = "demo-secret-key-32-bytes!!!";
    private static final String AES_GCM = "AES/GCM/NoPadding";

    private final BouncyCastleAesGcmBytesEncryptor encryptor;

    public CryptoService(String password, String salt) {
        this.encryptor = new BouncyCastleAesGcmBytesEncryptor(password, salt);
    }

    public byte[] encrypt(byte[] plaintext) {
        return encryptor.encrypt(plaintext);
    }

    public byte[] decrypt(byte[] ciphertext) {
        return encryptor.decrypt(ciphertext);
    }

    public String hashWithSHA256(String input) throws Exception {
        SHA256Digest digest = new SHA256Digest();
        byte[] inputBytes = input.getBytes("UTF-8");
        digest.update(inputBytes, 0, inputBytes.length);
        byte[] output = new byte[digest.getDigestSize()];
        digest.doFinal(output, 0);
        return Base64.getEncoder().encodeToString(output);
    }

    public KeyPair generateRSAKeyPair() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        return gen.generateKeyPair();
    }

    public KeyPair generateECDSAKeyPair() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("EC");
        ECGenParameterSpec spec = new ECGenParameterSpec("secp256r1");
        gen.initialize(spec);
        return gen.generateKeyPair();
    }

    public byte[] sign(byte[] data, java.security.PrivateKey privateKey) throws Exception {
        java.security.Signature sig = java.security.Signature.getInstance("SHA256withECDSA");
        sig.initSign(privateKey);
        sig.update(data);
        return sig.sign();
    }
}

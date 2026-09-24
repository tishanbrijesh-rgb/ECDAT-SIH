#include <openssl/evp.h>
#include <openssl/aes.h>
#include <openssl/rand.h>
#include <stdio.h>
#include <string.h>

int main() {
    EVP_CIPHER_CTX *ctx;
    unsigned char key[32], iv[16], plaintext[128], ciphertext[256];
    int len, ciphertext_len;

    RAND_bytes(key, sizeof(key));
    RAND_bytes(iv, sizeof(iv));
    strcpy((char *)plaintext, "Secret AES-GCM message");

    ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, key, iv);
    EVP_EncryptUpdate(ctx, ciphertext, &len, plaintext, strlen((char *)plaintext));
    ciphertext_len = len;
    EVP_EncryptFinal_ex(ctx, ciphertext + len, &len);
    ciphertext_len += len;
    EVP_CIPHER_CTX_free(ctx);

    printf("Encrypted %d bytes\n", ciphertext_len);
    return 0;
}

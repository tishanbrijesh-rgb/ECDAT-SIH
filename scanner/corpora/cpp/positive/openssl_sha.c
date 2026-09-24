#include <openssl/evp.h>
#include <openssl/sha.h>
#include <stdio.h>
#include <string.h>

int main() {
    EVP_MD_CTX *mdctx;
    unsigned char hash[SHA256_DIGEST_LENGTH];
    char message[] = "data to hash";
    int i;

    mdctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(mdctx, EVP_sha256(), NULL);
    EVP_DigestUpdate(mdctx, message, strlen(message));
    EVP_DigestFinal_ex(mdctx, hash, NULL);
    EVP_MD_CTX_free(mdctx);

    printf("SHA-256: ");
    for (i = 0; i < SHA256_DIGEST_LENGTH; i++)
        printf("%02x", hash[i]);
    printf("\n");
    return 0;
}

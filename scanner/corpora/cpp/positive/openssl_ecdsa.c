#include <openssl/evp.h>
#include <openssl/ec.h>
#include <openssl/ecdsa.h>
#include <openssl/sha.h>
#include <stdio.h>
#include <string.h>

int main() {
    EC_KEY *eckey = EC_KEY_new_by_curve_name(NID_X9_62_prime256v1);
    EC_KEY_generate_key(eckey);

    unsigned char hash[SHA256_DIGEST_LENGTH];
    char message[] = "Message to sign";
    SHA256((unsigned char *)message, strlen(message), hash);

    ECDSA_SIG *sig = ECDSA_do_sign(hash, SHA256_DIGEST_LENGTH, eckey);
    int valid = ECDSA_do_verify(hash, SHA256_DIGEST_LENGTH, sig, eckey);
    printf("Signature valid: %d\n", valid);

    ECDSA_SIG_free(sig);
    EC_KEY_free(eckey);
    return 0;
}

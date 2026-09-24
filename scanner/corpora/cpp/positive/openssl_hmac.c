#include <openssl/hmac.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <string.h>

int main() {
    unsigned char key[] = "my-secret-key";
    unsigned char data[] = "important data";
    unsigned char result[EVP_MAX_MD_SIZE];
    unsigned int result_len;

    HMAC(EVP_sha256(), key, strlen((char *)key),
         data, strlen((char *)data), result, &result_len);

    printf("HMAC-SHA256: ");
    for (unsigned int i = 0; i < result_len; i++)
        printf("%02x", result[i]);
    printf("\n");
    return 0;
}

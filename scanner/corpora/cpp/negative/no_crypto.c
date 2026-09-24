#include <stdio.h>

int main() {
    char data[256];
    printf("Enter data: ");
    scanf("%255s", data);
    printf("You entered: %s\n", data);
    return 0;
}

/** WebCrypto API encryption example (browser-based). */
async function encryptData() {
    const encoder = new TextEncoder();
    const keyMaterial = await crypto.subtle.generateKey(
        { name: "AES-GCM", length: 256 },
        true,
        ["encrypt", "decrypt"]
    );
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const plaintext = encoder.encode("Secret WebCrypto message");
    const ciphertext = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv: iv },
        keyMaterial,
        plaintext
    );
    return new Uint8Array(ciphertext);
}

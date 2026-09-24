using System;
using System.Security.Cryptography;
using System.Text;

class AesExample {
    static void Main() {
        using (Aes aes = Aes.Create()) {
            aes.KeySize = 256;
            aes.GenerateKey();
            aes.GenerateIV();

            byte[] plaintext = Encoding.UTF8.GetBytes("Secret AES message");
            using (ICryptoTransform encryptor = aes.CreateEncryptor()) {
                byte[] ciphertext = encryptor.TransformFinalBlock(plaintext, 0, plaintext.Length);
                Console.WriteLine(Convert.ToBase64String(ciphertext));
            }
        }
    }
}

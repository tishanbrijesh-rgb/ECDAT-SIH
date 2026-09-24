using System;
using System.Security.Cryptography;
using System.Text;

class RsaExample {
    static void Main() {
        using (RSACryptoServiceProvider rsa = new RSACryptoServiceProvider) {
            RSAParameters publicKey = rsa.ExportParameters(false);
            RSAParameters privateKey = rsa.ExportParameters(true);

            byte[] plaintext = Encoding.UTF8.GetBytes("Secret RSA message");
            byte[] encrypted = rsa.Encrypt(plaintext, false);
            byte[] decrypted = rsa.Decrypt(encrypted, false);

            Console.WriteLine(Encoding.UTF8.GetString(decrypted));
        }
    }
}

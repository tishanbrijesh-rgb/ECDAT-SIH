using System;
using System.Security.Cryptography;
using System.Text;

class HmacSha256Example {
    static void Main() {
        byte[] key = Encoding.UTF8.GetBytes("my-secret-key");
        byte[] message = Encoding.UTF8.GetBytes("important data");

        using (HMACSHA256 hmac = new HMACSHA256(key)) {
            byte[] hash = hmac.ComputeHash(message);
            Console.WriteLine(BitConverter.ToString(hash).Replace("-", ""));
        }
    }
}

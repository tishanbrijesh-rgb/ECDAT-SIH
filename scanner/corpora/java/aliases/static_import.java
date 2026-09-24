import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public class StaticImportExample {
    // Uses MessageDigest through static import pattern simulation
    public static byte[] sha256(byte[] data) throws NoSuchAlgorithmException {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        return md.digest(data);
    }

    public static void main(String[] args) throws Exception {
        byte[] hash = sha256("hello world".getBytes());
        for (byte b : hash) System.out.printf("%02x", b);
        System.out.println();
    }
}

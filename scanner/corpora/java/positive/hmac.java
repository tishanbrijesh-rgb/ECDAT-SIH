import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.security.MessageDigest;

public class HmacExample {
    public static void main(String[] args) throws Exception {
        byte[] key = "my-secret-key".getBytes();
        byte[] message = "important data".getBytes();

        Mac mac = Mac.getInstance("HmacSHA256");
        SecretKeySpec keySpec = new SecretKeySpec(key, "HmacSHA256");
        mac.init(keySpec);
        byte[] digest = mac.doFinal(message);
        System.out.println(javax.xml.bind.DatatypeConverter.printHexBinary(digest));
    }
}

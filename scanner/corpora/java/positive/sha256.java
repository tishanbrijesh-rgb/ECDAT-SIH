import java.security.MessageDigest;

public class Sha256Example {
    public static void main(String[] args) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] data = "data to hash".getBytes();
        byte[] hash = md.digest(data);
        System.out.println(javax.xml.bind.DatatypeConverter.printHexBinary(hash));
    }
}

/** Variable declarations only, no cryptographic operations performed. */
import java.security.MessageDigest;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import java.security.KeyPairGenerator;

public class DeclarationOnly {
    private MessageDigest sha256;
    private Cipher aesCipher;
    private KeyGenerator keyGen;
    private KeyPairGenerator rsaGen;

    public DeclarationOnly() {
        // Only declarations; no actual crypto use
    }
}

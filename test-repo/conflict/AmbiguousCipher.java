/* Intentional assurance test: an invalid composite transformation creates contradictory encryption evidence. */
import javax.crypto.Cipher;

public final class AmbiguousCipher {
    public Cipher build() throws Exception {
        return Cipher.getInstance("RSA/AES");
    }
}

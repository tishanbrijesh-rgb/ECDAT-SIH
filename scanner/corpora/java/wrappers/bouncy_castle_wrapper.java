import org.bouncycastle.jce.provider.BouncyCastleProvider;
import java.security.Security;
import java.security.KeyPairGenerator;
import java.security.KeyPair;
import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;

public class BouncyCastleWrapper {
    static {
        Security.addProvider(new BouncyCastleProvider());
    }

    public static class AesGcm {
        private final SecretKeySpec key;
        private final byte[] iv;

        public AesGcm(byte[] keyBytes, byte[] ivBytes) {
            this.key = new SecretKeySpec(keyBytes, "AES");
            this.iv = ivBytes;
        }

        public byte[] encrypt(byte[] plaintext) throws Exception {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding", "BC");
            cipher.init(Cipher.ENCRYPT_MODE, key, new javax.crypto.spec.GCMParameterSpec(128, iv));
            return cipher.doFinal(plaintext);
        }
    }

    public static class RsaHelper {
        public static KeyPair generateKeyPair() throws Exception {
            KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA", "BC");
            kpg.initialize;
            return kpg.generateKeyPair();
        }
    }
}

package de.burggraf.mathcraft;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Only the scoped device credential is stored; the provider/parent keys never enter this app. */
@CapacitorPlugin(name = "MathCraftCredentials")
public class MathCraftCredentialsPlugin extends Plugin {
    private static final String ALIAS = "MathCraft.device-access.v1";
    private static final String PREFS = "mathcraft-private-access";

    private SecretKey key(boolean create) throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (!store.containsAlias(ALIAS)) {
            if (!create) return null;
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(ALIAS, null);
    }

    @PluginMethod
    public void set(PluginCall call) {
        String value = call.getString("value");
        if (value == null || value.length() > 2048) { call.reject("Invalid device access record"); return; }
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key(true));
            String iv = Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP);
            String data = Base64.encodeToString(cipher.doFinal(value.getBytes(StandardCharsets.UTF_8)), Base64.NO_WRAP);
            boolean saved = getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString("iv", iv).putString("data", data).commit();
            if (!saved) { call.reject("Device access storage failed"); return; }
            call.resolve();
        } catch (Exception ignored) { call.reject("Device access storage failed"); }
    }

    @PluginMethod
    public void get(PluginCall call) {
        try {
            android.content.SharedPreferences prefs = getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            String data = prefs.getString("data", null);
            SecretKey key = key(false);
            JSObject reply = new JSObject();
            if (data == null || key == null) { reply.put("value", ""); call.resolve(reply); return; }
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key,
                new GCMParameterSpec(128, Base64.decode(prefs.getString("iv", ""), Base64.NO_WRAP)));
            reply.put("value", new String(cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)), StandardCharsets.UTF_8));
            call.resolve(reply);
        } catch (Exception ignored) { call.reject("Device access unavailable; pair again"); }
    }
}

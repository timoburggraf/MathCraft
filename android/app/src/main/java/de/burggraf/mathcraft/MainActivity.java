package de.burggraf.mathcraft;

import com.getcapacitor.BridgeActivity;
import android.os.Bundle;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(MathCraftCredentialsPlugin.class);
        super.onCreate(savedInstanceState);
    }
}

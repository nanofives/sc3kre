// SetGnuV2Demangler.java - pre-script for the Loki Linux demo imports (ghidra_headless.ps1 -Linux).
//
// The Loki SC3U demo libraries were built with GCC 2.95, whose mangling ("Apply__19cSC3AgDeveloperRuleRC14...")
// only the DEPRECATED GNU demangler (demangler_gnu_v2_24, format GNU) understands. Ghidra's default AUTO/modern
// path leaves these names mangled (measured on libSimRCI.so, 2026-10-05). Run as -preScript so auto-analysis
// demangles and applies the recovered signatures (argument types) to every exported function.
import ghidra.app.script.GhidraScript;
import java.util.Map;

public class SetGnuV2Demangler extends GhidraScript {
    @Override
    public void run() throws Exception {
        Map<String, String> opts = getCurrentAnalysisOptionsAndValues(currentProgram);
        for (String k : opts.keySet()) {
            if (k.startsWith("Demangler GNU")) println("BEFORE " + k + " = " + opts.get(k));
        }
        setAnalysisOption(currentProgram, "Demangler GNU.Use Deprecated Demangler", "true");
        setAnalysisOption(currentProgram, "Demangler GNU.Demangler Format", "GNU");
        setAnalysisOption(currentProgram, "Demangler GNU.Demangle Only Known Mangled Symbols", "false");
        // Switch-table recovery is off for these imports. Measured 2026-10-05 on sc3u_demo.x86: 30+ minutes in
        // DecompilerSwitchAnalyzer ("hit non-returning function, restarting ... later"), decompilers respawning
        // every few seconds at ~0 CPU, no completion. The matcher (linux_match.py) uses strings, constants, direct
        // callees and vtables, none of which depend on jump-table recovery.
        if (opts.containsKey("Decompiler Switch Analysis")) {
            setAnalysisOption(currentProgram, "Decompiler Switch Analysis", "false");
        } else {
            println("WARN no analyzer named 'Decompiler Switch Analysis'; switch-like options:");
            for (String k : opts.keySet()) if (k.toLowerCase().contains("switch")) println("  " + k);
        }
        opts = getCurrentAnalysisOptionsAndValues(currentProgram);
        for (String k : opts.keySet()) {
            if (k.startsWith("Demangler GNU") || k.equals("Decompiler Switch Analysis"))
                println("AFTER  " + k + " = " + opts.get(k));
        }
    }
}

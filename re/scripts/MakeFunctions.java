// MakeFunctions.java — force-create functions at addresses Ghidra's auto-analysis left as bare
// labels, then the next -Export picks up their bodies.
//
// WHY: GZCOM factory stubs are 3-line `operator_new(size) + ctor` blobs that are only ever
// reached through a registration table (a DATA reference), so auto-analysis often leaves them as
// LAB_* with no function. They are then invisible to the text export — in SIMUI.DLL that hid 12
// of the module's 40 registered classes.
//
// This script MUTATES the program, so it must run WITHOUT -readOnly:
//   analyzeHeadless <projdir> SC3_SIMUI -process SIMUI.DLL -noanalysis \
//       -scriptPath re\scripts -postScript MakeFunctions.java 0x1006ac73 0x1001a021 ...
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.BufferedReader;
import java.io.FileReader;
import java.util.ArrayList;
import java.util.List;

public class MakeFunctions extends GhidraScript {

    /** Args are either literal addresses, or "@path" to a file with one address per line. */
    private List<String> collectArgs() throws Exception {
        List<String> out = new ArrayList<>();
        for (String a : getScriptArgs()) {
            if (a.startsWith("@")) {
                try (BufferedReader r = new BufferedReader(new FileReader(a.substring(1)))) {
                    String line;
                    while ((line = r.readLine()) != null) {
                        line = line.trim();
                        if (!line.isEmpty() && !line.startsWith("#")) out.add(line);
                    }
                }
            } else {
                out.add(a);
            }
        }
        return out;
    }

    public void run() throws Exception {
        int made = 0, existed = 0, failed = 0;
        for (String arg : collectArgs()) {
            Address a = toAddr(Long.parseLong(arg.replace("0x", ""), 16));
            Function f = getFunctionAt(a);
            if (f != null) {
                println("  exists  " + a + "  " + f.getName());
                existed++;
                continue;
            }
            if (getInstructionAt(a) == null) {
                disassemble(a);
            }
            f = createFunction(a, null);
            if (f == null) {
                println("  FAILED  " + a + " — could not create a function here");
                failed++;
            } else {
                println("  created " + a + "  " + f.getName()
                        + "  " + f.getBody().getNumAddresses() + " bytes");
                made++;
            }
        }
        println("MakeFunctions: created " + made + ", already existed " + existed + ", failed " + failed);
    }
}

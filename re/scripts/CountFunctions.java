// Headless post-script: report SC3U.exe function-count breakdown + dump functions.csv
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;

public class CountFunctions extends GhidraScript {
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        int total = 0, thunks = 0, external = 0, real = 0, defaultNamed = 0;
        for (Function f : fm.getFunctions(true)) {
            total++;
            if (f.isThunk()) thunks++;
            if (f.isExternal()) external++;
            if (!f.isThunk() && !f.isExternal()) real++;
            String n = f.getName();
            if (n.startsWith("FUN_") || n.startsWith("thunk_FUN_")) defaultNamed++;
        }
        println("=== SC3U COUNT ===");
        println("TOTAL_FUNCTIONS=" + total);
        println("THUNKS=" + thunks);
        println("EXTERNAL=" + external);
        println("REAL_DEFINED=" + real);
        println("DEFAULT_NAMED_FUN=" + defaultNamed);
        println("NAMED_MEANINGFUL=" + (real - (defaultNamed)));

        String[] args = getScriptArgs();
        if (args.length > 0) {
            java.io.PrintWriter w = new java.io.PrintWriter(args[0]);
            w.println("address,name,size,isThunk,isExternal,namespace");
            for (Function f : fm.getFunctions(true)) {
                w.println("0x" + f.getEntryPoint() + "," + f.getName().replace(",", ";") + "," +
                        f.getBody().getNumAddresses() + "," + f.isThunk() + "," + f.isExternal() + "," +
                        f.getParentNamespace().getName().replace(",", ";"));
            }
            w.close();
            println("WROTE_CSV=" + args[0]);
        }
    }
}

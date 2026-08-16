// XrefProbe.java — headless "live Ghidra" xref probe (what the text export can't show).
// Prints all references TO each target address (call + DATA/pointer refs), with the
// containing function, so we can resolve indirect/static-init dispatch and map the
// GZCOM AgentTypes registry.
//
// Usage: -postScript XrefProbe.java 0x0040b761 0x0040cb70 0x0040cc08 ...
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;

public class XrefProbe extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (String a : args) {
            Address tgt = toAddr(Long.parseLong(a.replace("0x", ""), 16));
            println("==== refs TO " + tgt + " ====");
            int n = 0;
            for (Reference r : rm.getReferencesTo(tgt)) {
                Address from = r.getFromAddress();
                MemoryBlock blk = currentProgram.getMemory().getBlock(from);
                Function f = getFunctionContaining(from);
                String where = (f != null) ? f.getName() + " (" + f.getEntryPoint() + ")"
                                            : "<no func> in " + (blk != null ? blk.getName() : "?");
                println(String.format("  from %s  %-14s  %s", from, r.getReferenceType(), where));
                n++;
            }
            if (n == 0) println("  (none)");
            println("  total refs: " + n);
        }
    }
}

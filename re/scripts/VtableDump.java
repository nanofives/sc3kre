// VtableDump.java — print the contents of a vtable, slot by slot.
//
// The text exports (re\ghidra_export*\) contain function BODIES only, so vtables — which are
// data — are invisible to grep. This is the companion to VtableProbe.java: give it a vtable
// base address and it lists every slot with its target function, size and any name.
//
// Stops at the first slot that is not a pointer into an executable block (the usual end of a
// vtable), or after -maxslots.
//
// Usage:
//   pwsh re\scripts\ghidra_headless.ps1 -Module SIMUTIL.DLL -Script VtableDump.java \
//        -ScriptArgs "0x10020c48 0x10020ea8"
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.Symbol;

public class VtableDump extends GhidraScript {

    private static final int PTR = 4;
    private static final int MAX_SLOTS = 256;

    public void run() throws Exception {
        ReferenceManager rm = currentProgram.getReferenceManager();

        for (String arg : getScriptArgs()) {
            Address base = toAddr(Long.parseLong(arg.replace("0x", ""), 16));
            Symbol bs = getSymbolAt(base);
            println("");
            println("======== vtable " + base + (bs != null ? " (" + bs.getName() + ")" : "") + " ========");

            // who installs it
            for (Reference r : rm.getReferencesTo(base)) {
                MemoryBlock b = currentProgram.getMemory().getBlock(r.getFromAddress());
                if (b != null && b.isExecute()) {
                    Function f = getFunctionContaining(r.getFromAddress());
                    println("  installed by: " + (f != null ? f.getName() + " (" + f.getEntryPoint() + ")"
                                                            : r.getFromAddress().toString()));
                }
            }

            for (int i = 0; i < MAX_SLOTS; i++) {
                Address slotAddr = base.add((long) i * PTR);
                long v;
                try {
                    v = getInt(slotAddr) & 0xFFFFFFFFL;
                } catch (Exception e) {
                    println(String.format("  slot %-3d +0x%-4x  <unreadable> — stop", i, i * PTR));
                    break;
                }
                if (v == 0) {
                    println(String.format("  slot %-3d +0x%-4x  NULL", i, i * PTR));
                    continue;
                }
                Address t = toAddr(v);
                MemoryBlock tb = currentProgram.getMemory().getBlock(t);
                if (tb == null || !tb.isExecute()) {
                    println(String.format("  slot %-3d +0x%-4x  %s  <not code> — end of vtable",
                                          i, i * PTR, t));
                    break;
                }
                Function f = getFunctionAt(t);
                if (f == null) {
                    println(String.format("  slot %-3d +0x%-4x  %s  <no function defined>", i, i * PTR, t));
                    continue;
                }
                println(String.format("  slot %-3d +0x%-4x  %s  %-28s %d bytes",
                                      i, i * PTR, t, f.getName(), f.getBody().getNumAddresses()));
            }
        }
    }
}

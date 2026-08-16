// VtableProbe.java — resolve indirect dispatch that the text export cannot show.
//
// For each target FUNCTION address, find every DATA reference to it (i.e. every vtable slot
// holding its address). For each hit, walk backwards over the contiguous run of
// function-pointers to find the vtable START, report the target's SLOT INDEX, and then list
// the code references to that vtable start — those are the constructors that install it.
//
// This is the probe that answers "which class owns this method?" for a stripped C++ binary.
//
// Usage:
//   pwsh re\scripts\ghidra_headless.ps1 -Module SIMUTIL.DLL -Script VtableProbe.java \
//        -ScriptArgs "0x10004979 0x1000c8e2"
//
// Output per target:
//   vtable <start> slot <n> (+0xNN)   installed by: <ctor> ...
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.Symbol;

public class VtableProbe extends GhidraScript {

    private static final int PTR = 4;          // 32-bit targets
    private static final int MAX_SLOTS = 512;  // sanity bound on a vtable walk

    /** true if the dword stored at `a` is the entry point of a defined function */
    private boolean holdsFunctionPointer(Address a) {
        try {
            long v = getInt(a) & 0xFFFFFFFFL;
            if (v == 0) return false;
            Address t = toAddr(v);
            MemoryBlock b = currentProgram.getMemory().getBlock(t);
            if (b == null || !b.isExecute()) return false;
            return getFunctionAt(t) != null;
        } catch (Exception e) {
            return false;
        }
    }

    private String nameOf(Address a) {
        Function f = getFunctionContaining(a);
        if (f != null) return f.getName() + " (" + f.getEntryPoint() + ")";
        Symbol s = getSymbolAt(a);
        MemoryBlock b = currentProgram.getMemory().getBlock(a);
        return (s != null ? s.getName() + " " : "") + "<data" +
               (b != null ? " in " + b.getName() : "") + ">";
    }

    public void run() throws Exception {
        ReferenceManager rm = currentProgram.getReferenceManager();

        for (String arg : getScriptArgs()) {
            Address target = toAddr(Long.parseLong(arg.replace("0x", ""), 16));
            println("");
            println("======== target " + target + "  " + nameOf(target) + " ========");

            int hits = 0;
            for (Reference r : rm.getReferencesTo(target)) {
                Address from = r.getFromAddress();
                MemoryBlock blk = currentProgram.getMemory().getBlock(from);
                boolean isData = (blk != null && !blk.isExecute());
                if (!isData) continue;                   // code refs are ordinary calls
                if (!holdsFunctionPointer(from)) continue;

                hits++;
                // The vtable start is not simply the head of the contiguous function-pointer
                // run: MSVC emits RTTI pointers, nulls and pure-call stubs inside a vtable, and
                // the run walk stops at those. What reliably marks the start is that the ctor
                // takes its ADDRESS — so search backwards for the nearest preceding address
                // that has a code reference, and treat that as the vtable base.
                Address base = null;
                int slot = -1;
                for (int i = 0; i <= MAX_SLOTS; i++) {
                    Address cand = from.subtract((long) i * PTR);
                    boolean referencedFromCode = false;
                    for (Reference vr : rm.getReferencesTo(cand)) {
                        MemoryBlock vb = currentProgram.getMemory().getBlock(vr.getFromAddress());
                        if (vb != null && vb.isExecute()) { referencedFromCode = true; break; }
                    }
                    if (referencedFromCode) { base = cand; slot = i; break; }
                }

                if (base == null) {
                    println("  slot at " + from + " — no code-referenced vtable base within "
                            + (MAX_SLOTS * PTR) + " bytes [UNCERTAIN]");
                    continue;
                }

                Symbol bs = getSymbolAt(base);
                println(String.format("  vtable %s%s  slot %d (+0x%x)",
                                      base, (bs != null ? " (" + bs.getName() + ")" : ""),
                                      slot, slot * PTR));

                for (Reference vr : rm.getReferencesTo(base)) {
                    Address vf = vr.getFromAddress();
                    MemoryBlock vb = currentProgram.getMemory().getBlock(vf);
                    if (vb != null && vb.isExecute()) {
                        println("      installed by: " + nameOf(vf) + "  [" + vr.getReferenceType() + "]");
                    }
                }
            }

            if (hits == 0) {
                println("  no vtable slot holds this address — it is not a virtual method,");
                println("  or the pointer table was not recognised as data.");
            } else {
                println("  vtable slots found: " + hits);
            }
        }
    }
}

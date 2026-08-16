// FindVtables.java — locate vtable-shaped pointer arrays in a module and name their installers.
//
// WHY: vtables live in .rdata, so the decompiled text exports cannot see them at all. When an
// object is only ever reached through virtual calls (the usual GZCOM shape), the only way to
// identify its class is to find the vtable whose slot layout matches the calls you observed.
//
// Example: SIMSPR 0x1001de49 calls QueryInterface(0x487534f) on its param_1 and the resulting
// interface's slot 3. Separately FUN_1001e869 calls param_1->vt+0x1a8 / +0x1ac / +0x38 / +0x3c,
// so param_1's vtable has at least 108 slots. This script finds the candidates.
//
// Args: [minSlots] [requiredSlotOffsetHex ...]
//   minSlots  - only report vtables with at least this many consecutive code pointers (default 8)
//   required  - optional byte offsets that MUST be present (i.e. minSlots > offset/4)
//
// Usage:
//   pwsh re\scripts\ghidra_headless.ps1 -Module SIMSPR.DLL -Script FindVtables.java \
//        -ScriptArgs "100 0x1ac 0xc8"
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;

import java.util.ArrayList;
import java.util.List;

public class FindVtables extends GhidraScript {

    private static final int PTR = 4;

    public void run() throws Exception {
        String[] args = getScriptArgs();
        int minSlots = args.length > 0 ? Integer.parseInt(args[0]) : 8;
        List<Integer> required = new ArrayList<>();
        for (int i = 1; i < args.length; i++) {
            required.add(Integer.parseInt(args[i].replace("0x", ""), 16));
        }

        ReferenceManager rm = currentProgram.getReferenceManager();
        println("scanning for vtables with >= " + minSlots + " slots"
                + (required.isEmpty() ? "" : " covering offsets " + args[1]
                   + (args.length > 2 ? " .." : "")));

        int found = 0;
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (b.isExecute() || !b.isInitialized()) continue;      // .rdata/.data only
            Address a = b.getStart();
            while (a != null && a.compareTo(b.getEnd()) < 0) {
                int slots = countSlots(a, b);
                if (slots >= minSlots) {
                    boolean ok = true;
                    for (int off : required) {
                        if (off / PTR >= slots) { ok = false; break; }
                    }
                    if (ok) {
                        found++;
                        println("");
                        println("==== " + a + "   " + slots + " slots ====");
                        for (Reference r : rm.getReferencesTo(a)) {
                            MemoryBlock fb = currentProgram.getMemory().getBlock(r.getFromAddress());
                            if (fb != null && fb.isExecute()) {
                                Function f = getFunctionContaining(r.getFromAddress());
                                println("   installed by " + (f != null
                                        ? f.getName() + " (" + f.getEntryPoint() + ")"
                                        : r.getFromAddress().toString()));
                            }
                        }
                        for (int off : required) {
                            Address slot = a.add(off);
                            Function f = getFunctionAt(toAddr(getInt(slot) & 0xFFFFFFFFL));
                            println(String.format("   +0x%-4x = %s", off,
                                    f != null ? f.getName() + " (" + f.getEntryPoint() + ")"
                                              : "<no function>"));
                        }
                    }
                    a = a.add((long) slots * PTR);
                } else {
                    a = a.add(PTR);
                }
            }
        }
        println("");
        println(found + " candidate vtable(s)");
    }

    /** Number of consecutive dwords at `a` that point into an executable block. */
    private int countSlots(Address a, MemoryBlock b) {
        int n = 0;
        try {
            while (a.add((long) n * PTR).compareTo(b.getEnd()) < 0) {
                long v = getInt(a.add((long) n * PTR)) & 0xFFFFFFFFL;
                if (v == 0) break;
                MemoryBlock tb = currentProgram.getMemory().getBlock(toAddr(v));
                if (tb == null || !tb.isExecute()) break;
                n++;
            }
        } catch (Exception e) {
            // fell off the block or unreadable — treat as the end of the run
        }
        return n;
    }
}

// DumpDisasm.java — print the raw instruction listing of a function.
//
// WHY THIS EXISTS: the text exports (re\ghidra_export*\) hold DECOMPILED C, which is useless
// when the decompiler loses the calling convention — e.g. SIMSPR 0x1001de49, whose body comes
// out with `puRam00000000`, `extraout_ECX` and `unaff_ESI` and whose tail is unreadable. The
// disassembly is always correct even when the decompilation is not, so this dumps it directly.
//
// For each instruction it resolves CALL/JMP targets to function names, and annotates any
// reference to data (globals, vtables, string literals) with the symbol and, for small scalars,
// the value. That makes indirect `call [reg+0x50]` sites legible: you get the register-relative
// offset, and the preceding loads that set the register up.
//
// Usage:
//   pwsh re\scripts\ghidra_headless.ps1 -Module SIMSPR.DLL -Script DumpDisasm.java \
//        -ScriptArgs "0x1001de49 0x10012d91"
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;

public class DumpDisasm extends GhidraScript {

    public void run() throws Exception {
        for (String arg : getScriptArgs()) {
            Address entry = toAddr(Long.parseLong(arg.replace("0x", ""), 16));
            Function f = getFunctionContaining(entry);
            println("");
            println("======== " + arg + (f != null ? "  " + f.getName() : "  <no function>") + " ========");
            if (f == null) {
                println("  no function contains this address");
                continue;
            }
            println("  entry " + f.getEntryPoint() + "   " + f.getBody().getNumAddresses()
                    + " bytes   signature: " + f.getSignature());
            println("  calling convention: " + f.getCallingConventionName());
            println("");

            InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
            while (it.hasNext()) {
                Instruction ins = it.next();
                StringBuilder sb = new StringBuilder();
                sb.append(String.format("  %s  %-44s", ins.getAddress(), ins.toString()));

                // Resolve every reference this instruction makes.
                for (Reference r : ins.getReferencesFrom()) {
                    Address t = r.getToAddress();
                    if (t == null) continue;
                    Function tf = getFunctionAt(t);
                    if (tf != null) {
                        sb.append("  -> ").append(tf.getName());
                        continue;
                    }
                    Symbol s = getSymbolAt(t);
                    MemoryBlock b = currentProgram.getMemory().getBlock(t);
                    if (s != null) {
                        sb.append("  -> ").append(s.getName());
                    } else if (b != null) {
                        sb.append("  -> ").append(t);
                    }
                    // Annotate readable data with its defined value / string content.
                    if (b != null && !b.isExecute()) {
                        Data dat = getDataAt(t);
                        if (dat != null) {
                            Object v = dat.getValue();
                            if (v != null) sb.append(" = ").append(v);
                        }
                    }
                }
                String c = ins.getComment(CodeUnit.EOL_COMMENT);
                if (c != null) sb.append("   ; ").append(c);
                println(sb.toString());
            }
        }
    }
}

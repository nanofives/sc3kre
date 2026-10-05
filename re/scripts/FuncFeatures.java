// FuncFeatures.java - dump compiler-independent per-function features for cross-build matching.
//
// Used by re/tools/linux_match.py to pair SC3U Windows (MSVC) functions with their Loki Linux demo (GCC 2.95)
// counterparts. Features chosen because they survive a compiler change:
//   strings  - text of every string the function references (data refs to defined strings)
//   consts   - 32-bit scalar operands >= 0x10000 that are not addresses inside the program (IIDs, magic,
//              float bit patterns), so "0x82e0074c"-style GZCOM ids
//   callees  - entry points of called functions (for call-graph propagation)
// Output TSV (one row per non-thunk, non-external function):
//   entry \t name \t size \t callees(;) \t strings(\x1f) \t consts(;)
// Args: <out.tsv>
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class FuncFeatures extends GhidraScript {
    @Override
    public void run() throws Exception {
        String out = getScriptArgs()[0];
        Listing L = currentProgram.getListing();
        Memory mem = currentProgram.getMemory();
        ReferenceManager rm = currentProgram.getReferenceManager();
        PrintWriter w = new PrintWriter(new OutputStreamWriter(new FileOutputStream(out), "UTF-8"));
        int n = 0;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (monitor.isCancelled()) break;
            if (f.isThunk() || f.isExternal()) continue;
            TreeSet<String> callees = new TreeSet<>(), strs = new TreeSet<>(), consts = new TreeSet<>();
            StringBuilder shape = new StringBuilder();
            for (Function c : f.getCalledFunctions(monitor)) {
                Function t = c.isThunk() ? c.getThunkedFunction(true) : c;
                // externals keep their namespace: on Linux the GZ/RZ framework is imported (cRZRefCount::AddRef,
                // cRZString::..., RandomUint32Uniform) and a bare "AddRef" would conflate every class
                callees.add(t == null ? c.getName(true) : (t.isExternal() ? "EXT:" + t.getName(true) : t.getEntryPoint().toString()));
            }
            for (Instruction ins : L.getInstructions(f.getBody(), true)) {
                shape.append(ins.getMnemonicString());
                for (int i = 0; i < ins.getNumOperands(); i++) {
                    shape.append('|');
                    for (Object o : ins.getOpObjects(i)) {
                        if (o instanceof Scalar) {
                            long v = ((Scalar) o).getUnsignedValue() & 0xffffffffL;
                            Address a = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(v);
                            shape.append(mem.contains(a) ? "A" : Long.toHexString(v));
                        } else if (o instanceof Address) {
                            shape.append("A");
                        } else {
                            shape.append(o.toString());
                        }
                        shape.append(',');
                    }
                }
                shape.append(';');
                for (Reference r : ins.getReferencesFrom()) {
                    Data d = L.getDefinedDataAt(r.getToAddress());
                    if (d != null && d.hasStringValue()) {
                        Object v = d.getValue();
                        if (v != null && v.toString().length() >= 3) strs.add(v.toString().replace('\t', ' ').replace('\n', ' ').replace('\u001f', ' '));
                    }
                }
                for (int i = 0; i < ins.getNumOperands(); i++) {
                    for (Object o : ins.getOpObjects(i)) {
                        if (!(o instanceof Scalar)) continue;
                        long v = ((Scalar) o).getUnsignedValue() & 0xffffffffL;
                        if (v < 0x10000 || v == 0xffffffffL || (v & 0xffffff00L) == 0xffffff00L) continue;
                        Address a = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(v);
                        if (mem.contains(a)) continue;   // an address, not a constant
                        consts.add(String.format("0x%08x", v));
                    }
                }
            }
            // mhash: MD5 of the instruction stream with addresses masked. Identical for the copies of statically
            // linked GZ/RZ framework code that every SC3 DLL carries at a different address.
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("MD5");
            StringBuilder hx = new StringBuilder();
            for (byte b : md.digest(shape.toString().getBytes("UTF-8"))) hx.append(String.format("%02x", b));
            w.println(f.getEntryPoint() + "\t" + f.getName(true) + "\t" + f.getBody().getNumAddresses() + "\t"
                + String.join(";", callees) + "\t" + String.join("\u001f", strs) + "\t" + String.join(";", consts)
                + "\t" + hx);
            n++;
        }
        w.close();
        println("FEATURES " + n + " functions -> " + out);
    }
}

// DumpElfVtables.java - list every named vtable in a Loki Linux demo library with its resolved slots.
//
// GCC 2.95 names vtables "_vt.<len><Class>" (secondary bases: "_vt.<len><Class>.<len><Base>"); Ghidra's GNU v2
// demangler may render them as "<Class>::virtual table" / "vtable". Pointers are read AFTER Ghidra applied the
// .rel.dyn relocations, so R_386_32 slots (stored as 0 in the file) resolve to their targets.
// Output TSV: vt_address \t vt_symbol \t slot_entries(;)   (a slot that is not a function entry -> "-")
// Reading stops at the first dword that is neither a function entry nor 0 (GCC slot 0/1 can be 0/typeinfo).
// Args: <out.tsv>
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class DumpElfVtables extends GhidraScript {
    @Override
    public void run() throws Exception {
        PrintWriter w = new PrintWriter(new OutputStreamWriter(new FileOutputStream(getScriptArgs()[0]), "UTF-8"));
        Memory mem = currentProgram.getMemory();
        FunctionManager fm = currentProgram.getFunctionManager();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        int nvt = 0;
        for (Symbol s : currentProgram.getSymbolTable().getAllSymbols(true)) {
            String n = s.getName(true);
            if (!(n.startsWith("_vt.") || n.startsWith("_vt$") || n.contains("virtual_table") || n.contains("vtable")
                  || n.contains("virtual table"))) continue;
            Address a = s.getAddress();
            if (!mem.contains(a)) continue;
            List<String> slots = new ArrayList<>();
            for (int i = 0; i < 400; i++) {
                Address p = a.add(4L * i);
                long v;
                try { v = mem.getInt(p) & 0xffffffffL; } catch (Exception e) { break; }  // bss / unreadable
                Function f = null;
                try { f = v == 0 ? null : fm.getFunctionAt(sp.getAddress(v)); } catch (Exception e) { }
                if (f != null) { slots.add(f.getEntryPoint().toString()); continue; }
                if (i < 2) { slots.add("-"); continue; }   // GCC 2.95: slot 0 = this-offset, slot 1 = typeinfo
                break;
            }
            w.println(a + "\t" + n + "\t" + String.join(";", slots));
            nvt++;
        }
        w.close();
        println("VTABLES " + nvt);
    }
}

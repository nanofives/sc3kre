// ExportAllDecomp.java — SimCity 3000 RE
// Headless post-script: exports the FULL analysis as greppable text into re/ghidra_export/.
// This is the "no-MCP" offline model: any Claude (incl. claude2 / worker, Read+Grep only)
// answers "what does the original do?" by grepping these files — no live Ghidra, no locking.
//
//   functions/0x<addr>_<Name>.c   one decompiled C file per function
//   symbols.csv                    address,name,size,isThunk,isLibrary,namespace
//   globals.csv                    address,name,datatype
//   strings.csv                    address,string
//   EXPORT_INFO.txt                anchor + counts + timestamp
//
// Usage (via scripts/ghidra_headless.ps1 -Export):
//   analyzeHeadless <proj> SC3 -process SC3U.exe -noanalysis -readOnly \
//       -scriptPath scripts -postScript ExportAllDecomp.java <exportDir>
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Data;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.mem.MemoryBlock;
import java.io.File;
import java.io.PrintWriter;

public class ExportAllDecomp extends GhidraScript {
    public void run() throws Exception {
        String[] a = getScriptArgs();
        String outRoot = (a.length > 0) ? a[0] : "re_ghidra_export";
        File fnDir = new File(outRoot, "functions");
        fnDir.mkdirs();

        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);

        PrintWriter sym = new PrintWriter(new File(outRoot, "symbols.csv"));
        sym.println("address,name,size,isThunk,isLibrary,namespace");

        int n = 0, ok = 0, fail = 0;
        for (Function f : fm.getFunctions(true)) {
            n++;
            String addr = "0x" + f.getEntryPoint();
            String name = f.getName().replace(",", ";");
            boolean lib = f.getName().matches("^(_|__|@).*") || !f.getName().startsWith("FUN_") && !f.isThunk() && f.getSymbol() != null && f.getSymbol().getSource().toString().equals("IMPORTED");
            sym.println(addr + "," + name + "," + f.getBody().getNumAddresses() + "," +
                        f.isThunk() + "," + lib + "," + f.getParentNamespace().getName().replace(",", ";"));
            if (monitor.isCancelled()) break;
            try {
                DecompileResults r = dec.decompileFunction(f, 60, monitor);
                String c = (r != null && r.decompileCompleted()) ? r.getDecompiledFunction().getC()
                                                                 : "// DECOMPILE FAILED @ " + addr + "\n";
                File cf = new File(fnDir, f.getEntryPoint() + "_" + sanitize(f.getName()) + ".c");
                PrintWriter w = new PrintWriter(cf);
                w.println("// " + addr + "  " + f.getName() + "  (" + f.getBody().getNumAddresses() + " bytes)");
                w.print(c);
                w.close();
                ok++;
            } catch (Exception e) { fail++; }
            if (n % 500 == 0) println("decomp " + n + " ... (ok=" + ok + " fail=" + fail + ")");
        }
        sym.close();

        // globals + strings
        PrintWriter gl = new PrintWriter(new File(outRoot, "globals.csv"));
        gl.println("address,name,datatype");
        SymbolTable st = currentProgram.getSymbolTable();
        for (Symbol s : st.getDefinedSymbols()) {
            if (s.getSymbolType().toString().equals("Label") && s.getAddress().isMemoryAddress()) {
                Data d = getDataAt(s.getAddress());
                String dt = (d != null) ? d.getDataType().getName() : "";
                gl.println("0x" + s.getAddress() + "," + s.getName().replace(",", ";") + "," + dt);
            }
        }
        gl.close();

        PrintWriter strf = new PrintWriter(new File(outRoot, "strings.csv"));
        strf.println("address,string");
        for (Data d : currentProgram.getListing().getDefinedData(true)) {
            if (d.hasStringValue()) {
                Object v = d.getValue();
                if (v != null) strf.println("0x" + d.getAddress() + ",\"" +
                        v.toString().replace("\"", "'").replace("\n", "\\n").replace("\r", "") + "\"");
            }
        }
        strf.close();

        PrintWriter info = new PrintWriter(new File(outRoot, "EXPORT_INFO.txt"));
        info.println(currentProgram.getName() + " — Ghidra full export");
        info.println("program        = " + currentProgram.getName());
        info.println("sha256         = " + currentProgram.getExecutableSHA256());
        info.println("image_base     = " + currentProgram.getImageBase());
        info.println("functions      = " + n + "  (decomp ok=" + ok + " fail=" + fail + ")");
        info.close();

        dec.dispose();
        println("EXPORT DONE: functions=" + n + " ok=" + ok + " fail=" + fail + " -> " + outRoot);
    }

    private String sanitize(String s) {
        String x = s.replaceAll("[^A-Za-z0-9_]", "_");
        return x.length() > 80 ? x.substring(0, 80) : x;
    }
}

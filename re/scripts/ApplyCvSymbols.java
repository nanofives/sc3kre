// ApplyCvSymbols.java - name SC3U.exe from the retail CD's CodeView symbols (re/tools/cv_symbols.py output).
//
// The retail SC3U.ICD (2.0.949) is the same build as original/SC3U.exe (.text differs in 10 bytes, same RVAs), so its
// NB11 symbols apply 1:1. Background: re/analysis/CV_SYMBOLS.md.
//
// For every row of cv_functions.tsv:
//   * thunks are left alone (Ghidra already names imports);
//   * no function at the address and the address is not inside another function -> disassemble + create one;
//     inside another function -> logged as INSIDE, not split (needs a look first);
//   * mangled C++ name -> add it as an IMPORTED label, then DemanglerCmd (namespace + name + signature);
//   * otherwise (C name / static proc) -> name + class namespace from the undecorated name.
// For cv_data.tsv: labels (vftables, statics, globals). `??_C@` string literals and `__imp_` IAT slots are skipped.
//
// MUTATES the program: run without -readOnly, i.e.
//   pwsh re\scripts\ghidra_headless.ps1 -Script ApplyCvSymbols.java -Write -Args "<cv_functions.tsv> <cv_data.tsv> <log.tsv>"
import ghidra.app.cmd.label.DemanglerCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Namespace;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.symbol.SymbolUtilities;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;

public class ApplyCvSymbols extends GhidraScript {

    private TreeMap<String, Integer> counts = new TreeMap<>();
    private PrintWriter log;

    private void count(String k) { counts.merge(k, 1, Integer::sum); }

    private List<String[]> readTsv(String path) throws Exception {
        List<String[]> rows = new ArrayList<>();
        try (BufferedReader r = new BufferedReader(new FileReader(path))) {
            String line = r.readLine(); // header
            while ((line = r.readLine()) != null) {
                if (!line.isEmpty()) rows.add(line.split("\t", -1));
            }
        }
        return rows;
    }

    /** "A<x::y>::B::c" -> ["A<x::y>", "B", "c"], splitting only on top-level '::'. */
    private static List<String> splitQualified(String s) {
        List<String> out = new ArrayList<>();
        int depth = 0, start = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '<' || c == '(') depth++;
            else if (c == '>' || c == ')') depth--;
            else if (depth == 0 && c == ':' && i + 1 < s.length() && s.charAt(i + 1) == ':') {
                out.add(s.substring(start, i));
                start = i + 2;
                i++;
            }
        }
        out.add(s.substring(start));
        return out;
    }

    private Namespace namespaceFor(List<String> parts) throws Exception {
        SymbolTable st = currentProgram.getSymbolTable();
        Namespace ns = currentProgram.getGlobalNamespace();
        for (int i = 0; i < parts.size() - 1; i++) {
            String p = SymbolUtilities.replaceInvalidChars(parts.get(i), true);
            Namespace n = st.getNamespace(p, ns);
            if (n == null) n = st.createClass(ns, p, SourceType.IMPORTED);
            ns = n;
        }
        return ns;
    }

    private static String plainCName(String n) {
        // _WinMain@16 -> WinMain ; _foo -> foo ; @fast@8 -> fast
        String x = n;
        if (x.startsWith("_") || x.startsWith("@")) x = x.substring(1);
        int at = x.lastIndexOf('@');
        if (at > 0 && x.substring(at + 1).matches("\\d+")) x = x.substring(0, at);
        return x;
    }

    private boolean nameByParts(Address a, String qualified, boolean isFunction) throws Exception {
        List<String> parts = splitQualified(qualified);
        String leaf = SymbolUtilities.replaceInvalidChars(parts.get(parts.size() - 1), true);
        Namespace ns = namespaceFor(parts);
        if (isFunction) {
            Function f = getFunctionAt(a);
            f.setParentNamespace(ns);
            f.setName(leaf, SourceType.IMPORTED);
        } else {
            Symbol s = currentProgram.getSymbolTable().createLabel(a, leaf, ns, SourceType.IMPORTED);
            s.setPrimary();
        }
        return true;
    }

    private boolean demangle(Address a, String mangled) {
        try {
            DemanglerCmd cmd = new DemanglerCmd(a, mangled);
            return cmd.applyTo(currentProgram, monitor);
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 3) throw new IllegalArgumentException("args: cv_functions.tsv cv_data.tsv log.tsv");
        log = new PrintWriter(args[2], "UTF-8");
        log.println("va\tkind\taction\tghidra_before\tghidra_after");
        FunctionManager fm = currentProgram.getFunctionManager();
        SymbolTable st = currentProgram.getSymbolTable();

        // ---- functions
        for (String[] r : readTsv(args[0])) {
            if (monitor.isCancelled()) break;
            Address a = toAddr(r[0]);
            String name = r[3], mangled = r[4], alt = r[6];
            Function f = fm.getFunctionAt(a);
            String before = f == null ? "" : f.getName(true);
            String action;
            if (f == null) {
                Function owner = fm.getFunctionContaining(a);
                if (owner != null) {
                    log.println(r[0] + "\tfun\tINSIDE " + owner.getEntryPoint() + "\t" + owner.getName(true) + "\t");
                    count("fun INSIDE another function (not split)");
                    continue;
                }
                if (getInstructionAt(a) == null) disassemble(a);
                f = createFunction(a, null);
                if (f == null) {
                    log.println(r[0] + "\tfun\tCREATE FAILED\t\t");
                    count("fun create failed");
                    continue;
                }
                count("fun created");
                action = "created+";
            } else if (f.isThunk()) {
                count("fun thunk left alone");
                continue;
            } else {
                action = "";
            }
            boolean ok = false;
            if (mangled.startsWith("?")) {
                st.createLabel(a, mangled, SourceType.IMPORTED);
                ok = demangle(a, mangled);
                f = fm.getFunctionAt(a);
                if (ok && f != null && f.getName().startsWith("FUN_")) ok = false; // demangler did not rename
                action += ok ? "demangled" : "named(fallback)";
                if (!ok) ok = nameByParts(a, name, true);
            } else {
                if (!mangled.isEmpty() && !mangled.equals(name)) st.createLabel(a, mangled, SourceType.IMPORTED);
                String q = mangled.isEmpty() ? name : (name.contains("::") ? name : plainCName(name));
                ok = nameByParts(a, q, true);
                action += "named";
            }
            for (String m : alt.split(" ")) {
                if (!m.isEmpty()) st.createLabel(a, m, SourceType.IMPORTED);   // folded (ICF) siblings
            }
            count(ok ? "fun " + action : "fun failed");
            f = fm.getFunctionAt(a);
            log.println(r[0] + "\tfun\t" + action + "\t" + before + "\t" + (f == null ? "" : f.getName(true)));
        }

        // ---- data
        for (String[] r : readTsv(args[1])) {
            if (monitor.isCancelled()) break;
            Address a = toAddr(r[0]);
            String name = r[2], mangled = r[3];
            if (mangled.startsWith("??_C@") || mangled.startsWith("__imp_") || name.startsWith("__imp_")) {
                count("data skipped (string literal / IAT)");
                continue;
            }
            if (fm.getFunctionContaining(a) != null) { count("data inside a function, skipped"); continue; }
            Symbol prim = st.getPrimarySymbol(a);
            String before = prim == null ? "" : prim.getName(true);
            boolean ok;
            String action;
            if (mangled.startsWith("?")) {
                st.createLabel(a, mangled, SourceType.IMPORTED);
                ok = demangle(a, mangled);
                action = "demangled";
                if (!ok) { ok = nameByParts(a, name, false); action = "named(fallback)"; }
            } else {
                ok = nameByParts(a, name.contains("::") ? name : plainCName(name), false);
                action = "named";
            }
            count(ok ? "data " + action : "data failed");
            prim = st.getPrimarySymbol(a);
            log.println(r[0] + "\tdata\t" + action + "\t" + before + "\t" + (prim == null ? "" : prim.getName(true)));
        }
        log.close();
        for (String k : counts.keySet()) println(String.format("%-45s %6d", k, counts.get(k)));
    }
}

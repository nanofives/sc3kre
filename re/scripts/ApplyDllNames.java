// ApplyDllNames.java - name a DLL's Ghidra program from its naming plan (re/tools/dll_names.py output).
//
// Plan columns: address  create  primary  mangled  labels  comment  kind (sc3 = session name, cv = CodeView name)
//   create=1  -> disassemble + create the function first (vtable slot targets Ghidra never made a function of);
//                skipped (logged INSIDE) if the address is inside another function.
//   mangled   -> exe twin's decorated name ([CV-COPY]): demangled first, which applies the original signature and
//                class namespace. If `primary` is an sc3_* name, the function is then renamed to it (global ns).
//   primary   -> otherwise the name: "A::B::m" puts m in class namespace A::B; sc3_* names stay global.
//   labels    -> ';'-separated secondary labels (CodeView names behind an sc3_ primary, extra slots of a shared body).
//   comment   -> plate comment (CodeView signatures + evidence tags), prefixed "CV:".
// sc3_* names are SourceType.USER_DEFINED (session names), CodeView names IMPORTED.
//
// MUTATES the program:
//   pwsh re\scripts\ghidra_headless.ps1 -Module SIMCITY.DLL -Script ApplyDllNames.java -Write -Args "<plan.tsv> <log.tsv>"
import ghidra.app.cmd.label.DemanglerCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Namespace;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.symbol.SymbolUtilities;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;

public class ApplyDllNames extends GhidraScript {

    private TreeMap<String, Integer> counts = new TreeMap<>();

    private void count(String k) { counts.merge(k, 1, Integer::sum); }

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

    private void setName(Function f, String qualified, SourceType src) throws Exception {
        List<String> parts = splitQualified(qualified);
        String leaf = SymbolUtilities.replaceInvalidChars(parts.get(parts.size() - 1), true);
        Namespace ns = namespaceFor(parts);
        try {
            f.setParentNamespace(ns);
            f.setName(leaf, src);
        } catch (Exception dup) {
            f.setName(leaf + "_" + f.getEntryPoint(), src);   // name already taken in that namespace
            count("name collision -> suffixed with address");
        }
    }

    private void addLabel(Address a, String qualified) {
        try {
            List<String> parts = splitQualified(qualified);
            String leaf = SymbolUtilities.replaceInvalidChars(parts.get(parts.size() - 1), true);
            currentProgram.getSymbolTable().createLabel(a, leaf, namespaceFor(parts), SourceType.IMPORTED);
        } catch (Exception e) {
            count("label failed");
        }
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) throw new IllegalArgumentException("args: plan.tsv log.tsv");
        PrintWriter log = new PrintWriter(args[1], "UTF-8");
        log.println("address\taction\tbefore\tafter");
        FunctionManager fm = currentProgram.getFunctionManager();
        SymbolTable st = currentProgram.getSymbolTable();
        try (BufferedReader r = new BufferedReader(new FileReader(args[0]))) {
            String line = r.readLine();
            while ((line = r.readLine()) != null) {
                if (line.isEmpty() || monitor.isCancelled()) continue;
                String[] c = line.split("\t", -1);
                Address a = toAddr(c[0]);
                String primary = c[2], mangled = c[3], labels = c[4], comment = c[5];
                Function f = fm.getFunctionAt(a);
                String action = "";
                if (f == null) {
                    Function owner = fm.getFunctionContaining(a);
                    if (owner != null) {
                        log.println(c[0] + "\tINSIDE " + owner.getEntryPoint() + "\t" + owner.getName(true) + "\t");
                        count("inside another function (not split)");
                        continue;
                    }
                    if (getInstructionAt(a) == null) disassemble(a);
                    f = createFunction(a, null);
                    if (f == null) { count("create failed"); log.println(c[0] + "\tCREATE FAILED\t\t"); continue; }
                    count("created");
                    action = "created+";
                }
                String before = f.getName(true);
                boolean sc3 = c.length > 6 && c[6].equals("sc3");   // kind column: session name vs CodeView name
                if (!mangled.isEmpty()) {
                    try {
                        st.createLabel(a, mangled, SourceType.IMPORTED);
                        new DemanglerCmd(a, mangled).applyTo(currentProgram, monitor);
                        action += "demangled+";
                    } catch (Exception e) {
                        count("demangle failed");
                    }
                    f = fm.getFunctionAt(a);
                    if (!sc3 && f.getName().startsWith("FUN_")) setName(f, primary, SourceType.IMPORTED);
                }
                if (sc3) {
                    setName(f, primary, SourceType.USER_DEFINED);
                    action += "sc3";
                } else if (mangled.isEmpty()) {
                    setName(f, primary, SourceType.IMPORTED);
                    action += "cv";
                } else {
                    action += "cv";
                }
                for (String l : labels.split(";")) {
                    if (!l.isEmpty()) addLabel(a, l);
                }
                String oldPlate = getPlateComment(a);
                if (!comment.isEmpty() && (oldPlate == null || !oldPlate.contains("CV: "))) {   // re-runnable
                    String old = oldPlate;
                    String add = "CV: " + comment.replace(" / ", "\n    ");
                    setPlateComment(a, old == null || old.isEmpty() ? add : old + "\n" + add);
                }
                count(action);
                log.println(c[0] + "\t" + action + "\t" + before + "\t" + fm.getFunctionAt(a).getName(true));
            }
        }
        log.close();
        for (String k : counts.keySet()) println(String.format("%-45s %6d", k, counts.get(k)));
    }
}

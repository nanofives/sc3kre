// ForceSignature.java — override a function's signature, then print its decompilation.
//
// WHY: Ghidra's auto-derived prototypes are sometimes wrong in a way that corrupts the whole
// decompilation. The case that motivated this: SIMRCI cISC3ZoneLayer::PlaceZone (0x1003591f) is a
// 4-argument __thiscall (confirmed `ret 0x10`), but auto-analysis gave it 3 and then ALIASED a
// stack boolean onto param_2's high byte (`param_2 = CONCAT13(1, param_2._0_3_)`), which made the
// 4th argument invisible and the control flow unreadable (U-047).
//
// This script MUTATES the program, so it must run WITHOUT -readOnly:
//   analyzeHeadless <projdir> SC3_SIMRCI -process SIMRCI.DLL -noanalysis \
//       -scriptPath re\scripts -postScript ForceSignature.java 0x1003591f __thiscall bool int ptr ptr bool
//
// Args: <addr> <callingConvention> <returnType> <paramType>...
// Types: void int uint short ushort char uchar bool float double ptr  (ptr = void*)
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Parameter;
import ghidra.program.model.listing.ParameterImpl;
import ghidra.program.model.listing.ReturnParameterImpl;
import ghidra.program.model.listing.Variable;
import ghidra.program.model.symbol.SourceType;
import java.util.ArrayList;
import java.util.List;

public class ForceSignature extends GhidraScript {

    private DataType ty(String s) {
        switch (s.toLowerCase()) {
            case "void":   return VoidDataType.dataType;
            case "int":    return IntegerDataType.dataType;
            case "uint":   return UnsignedIntegerDataType.dataType;
            case "short":  return ShortDataType.dataType;
            case "ushort": return UnsignedShortDataType.dataType;
            case "char":   return CharDataType.dataType;
            case "uchar":  return UnsignedCharDataType.dataType;
            case "bool":   return BooleanDataType.dataType;
            case "float":  return FloatDataType.dataType;
            case "double": return DoubleDataType.dataType;
            case "ptr":    return new PointerDataType(VoidDataType.dataType);
            default: throw new IllegalArgumentException("unknown type: " + s);
        }
    }

    public void run() throws Exception {
        String[] a = getScriptArgs();
        if (a.length < 3) {
            println("usage: ForceSignature.java <addr> <conv> <retType> <paramType>...");
            return;
        }
        Address addr = toAddr(Long.parseLong(a[0].replace("0x", ""), 16));
        String conv = a[1];
        DataType ret = ty(a[2]);

        Function f = getFunctionAt(addr);
        if (f == null) { println("NO FUNCTION at " + addr); return; }

        println("BEFORE: " + f.getName() + "  " + f.getSignature().getPrototypeString()
                + "   conv=" + f.getCallingConventionName()
                + "  params=" + f.getParameterCount());

        List<Variable> params = new ArrayList<>();
        for (int i = 3; i < a.length; i++) {
            params.add(new ParameterImpl("a" + (i - 2), ty(a[i]), currentProgram));
        }

        f.updateFunction(conv,
                new ReturnParameterImpl(ret, currentProgram),
                params,
                Function.FunctionUpdateType.DYNAMIC_STORAGE_FORMAL_PARAMS,
                true,
                SourceType.USER_DEFINED);

        println("AFTER : " + f.getSignature().getPrototypeString()
                + "   conv=" + f.getCallingConventionName()
                + "  params=" + f.getParameterCount());
        for (Parameter p : f.getParameters()) {
            println("   param " + p.getOrdinal() + "  " + p.getDataType().getName()
                    + " " + p.getName() + "  storage=" + p.getVariableStorage());
        }

        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        DecompileResults r = dec.decompileFunction(f, 120, monitor);
        println("======== DECOMPILATION @ " + addr + " ========");
        if (r != null && r.decompileCompleted()) {
            println(r.getDecompiledFunction().getC());
        } else {
            println("DECOMPILE FAILED: " + (r == null ? "null" : r.getErrorMessage()));
        }
        dec.dispose();
    }
}

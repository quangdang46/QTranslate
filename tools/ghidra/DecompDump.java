import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;

// Decompile named functions and print their C, one bounded line at a time.
//
// WHY THE LINE SPLITTING MATTERS: a single println() of a whole decompiled
// body works for a ~1.2 KB function and silently prints NOTHING for a ~15 KB
// one (FUN_00464c2f, 2203 bytes of code, decompiles to 15112 chars). The
// headless log writer drops the oversized record, which reads exactly like
// "this function has no body" and cost several wasted rounds. Splitting on
// newlines first keeps every println small enough to survive.
//@category QTranslate
public class DecompDump extends GhidraScript {
    @Override public void run() throws Exception {
        String[] names = getScriptArgs();
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface di = new DecompInterface();
        if (!di.setOptions(new DecompileOptions()) || !di.openProgram(currentProgram)) {
            println("ERROR: could not open the decompiler");
            return;
        }
        try {
            for (String name : names) {
                Function f = null;
                for (Function g : fm.getFunctions(true)) {
                    if (g.getName().equals(name)) { f = g; break; }
                }
                println("=== FUNCTION " + name + " @ " + (f == null ? "NOT FOUND" : f.getEntryPoint()));
                if (f == null) continue;
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                if (r == null || !r.decompileCompleted() || r.getDecompiledFunction() == null) {
                    println("  (decompile failed: " + (r == null ? "null results" : r.getErrorMessage()) + ")");
                    continue;
                }
                String c = r.getDecompiledFunction().getC();
                if (c == null || c.trim().isEmpty()) { println("  (EMPTY body)"); continue; }
                println("---BEGIN-C---");
                for (String line : c.split("\n")) {
                    // One further guard: a single very long line still gets
                    // chunked, so nothing can be dropped for its size.
                    while (line.length() > 400) { println(line.substring(0, 400)); line = line.substring(400); }
                    println(line);
                }
                println("---END-C---");
            }
        } finally { di.dispose(); }
    }
}

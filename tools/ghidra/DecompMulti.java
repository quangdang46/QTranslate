// Decompile several named functions and print their C, via headless Ghidra.
//
// A variant of DecompileNamed that does not swallow failures. The original
// assumed `decompileCompleted() == true` implies `getDecompiledFunction()`
// is non-null; it can be null with a completed, errored decompilation, and
// `println(null)` then prints one empty line -- which reads exactly like
// "the function has no body" rather than "decompilation errored". That
// distinction cost a round of silent empty output here.
//@category QTranslate
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;

public class DecompMulti extends GhidraScript {

    @Override public void run() throws Exception {
        String[] names = getScriptArgs();
        if (names.length == 0) {
            println("USAGE: -postScript DecompMulti.java FUN_00466509 ...");
            return;
        }
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface di = new DecompInterface();
        if (!di.setOptions(new DecompileOptions())) {
            println("ERROR: decompiler rejected the options");
            return;
        }
        if (!di.openProgram(currentProgram)) {
            println("ERROR: could not open the program for decompilation");
            return;
        }
        try {
            for (String name : names) {
                Function f = findByName(fm, name);
                if (f == null) { println("=== " + name + ": NOT FOUND by name"); continue; }
                println("=== " + name + " @ " + f.getEntryPoint());
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                if (r == null) { println("  (null DecompileResults)"); continue; }
                if (!r.decompileCompleted()) {
                    println("  (decompilation did not complete: " + r.getErrorMessage() + ")");
                    continue;
                }
                if (r.getDecompiledFunction() == null) {
                    println("  (completed but no decompiled function: "
                            + r.getErrorMessage() + ")");
                    continue;
                }
                String c = r.getDecompiledFunction().getC();
                if (c == null) { println("  (null C)"); }
                else if (c.trim().isEmpty()) {
                    // An empty body is not a successful decompile: it means the
                    // decompiler produced nothing, and printing it as a blank
                    // line reads exactly like "this function has no body".
                    println("  (EMPTY decompiled body; error="
                            + r.getErrorMessage() + ")");
                }
                else { println(c); }
            }
        } finally {
            di.dispose();
        }
    }

    private Function findByName(FunctionManager fm, String want) {
        for (Function f : fm.getFunctions(true)) if (f.getName().equals(want)) return f;
        return null;
    }
}

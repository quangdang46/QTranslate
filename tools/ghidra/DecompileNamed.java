// Decompile named functions and print their C, via headless Ghidra.
//
// Ghidra compiles .java scripts itself, so there is no javac step and no
// classpath to assemble — only this file needs to exist in -scriptPath.
//
//   JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
//     ~/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
//       ~/Projects QT_REAL -process "QTranslate.6.10.0.exe" -noanalysis \
//       -scriptPath <this dir> -postScript DecompileNamed.java NAME...
//
// JAVA_HOME is required: java_home does not list keg-only Homebrew formulae,
// which is how this host's OpenJDK 21 was once wrongly declared missing
// (docs/review/GHIDRA_MCP_UNAVAILABLE_2026-10-10.md).
//
// Resolves by exact NAME rather than address, so a name the analyzer labelled
// differently reports NOT FOUND instead of silently decompiling the wrong
// function. That distinction matters: 49 of the 439 addresses cited in the
// coverage checklist are analyst-label differences, not missing functions.
//@category QTranslate
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;

public class DecompileNamed extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] names = getScriptArgs();
        if (names.length == 0) {
            println("USAGE: -postScript DecompileNamed.java FUN_00466509 ...");
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
                if (f == null) {
                    println("=== " + name + ": NOT FOUND by name");
                    continue;
                }
                println("=== " + name + " @ " + f.getEntryPoint());
                DecompileResults r = di.decompileFunction(f, 30, monitor);
                if (r == null || !r.decompileCompleted()) {
                    println("  (decompilation failed or timed out)");
                    continue;
                }
                println(r.getDecompiledFunction().getC());
            }
        } finally {
            di.dispose();
        }
    }

    private Function findByName(FunctionManager fm, String want) {
        for (Function f : fm.getFunctions(true)) {
            if (f.getName().equals(want)) {
                return f;
            }
        }
        return null;
    }
}

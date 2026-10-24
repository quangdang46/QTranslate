// Decompile by ADDRESS (hex, 0x...), for a project whose analyzer named
// functions differently than the old one the docs cite.
//@category QTranslate
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;

public class DecompAt extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface di = new DecompInterface();
        di.setOptions(new DecompileOptions());
        di.openProgram(currentProgram);
        try {
            for (String a : args) {
                Address addr = currentProgram.getAddressFactory()
                        .getAddress(a);
                Function f = fm.getFunctionContaining(addr);
                if (f == null) {
                    println("=== " + a + ": no function at address");
                    continue;
                }
                println("=== " + a + " -> " + f.getName()
                        + " @ " + f.getEntryPoint());
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                if (r == null || !r.decompileCompleted()) {
                    println("  (decompilation failed)");
                    continue;
                }
                println(r.getDecompiledFunction().getC());
            }
        } finally {
            di.dispose();
        }
    }
}

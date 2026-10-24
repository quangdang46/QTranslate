// Dump a vftable's function pointers and decompile each.
//@category QTranslate
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;

public class DumpVtable extends GhidraScript {
    @Override
    public void run() throws Exception {
        DecompInterface di = new DecompInterface();
        di.setOptions(new DecompileOptions());
        di.openProgram(currentProgram);
        Memory mem = currentProgram.getMemory();
        try {
            for (String a : getScriptArgs()) {
                Address base = currentProgram.getAddressFactory()
                        .getAddress(a);
                println("=== vftable @ " + a);
                for (int i = 0; i < 8; i++) {
                    long fn = mem.getLong(base.add(i * 4L)) & 0xffffffffL;
                    if (fn == 0 || fn < 0x400000 || fn > 0x600000) {
                        break;
                    }
                    Address fa = currentProgram.getAddressFactory()
                            .getAddress("0" + Long.toHexString(fn));
                    Function f = currentProgram.getFunctionManager()
                            .getFunctionAt(fa);
                    println("--- slot " + i + " -> "
                            + (f == null ? fa.toString() : f.getName()
                               + " @ " + f.getEntryPoint()));
                    if (f != null) {
                        DecompileResults r = di.decompileFunction(f, 60,
                                monitor);
                        if (r != null && r.decompileCompleted()) {
                            println(r.getDecompiledFunction().getC());
                        }
                    }
                }
            }
        } finally {
            di.dispose();
        }
    }
}

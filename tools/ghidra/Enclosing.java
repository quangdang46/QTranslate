// Report the function enclosing each address argument, via headless Ghidra.
//
// Useful for turning an xref address into a decompilable function name: the
// operand offsets found by scanning for a VA are instruction operands, not
// function entry points, so DecompileNamed.java reports NOT FOUND on them.
//
//   JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
//     ~/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
//       ~/Projects QT_REAL -process "QTranslate.6.10.0.exe" -noanalysis \
//       -scriptPath <this dir> -postScript Enclosing.java 0x45826f 0x45d7a0
//
// Grep "error:" in the log before trusting a "script not found" — a compile
// failure presents identically, see GHIDRA_MCP_UNAVAILABLE_2026-10-10.md.
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class Enclosing extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 0) {
            println("USAGE: -postScript Enclosing.java 0x45826f 0x45d7a0");
            return;
        }
        for (String a : args) {
            Address ad = currentProgram.getAddressFactory().getAddress(a);
            if (ad == null) {
                println(a + " -> (unparseable address)");
                continue;
            }
            Function f = currentProgram.getFunctionManager().getFunctionContaining(ad);
            if (f == null) {
                println(a + " -> (no enclosing function)");
                continue;
            }
            println(a + " -> " + f.getName() + " @ " + f.getEntryPoint());
        }
    }
}

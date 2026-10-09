// Print the disassembly of named functions, via headless Ghidra.
//
// The decompiler is the wrong instrument when the thing being asked is a
// *vtable offset* or an *instruction sequence*: it renders an indirect call
// through `lpVtbl` as `(*pIVar2->get_accName)(...)`, which requires knowing
// already which member sits at that offset. The raw instructions carry the
// offset literally (`CALL DWORD PTR [EAX+0x28]`), so this prints both.
//
//   JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
//     ~/ghidra/ghidra_12.1.4_PUBLIC/support/analyzeHeadless \
//       ~/Projects QT_REAL -process "QTranslate.6.10.0.exe" -noanalysis \
//       -scriptPath <this dir> -postScript DisasmNamed.java FUN_...
//
// Comments are included, because a call Ghidra has resolved to an import
// (AccessibleObjectFromPoint, SysStringLen, ...) appears as a name in the
// comment rather than in the operand.
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.address.AddressIterator;

public class DisasmNamed extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] names = getScriptArgs();
        if (names.length == 0) {
            println("USAGE: -postScript DisasmNamed.java FUN_00404901 ...");
            return;
        }
        FunctionManager fm = currentProgram.getFunctionManager();
        for (String name : names) {
            Function f = findByName(fm, name);
            if (f == null) {
                println("=== " + name + ": NOT FOUND by name");
                continue;
            }
            println("=== " + name + " @ " + f.getEntryPoint());
            InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
            while (it.hasNext()) {
                Instruction ins = it.next();
                String c = ins.getComment(ghidra.program.model.listing.CodeUnit.EOL_COMMENT);
                String line = ins.getAddressString(true, true) + "   " + ins.toString();
                if (c != null && !c.isEmpty()) {
                    line += "    ; " + c;
                }
                println(line);
            }
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

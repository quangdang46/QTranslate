// Find instructions carrying a given immediate (e.g. internal window
// messages 0x8064/0x8069) and print the enclosing function.
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;

public class FindImm extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (String a : getScriptArgs()) {
            long want = Long.parseLong(a.replace("0x", ""), 16);
            println("=== immediate 0x" + Long.toHexString(want));
            InstructionIterator it = currentProgram.getListing()
                    .getInstructions(true);
            while (it.hasNext()) {
                Instruction ins = it.next();
                for (int i = 0; i < ins.getNumOperands(); i++) {
                    Object[] ops = ins.getOpObjects(i);
                    for (Object o : ops) {
                        if (o instanceof Scalar
                                && ((Scalar) o).getValue() == want) {
                            Function f = currentProgram
                                    .getFunctionManager()
                                    .getFunctionContaining(ins.getAddress());
                            println(ins.getAddress() + " "
                                    + ins.getMnemonicString() + " in "
                                    + (f == null ? "?" : f.getName()
                                       + " @ " + f.getEntryPoint()));
                        }
                    }
                }
            }
        }
    }
}

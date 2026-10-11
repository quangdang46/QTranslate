//@category QTranslate
// Find every instruction whose operand is one of the Appearance struct
// offsets, and report the enclosing function. One analysis pass answers for
// all four keys at once, which four separate REA imports would not.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import java.util.*;

public class StructRefs extends GhidraScript {
    @Override public void run() throws Exception {
        // ThemeName +0x1dc, ColorBack +0x1e8, ColorText +0x1ec, ColorFrame +0x1f0
        Map<Long, String> wanted = new LinkedHashMap<>();
        wanted.put(0x1dcL, "ThemeName");
        wanted.put(0x1e8L, "ColorBack");
        wanted.put(0x1ecL, "ColorText");
        wanted.put(0x1f0L, "ColorFrame");

        Listing lst = currentProgram.getListing();
        FunctionIterator fi = currentProgram.getFunctionManager().getFunctions(true);
        while (fi.hasNext()) {
            Function f = fi.next();
            InstructionIterator ii = lst.getInstructions(f.getBody(), true);
            while (ii.hasNext()) {
                Instruction ins = ii.next();
                int n = ins.getNumOperands();
                for (int op = 0; op < n; op++) {
                    for (Object o : ins.getOpObjects(op)) {
                        if (!(o instanceof Scalar)) continue;
                        long v = ((Scalar) o).getUnsignedValue();
                        if (wanted.containsKey(v)) {
                            println(wanted.get(v) + " @ " + ins.getAddress()
                                    + " in " + f.getName() + "  |  " + ins);
                        }
                    }
                }
            }
        }
    }
}

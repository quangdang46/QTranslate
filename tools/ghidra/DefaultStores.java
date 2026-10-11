// Find every instruction that stores 0xf0f0f0 (ColorBack's default) or
// 0x7a6c5d (ColorFrame's default) and report its enclosing function.
//
// The struct-offset scan (StructRefs) found many hits, but several functions
// turned out to be unrelated structs that merely share offsets like +0x1e8
// (a message-handler switch on command IDs; a small packed-value defaults
// block). Those are false positives. An immediate-store scan on the two
// discriminating default *values* is a much stronger signal: a real
// Appearance initialiser must write exactly 0xf0f0f0 and 0x7a6c5d.
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import java.util.*;

public class DefaultStores extends GhidraScript {
    @Override public void run() throws Exception {
        Map<Long, String> wanted = new LinkedHashMap<>();
        wanted.put(0xf0f0f0L, "ColorBack=#f0f0f0");
        wanted.put(0x7a6c5dL, "ColorFrame=#7a6c5d");

        Listing lst = currentProgram.getListing();
        FunctionIterator fi = currentProgram.getFunctionManager().getFunctions(true);
        while (fi.hasNext()) {
            Function f = fi.next();
            InstructionIterator ii = lst.getInstructions(f.getBody(), true);
            while (ii.hasNext()) {
                Instruction ins = ii.next();
                for (int op = 0; op < ins.getNumOperands(); op++) {
                    for (Object o : ins.getOpObjects(op)) {
                        if (!(o instanceof Scalar)) continue;
                        long v = ((Scalar) o).getUnsignedValue();
                        if (wanted.containsKey(v)) {
                            println(wanted.get(v) + "  store @ " + ins.getAddress()
                                    + "  in " + f.getName()
                                    + "  |  " + ins);
                        }
                    }
                }
            }
        }
    }
}

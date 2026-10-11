import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;

public class dis_one extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Address a = currentProgram.getAddressFactory().getAddress(args[0]);
        Address end = currentProgram.getAddressFactory().getAddress(args[1]);
        Listing lst = currentProgram.getListing();
        Address cur = a;
        while (cur != null && cur.compareTo(end) < 0) {
            Instruction ins = lst.getInstructionAt(cur);
            if (ins == null) { cur = cur.add(1); continue; }
            println(cur + ": " + ins.toString());
            cur = cur.add(ins.getLength());
        }
    }
}

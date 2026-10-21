// Dump every defined string in the program as "ADDR<TAB>text".
//
//   -postScript DumpStrings.java
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;

public class DumpStrings extends GhidraScript {

    @Override
    public void run() throws Exception {
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int n = 0;
        while (it.hasNext()) {
            Data d = it.next();
            Object v = d.getValue();
            if (!(v instanceof String)) continue;
            String txt = ((String) v).replace("\n", "\\n").replace("\r", "\\r");
            println(d.getAddress() + "\t" + txt);
            n++;
        }
        println("TOTAL " + n);
    }
}

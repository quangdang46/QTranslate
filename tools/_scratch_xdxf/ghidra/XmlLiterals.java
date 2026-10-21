// Find XML-ish string literals in the program ("<ar", "</ar", "<k>", ...)
// and report the functions that reference them.
//
//   -postScript XmlLiterals.java
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class XmlLiterals extends GhidraScript {

    private static final String[] MARKS = {
        "<ar", "</ar", "<xdxf", "</xdxf", "<k>", "<tr>", "<ex>", "<def>",
        "<br/>", "<br>", "<dtrn", "<kref", "<iref", "qtdp:", "</k>", "</tr>",
        "<?xml", "xslt"
    };

    @Override
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int hits = 0;
        while (it.hasNext()) {
            Data d = it.next();
            Object v = d.getValue();
            if (!(v instanceof String)) continue;
            String txt = (String) v;
            boolean want = false;
            for (String m : MARKS) {
                if (txt.contains(m)) { want = true; break; }
            }
            if (!want) continue;
            hits++;
            println("STR  " + d.getAddress() + "  " + txt);
            Address a = d.getAddress();
            ReferenceIterator ri = currentProgram.getReferenceManager()
                    .getReferencesTo(a);
            while (ri.hasNext()) {
                Reference r = ri.next();
                Function f = fm.getFunctionContaining(r.getFromAddress());
                println("   <- " + r.getFromAddress() + "  in "
                        + (f == null ? "<no function>" : f.getName() + " @ " + f.getEntryPoint()));
            }
        }
        println("TOTAL hits: " + hits);
    }
}

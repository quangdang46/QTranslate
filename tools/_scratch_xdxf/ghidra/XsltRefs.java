// Scan the program's strings for XSLT / MSXML markers and report which
// functions reference them.
//
//   JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
//     /opt/homebrew/Cellar/ghidra/12.1.4/libexec/support/analyzeHeadless \
//       ~/Projects QT_FULL -process "QTranslate.6.10.0.exe" -noanalysis \
//       -scriptPath <dir> -postScript XsltRefs.java
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class XsltRefs extends GhidraScript {

    private static final String[] MARKS = {
        "xslt", "Xdxf", "xdxf", "XSLT", "transform", "Transform",
        "MSXML", "msxml", "selectSingleNode", "selectNodes",
        "IXMLDOM", "stylesheet", "Stylesheet", "XSLT"
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
        println("TOTAL string hits: " + hits);
    }
}

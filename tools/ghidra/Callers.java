//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import java.util.Set;
import ghidra.program.model.symbol.*;

public class Callers extends GhidraScript {
    @Override public void run() throws Exception {
        String[] names = getScriptArgs();
        FunctionManager fm = currentProgram.getFunctionManager();
        for (String nm : names) {
            Function f = null;
            for (Function g : fm.getFunctions(true)) if (g.getName().equals(nm)) { f = g; break; }
            if (f == null) { println("=== " + nm + ": NOT FOUND"); continue; }
            println("=== callers of " + nm + " @ " + f.getEntryPoint());
            Set<Function> callers = null;

            ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
            while (it.hasNext()) {
                Reference r = it.next();
                println("  ref " + r.getReferenceType() + " from " + r.getFromAddress());
            }
        }
    }
}

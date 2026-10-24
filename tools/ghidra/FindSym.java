// List symbols whose FULL PATH matches a regex, with references TO them.
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import java.util.regex.Pattern;

public class FindSym extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (String a : getScriptArgs()) {
            Pattern p = Pattern.compile(a);
            println("=== symbols matching " + a);
            SymbolTable st = currentProgram.getSymbolTable();
            for (Symbol s : st.getAllSymbols(true)) {
                String path = s.getName(true);
                if (!p.matcher(path).find()) {
                    continue;
                }
                println(s.getAddress() + "  " + path);
                for (Reference r : currentProgram.getReferenceManager()
                        .getReferencesTo(s.getAddress())) {
                    Function f = currentProgram.getFunctionManager()
                            .getFunctionContaining(r.getFromAddress());
                    println("   <- " + r.getFromAddress() + " in "
                            + (f == null ? "?" : f.getName() + "@"
                               + f.getEntryPoint()));
                }
            }
        }
    }
}

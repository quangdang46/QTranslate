// Dump raw bytes at given addresses (hex + ascii).
//
//   -postScript DumpBytes.java 0051c4f4 32 00511320 16
//@category QTranslate
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;

public class DumpBytes extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("USAGE: -postScript DumpBytes.java ADDR LEN [ADDR LEN ...]");
            return;
        }
        Memory mem = currentProgram.getMemory();
        for (int i = 0; i + 1 < args.length; i += 2) {
            Address a = toAddr(args[i]);
            int len = Integer.parseInt(args[i + 1]);
            StringBuilder hex = new StringBuilder();
            StringBuilder asc = new StringBuilder();
            for (int k = 0; k < len; k++) {
                int v = mem.getByte(a.add(k)) & 0xff;
                hex.append(String.format("%02x ", v));
                asc.append((v >= 0x20 && v < 0x7f) ? (char) v : '.');
            }
            println("BYTES " + args[i] + " len=" + len);
            println("  hex   " + hex.toString());
            println("  ascii " + asc.toString());
        }
    }
}

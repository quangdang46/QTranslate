"""Walk RT_STRING from the recovered PE and print ids 185/186/190/202.

Correct indexing: a type-6 leaf's nameId is (block + 1), and each leaf
holds ONE IMAGE_RESOURCE_DATA_ENTRY whose OffsetToData (an RVA) points at
the packed 16-string block. Verified 2026-10-10.
"""
import struct
d = open("docs/review/artifacts/QTranslate.6.10.0.exe", "rb").read()
ROOT = 0x146000                      # .rsrc raw offset
def u16(o): return struct.unpack_from("<H", d, o)[0]
def u32(o): return struct.unpack_from("<I", d, o)[0]
def entries(off):
    n = u16(off+12)+u16(off+14)
    for i in range(n):
        e = off+16+i*8
        yield (u32(e)&0x7fffffff, bool(u32(e+4)&0x80000000), ROOT+(u32(e+4)&0x7fffffff))
T6 = [s for t,i,s in entries(ROOT) if t == 6][0]
out = {}
for nid, isd, sub in entries(T6):    # leaf nameId = block+1
    block = nid - 1
    deoff = entries(sub).__next__()[2]      # the single data entry
    p = ROOT + (u32(deoff) - 0x14b000)
    end = p + u32(deoff+4)
    for slot in range(16):
        ln = u16(p)
        out[block*16+slot] = d[p+2:p+2+ln*2].decode("utf-16-le","replace")
        p += 2 + ln*2
        if p >= end:
            break
for w in (185, 186, 190, 202):
    print("  id %-4d -> %r" % (w, out.get(w)))

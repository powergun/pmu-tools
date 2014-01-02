#!/usr/bin/python
# resolve ELF and DWARF symbol tables using elftools
import bisect
from elftools.common.py3compat import maxint, bytes2str
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

# global caches
open_files = dict()
resolved = dict()
symtables = dict()
lines = dict()

def build_line_table(dwarfinfo):
    lines = []
    for CU in dwarfinfo.iter_CUs():
        lp = dwarfinfo.line_program_for_CU(CU)
        prevstate = None
        for entry in lp.get_entries():
            if entry.state is None or entry.state.end_sequence:
                continue
            if prevstate:
                lines.append((prevstate.address, 
                              entry.state.address,
                              lp['file_entry'][prevstate.file - 1].name,
                              prevstate.line))
            prevstate = entry.state
    lines.sort()
    return lines
                              
def build_symtab(elffile):
    syms = []
    for section in elffile.iter_sections():
        if isinstance(section, SymbolTableSection):
            for nsym, sym in enumerate(section.iter_symbols()):
                name = bytes2str(sym.name)
                if not name:
                    continue
                if sym.entry.st_info.type != 'STT_FUNC':
                    continue
                end = sym['st_value'] + sym['st_size']
                syms.append((sym['st_value'], end, 
                             bytes2str(sym.name)))
    syms.sort()
    return syms

def find_le(f, key):
    pos = bisect.bisect_left(f, (key,))
    if pos < len(f) and f[pos][0] == key:
        return f[pos]
    if pos == 0:
        return None
    return f[pos - 1]

def find_elf_file(fn):
    if fn in open_files:
        elffile = open_files[fn]
    else:
        f = open(fn, 'rb')
        elffile = ELFFile(f)
        open_files[fn] = elffile
    return elffile

def resolve_line(fn, ip):
    elffile = find_elf_file(fn)
    if fn not in lines and elffile.has_dwarf_info():
        lines[fn] = build_line_table(elffile.get_dwarf_info())

    src = None
    if resolve_line and fn in lines:
        pos = find_le(lines[fn], ip)
        if pos:
            src = "%s:%d" % (pos[2], pos[3])    
    return src

def resolve_sym(fn, ip):
    elffile = find_elf_file(fn)
        
    if fn not in symtables:
        symtables[fn] = build_symtab(elffile)

    loc = None
    offset = None
    if fn in symtables:
        sym = find_le(symtables[fn], ip)
        if sym:
            loc, offset = sym[2], ip - sym[0]

    return loc, offset
        
def resolve_ip(filename, foffset, ip, need_line):
    sym, soffset, line = None, 0, None
    if filename and filename.startswith("/"):
        sym, soffset = resolve_sym(filename, foffset)
        if not sym:
            sym, soffset = resolve_sym(filename, ip)
        if need_line:
            line = resolve_line(filename, ip)
    return sym, soffset, line

if __name__ == '__main__':
    import sys
    print resolve_addr(sys.argv[1], int(sys.argv[2], 16))
    print resolve_line(sys.argv[1], int(sys.argv[2], 16))

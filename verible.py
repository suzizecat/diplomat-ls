import base64
import json
import typing as T
import gc
from frontend import KytheTree
import time

def run2() :
    p = "Z:\\test\\index.json"
    p = "C:\\Users\\jfaucher\\Desktop\\index.json"

    with open(p, "r") as f:
        tstart = time.time()
        print("Reading data...")
        text = ""
        tree = KytheTree()
        gc.disable()
        i = 0
        for line in f :
            text += line
            if line == "}\n" :
                data = json.loads(text)
                tree.add_and_link_element(data)
                text = ""
                i += 1
                if (i % 1000 ) == 0:
                    print(f"Handled {i:6d} elements")

        gc.enable()
        print(f"Done {i} elements in {time.time() - tstart}s.")
        """
        print("Formatting data...")
        text = "[" + text.replace("}\n{", "},\n{") + "]"
        print("Loading JSON...")
        data = json.loads(text)

        print("Filling tree...")

        for e in data :
            tree.add_element(e)
        """
        print("Resolving tree...")
        tree.solve_edges()

        print("Processing tree...")
        anchors = [n for n in tree.nodes.values() if n.facts["/kythe/node/kind"] == "anchor"]
        for n in anchors:
            n.text = tree.nodes[n.path].facts["/kythe/text"][
                     int(n.facts["/kythe/loc/start"]):int(n.facts["/kythe/loc/end"])]

        for n in anchors:
            text = tree.nodes[n.path].facts["/kythe/text"]
            start = int(n.facts["/kythe/loc/start"])
            tline = text[:start].count("\n")
            tchar = start - text[:start].rfind("\n")
            n.posstring = f"{n.path}:{tline}:{tchar}"

        print(f"Finished in {time.time() - tstart}s")
        return tree


def run() :

    logdict = dict()

    raw_dict : T.Dict[str,T.Dict[str,str]] =dict()
    files : T.Dict[str,str] = dict()
    with open("/home/julien/Projets/HDL/MPU_KATSV/t.json","r") as f :
        data = json.loads("[" +
                          f.read().replace("}\n{", "},\n{") +
                          "]")

    i = 0
    for elt in data :
        i += 1
        raw_symbul = elt["source"]["signature"]
        symbol = str(raw_symbul) +" - "+ base64.b64decode(raw_symbul).decode("ascii")

        fpath =  elt["source"]["path"]
        if symbol not in raw_dict :
            raw_dict[symbol] = dict()
            raw_dict[symbol]["file"] = fpath

        fact_name =  elt["fact_name"]
        value = base64.b64decode(elt["fact_value"]).decode("ascii") if "fact_value" in elt else ""
        if fact_name == "/kythe/text":
            files[fpath] = value

        if fact_name == "/" and "edge_kind" in elt :
            fact_name = f"{elt['edge_kind']}"


        target = ""
        if "target" in elt :
            target = elt["target"]["path"]
            target += ":"+ base64.b64decode(elt["target"]["signature"]).decode("ascii")

        regfactname = fact_name
        append = 0
        while f"{regfactname}" in raw_dict[symbol] :
            append += 1
            regfactname = f"{fact_name}{append}"

        raw_dict[symbol][regfactname] = value if value != "" else target

        print(f"{i:>4d} {fact_name:32s} - {symbol:50s} = {value} [{target}]")

    for name, symb in raw_dict.items() :
        print(name)
        for k in symb:
            print(f"\t{k:30s} : {symb[k]}")
        if "/kythe/node/kind" in symb and symb["/kythe/node/kind"] == "anchor" :
            beg = int(symb["/kythe/loc/start"])
            end = int(symb["/kythe/loc/end"])
            content = files[symb["file"]][beg:end]
            print(f"\t{'text':30s} : {content}")



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    import os
    from frontend.indexers import KytheIndexer
    from urllib.parse import urlunparse, ParseResult, quote as urlquote
    from pygls.lsp.types import Location, Range, Position
    t = run2()
    if True :
        # find_symbol_per_location
        #find_file = "\\media\\hyadum3p1\\dpt\\adh\\workspace\\easii-ic\\a19011\\users\\jfaucher\\dev_stfe\\input\\sharedrtl\\rtl\\fifo\\sync_fifo_memsp.sv"
        print("Start lookup")
        start = time.time()
        find_file = "\\media\\hyadum3p1\\dpt\\adh\\workspace\\easii-ic\\a19011\\users\\jfaucher\\dev_stfe\\input\\sharedrtl\\rtl\\lvds\\lvds_out.sv"
        find_line = 30
        find_selection = (8,24)

        # uri_base = ParseResult(scheme='file', path=urlquote(find_file),netloc="",params="",query="",fragment="")
        loc = Location(uri=find_file,
                       range = Range(
                           start=Position(line=find_line,character=find_selection[0]),
                           end=Position(line=find_line,character=find_selection[1]))
                       )

        # loc.range.start.line = find_line
        # loc.range.start.character = find_selection[0]
        # loc.range.end.line = find_line
        # loc.range.end.character = find_selection[1]

        indexer = KytheIndexer()
        indexer.tree = t
        indexer.refresh_anchors()
        indexer.refresh_files()

        refs = indexer.get_refs_from_location(loc)
        defs = indexer.get_definition_from_location(loc)

        print("Done in ",time.time() - start)


# See PyCharm help at https://www.jetbrains.com/help/pycharm/

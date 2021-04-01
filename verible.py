import base64
import json
import typing as T

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
    run()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
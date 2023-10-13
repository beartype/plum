Search.setIndex({"docnames": ["advanced_usage", "api", "autoreload", "basic_usage", "classes", "command_line", "comparison", "conversion_promotion", "dispatch", "integration", "intro", "keyword_arguments", "parametric", "precedence", "scope", "types", "union_aliases"], "filenames": ["advanced_usage.md", "api.rst", "autoreload.md", "basic_usage.md", "classes.md", "command_line.md", "comparison.md", "conversion_promotion.md", "dispatch.md", "integration.md", "intro.md", "keyword_arguments.md", "parametric.md", "precedence.md", "scope.md", "types.md", "union_aliases.md"], "titles": ["Advanced Usage", "Application Programming Interface", "Support for IPython Autoreload", "Basic Usage", "Classes", "Command Line Configuration Options", "Comparison with Other Multiple Dispatch Implementations", "Conversion and Promotion", "Ways to Dispatch", "Integration with Linters and <code class=\"docutils literal notranslate\"><span class=\"pre\">mypy</span></code>", "Plum", "Keyword Arguments", "Parametric Classes", "Method Precedence", "Scope of Functions", "Types", "Union Aliases"], "terms": {"you": [0, 1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 14, 15, 16], "ve": 0, "now": [0, 16], "master": 0, "basic": [0, 10], "Its": 0, "time": 0, "explor": [0, 10], "more": [0, 3, 6, 9, 12, 13, 15, 16], "wai": [0, 3, 9, 11, 12, 16], "us": [0, 1, 2, 4, 6, 7, 8, 9, 11, 12, 13, 14, 15], "plum": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16], "moduletyp": 1, "modul": [1, 4, 5, 8, 16], "name": [1, 4, 11], "sourc": 1, "A": [1, 6, 8, 9, 12, 15, 16], "from": [1, 2, 3, 4, 5, 6, 7, 9, 11, 12, 13, 14, 15, 16], "anoth": [1, 7, 9, 14, 15], "paramet": [1, 6, 12, 16], "str": [1, 3, 4, 6, 7, 8, 9, 12, 15, 16], "live": 1, "promis": 1, "retriev": 1, "attempt": [1, 7, 15], "refer": 1, "return": [1, 3, 4, 6, 8, 9, 11, 12, 13, 14, 15, 16], "self": [1, 4, 6, 7, 12], "promisedtyp": 1, "sometyp": 1, "avail": [1, 3, 15], "when": [1, 4, 7, 8, 12, 15], "need": 1, "option": [1, 6, 11, 15, 16], "default": [1, 2], "is_faith": [1, 15], "x": [1, 3, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16], "check": [1, 6, 9, 12], "whether": [1, 6, 12, 15], "hint": [1, 4, 6, 15], "faith": 1, "t": [1, 3, 6, 12, 15, 16], "defin": [1, 2, 4, 6, 14], "_faithful_": 1, "all": [1, 3, 5, 6, 8, 9, 15, 16], "follow": [1, 4, 5, 6, 9, 11, 12, 13, 14, 15, 16], "hold": 1, "true": [1, 6, 12, 15], "isinst": [1, 6, 12, 15], "issubclass": [1, 12, 15], "can": [1, 2, 3, 4, 6, 7, 8, 11, 12, 13, 14, 15, 16], "control": 1, "ar": [1, 2, 6, 8, 11, 12, 13, 14, 15, 16], "set": [1, 2, 4, 5, 6, 12, 13, 15], "attribut": 1, "__faithful__": [1, 15], "unfaithfultyp": 1, "fals": [1, 12, 15], "bool": [1, 16], "resolve_type_hint": [1, 15], "resolv": [1, 3, 4, 8, 11, 12, 14, 15], "resolvabletyp": 1, "s": [1, 2, 3, 8, 9, 11, 12, 15, 16], "type_map": 1, "run": [1, 4, 12, 15], "map": 1, "kei": [1, 16], "thi": [1, 3, 4, 6, 7, 9, 11, 12, 14, 15, 16], "dictionari": 1, "valu": [1, 4, 11, 13, 16], "dict": [1, 15], "object": [1, 4, 6, 7, 12, 13, 15, 16], "vararg": 1, "miss": 1, "return_typ": 1, "ani": [1, 4, 6, 12], "preced": [1, 6], "int": [1, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15], "0": [1, 3, 4, 6, 7, 8, 11, 12, 13, 14], "implement": [1, 3, 7, 8, 9, 11, 12, 13, 15, 16], "callabl": 1, "none": [1, 4, 6, 12, 15], "tupl": [1, 6, 16], "argument": [1, 3, 8, 12, 13, 15], "variabl": [1, 2], "number": [1, 3, 6, 7, 8, 12], "has_vararg": 1, "onli": [1, 5, 9, 11, 12, 15], "expand_vararg": 1, "n": [1, 12], "expand": [1, 16], "desir": [1, 12, 16], "match": [1, 6, 7, 11], "otherwis": [1, 11], "append_default_arg": 1, "f": [1, 3, 5, 6, 7, 8, 11, 12, 14, 15], "list": [1, 8, 15, 16], "where": [1, 2, 3, 11, 15], "those": [1, 12], "deriv": 1, "input": [1, 4], "treat": 1, "everi": 1, "non": 1, "keyword": [1, 13], "turn": 1, "extract": [1, 12], "which": [1, 6, 9, 11, 12, 13, 15], "remov": 1, "exclud": 1, "extract_signatur": 1, "method": [1, 2, 3, 5, 6, 9, 11, 12, 14, 15], "owner": 1, "wrap": 1, "own": 1, "clear_cach": 1, "reregist": 1, "clear": [1, 11, 15], "cach": [1, 15], "also": [1, 3, 7, 11, 12, 14, 15], "decor": [1, 7, 9, 12], "extend": 1, "dispatch_multi": 1, "multipl": [1, 3, 9, 11], "onc": [1, 11], "regist": [1, 5], "invok": 1, "particular": [1, 8, 11, 16], "properti": [1, 4], "If": [1, 2, 4, 14, 15, 16], "either": [1, 2, 3, 11, 15], "must": [1, 9, 11, 15, 16], "given": [1, 8, 11, 12], "resolve_method": 1, "target": 1, "find": [1, 6], "namespac": 1, "qualifi": 1, "abstract": [1, 5], "an": [1, 2, 3, 6, 8, 9, 11, 12, 13, 14, 15], "definit": 1, "The": [1, 3, 4, 5, 6, 7, 9, 11, 12, 13, 15], "doe": [1, 2, 7, 9, 12], "multi": [1, 8], "clear_all_cach": [1, 15], "includ": [1, 2, 16], "subclass": [1, 12], "should": [1, 6, 7, 11, 15], "call": [1, 4, 8, 9, 11, 12, 15], "modifi": 1, "conveni": 1, "purpos": [1, 12], "except": [1, 3], "ambiguouslookuperror": [1, 6, 13], "cannot": [1, 7, 15], "due": [1, 15], "ambigu": [1, 6, 13], "notfoundlookuperror": [1, 3, 4, 8, 11, 12, 14, 15], "becaus": [1, 6, 11, 12, 15, 16], "found": [1, 6], "covariantmeta": 1, "metaclass": [1, 6, 15], "covari": [1, 12, 15], "kind": 1, "arg": [1, 9, 12], "kw_arg": 1, "provid": [1, 6, 12], "val": 1, "move": 1, "inform": [1, 12], "domain": [1, 12], "superclass": 1, "creat": [1, 8, 12, 14, 15], "wrapper": [1, 12], "super": 1, "new": [1, 8, 11, 14], "original_class": 1, "constructor": 1, "befor": [1, 2, 11, 15], "ha": [1, 6, 11, 12], "been": [1, 11], "specifi": [1, 3, 9, 13, 15], "infer": [1, 12], "__inter_type_parameter__": 1, "shown": 1, "here": [1, 12, 15], "possibl": [1, 6, 15], "overrid": [1, 2, 12], "classmethod": [1, 6, 12], "def": [1, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16], "__infer_type_parameter__": [1, 12], "cl": [1, 6], "after": [1, 9, 15, 16], "__init_type_parameter__": [1, 6, 12], "again": 1, "show": [1, 5], "ps": 1, "To": [1, 2, 4, 14, 16], "determin": 1, "one": [1, 7, 9, 11, 15], "instanc": [1, 12], "compar": [1, 6], "__le_type_parameter__": [1, 6, 12], "left": [1, 6, 12], "right": [1, 6, 7, 12], "Is": [1, 11, 12], "type_paramet": [1, 6, 12], "get": [1, 4, 6, 12], "concret": [1, 6, 12], "thereof": 1, "add_conversion_method": [1, 7], "type_from": [1, 7], "type_to": [1, 7], "add": [1, 7, 8, 9, 16], "convert": [1, 6], "add_promotion_rul": [1, 7], "type1": 1, "type2": 1, "rule": [1, 3, 7], "first": [1, 5, 6, 9, 12, 15], "second": [1, 6, 9], "conversion_method": [1, 7], "obj": 1, "obj1": 1, "obj2": 1, "common": [1, 7], "monkei": 1, "patch": 1, "__repr__": [1, 16], "__str__": [1, 16], "how": [1, 7, 11, 12, 16], "displai": [1, 16], "exampl": [1, 6, 7, 8, 9, 11, 13, 15, 16], "activate_union_alias": [1, 16], "intorfloat": 1, "float": [1, 3, 4, 7, 8, 9, 11, 12, 14], "set_union_alia": [1, 16], "note": [1, 12, 15, 16], "print": [1, 6, 16], "rather": [1, 16], "than": [1, 16], "just": [1, 6, 12, 15, 16], "deliber": 1, "goal": 1, "break": [1, 2, 13, 16], "code": [1, 9, 16], "reli": 1, "pars": 1, "alia": [1, 16], "replac": 1, "deactivate_union_alias": [1, 16], "undo": 1, "what": [1, 6, 7, 11, 12, 14, 15, 16], "activ": [1, 2, 16], "did": 1, "restor": 1, "origin": 1, "chang": [1, 16], "activate_autoreload": [1, 2], "pirat": 1, "update_inst": 1, "have": [1, 9, 11, 12, 15], "work": [1, 2, 6, 9, 11, 12, 16], "deactivate_autoreload": [1, 2], "disabl": [1, 2], "hack": 1, "mixin": 1, "make": [1, 6, 11, 12], "requir": 1, "__le__": 1, "is_compar": 1, "indic": [1, 7], "instanti": [1, 12], "boolean": 1, "typehint": 1, "get_class": 1, "assum": 1, "part": 1, "fulli": [1, 15], "get_context": 1, "context": 1, "correspond": 1, "scope": 1, "is_in_class": 1, "multihash": 1, "order": [1, 6], "sensit": 1, "hash": 1, "repr_short": 1, "represent": 1, "string": [1, 3, 9], "shorter": 1, "form": 1, "_type_repr": 1, "wrap_lambda": 1, "lambda": 1, "version": [1, 9, 12], "out": [2, 11], "box": 2, "extens": 2, "reload": 2, "file": 2, "class": [2, 7, 13, 15], "most": [2, 3, 4, 6], "like": [2, 14, 15], "your": [2, 6, 9, 14, 15], "dispatch": [2, 3, 4, 5, 7, 9, 12, 13, 14, 15, 16], "tabl": 2, "experiment": 2, "enabl": 2, "some": [2, 11, 12], "intern": 2, "environ": 2, "plum_autoreload": 2, "1": [2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16], "load": [2, 15], "export": 2, "import": [2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16], "issu": [2, 4], "pleas": [2, 10], "open": 2, "featur": [2, 16], "allow": 3, "same": 3, "function": [3, 4, 5, 6, 7, 9, 11, 12, 13, 15, 16], "type": [3, 4, 8, 9, 11, 12, 16], "integ": [3, 5, 9, 12, 13, 15], "we": [3, 4, 6, 8, 9, 11, 12, 16], "haven": 3, "so": [3, 15], "case": [3, 6, 7, 11, 12, 15], "rais": [3, 6, 12], "For": [3, 4, 6, 8, 9, 11, 12, 13, 14, 15, 16], "could": [3, 4, 6, 8, 11, 12, 14, 15], "instead": [3, 7, 9, 12], "let": [3, 6, 7, 16], "sinc": [3, 6, 15], "But": 3, "specif": [3, 12], "chosen": 3, "necessarili": [3, 6], "obtain": 3, "signatur": [3, 6, 8, 9, 13, 15], "0x7f9f6014f160": 3, "0x7f9f6029c280": 3, "0x7f9f801fdf70": 3, "excel": 3, "detail": [3, 11], "overview": 3, "see": [3, 11, 12, 16], "manual": 3, "julia": [3, 15], "languag": 3, "within": 4, "real": [4, 6], "__add__": 4, "other": [4, 11, 15], "ad": 4, "without": [4, 6, 9, 11], "problem": [4, 15, 16], "myclass": [4, 15], "__init__": [4, 7, 12, 14], "_name": 4, "setter": 4, "ok": [4, 11, 12], "Not": [4, 11, 12], "__main__": [4, 5, 6, 7, 8, 12, 13, 16], "0x7f8cb8813eb0": 4, "imagin": 4, "design": [4, 11, 13, 14], "try": [4, 12], "error": [4, 6, 11], "nameerror": 4, "traceback": 4, "recent": 4, "last": 4, "ipython": 4, "2c6fe56c8a98": 4, "2": [4, 6, 7, 8, 11, 12, 15], "3": [4, 6, 7, 9, 11, 12], "4": [4, 11], "5": [4, 7, 15], "6": [4, 15], "yet": [4, 15], "circumv": 4, "prevent": [5, 14, 16], "concaten": 5, "docstr": 5, "consid": [5, 6, 11, 14, 16], "do": [5, 9, 11, 12, 15, 16], "someth": [5, 9, 11, 12], "usual": [5, 7, 9, 15], "output": 5, "help": [5, 8, 12, 16], "With": 5, "There": 6, "few": [6, 15, 16], "realli": 6, "great": 6, "altern": 6, "notabl": 6, "multipledispatch": 6, "multimethod": 6, "below": [6, 8, 11, 12], "describ": [6, 12], "apart": 6, "arguabl": 6, "appeal": 6, "aspect": 6, "mean": [6, 11, 12, 15], "heavi": 6, "lift": 6, "around": [6, 11], "correctli": 6, "handl": 6, "taken": 6, "veri": [6, 11, 12, 15], "difficult": 6, "absolut": 6, "intent": [6, 16], "mess": 6, "gladli": 6, "stuff": 6, "central": 6, "stai": 6, "close": 6, "packag": [6, 10, 14, 15], "y": [6, 7, 8, 9, 11, 16], "union": [6, 7, 8, 15], "gener": 6, "methoderror": 6, "int64": [6, 16], "candid": 6, "main": [6, 11], "repl": 6, "fix": 6, "among": [6, 13], "0x7fbbe8e3cdc0": 6, "0x7fbbc81813a0": 6, "saniti": 6, "thing": [6, 11], "inde": 6, "take": [6, 12], "serious": 6, "snippet": 6, "fallback": [6, 15], "b": [6, 11, 13, 14], "notimplementederror": 6, "similarli": 6, "dispatcherror": 6, "behaviour": [6, 8], "undesir": [6, 14], "isn": 6, "accord": 6, "principl": 6, "tri": 6, "next": [6, 10], "wildest": 6, "dream": 6, "come": 6, "numpi": [6, 16], "arrai": 6, "shape": 6, "size": 6, "concess": 6, "np": [6, 16], "ndarraymeta": 6, "__instancecheck__": [6, 15], "dtype": 6, "els": [6, 11], "ndarrai": 6, "valid": [6, 12], "That": [6, 11, 12, 15], "shape_left": 6, "dtype_left": 6, "shape_right": 6, "dtype_right": 6, "2x2": 6, "ones": [6, 15], "numer": 6, "nowher": 6, "tool": [6, 9, 13], "simplifi": [6, 13], "complic": [6, 13], "promot": 6, "specialis": [6, 13], "nich": [6, 15], "alias": 6, "result": 7, "typeerror": 7, "know": 7, "perform": [7, 12], "tell": [7, 15], "done": 7, "ration": 7, "num": 7, "denom": 7, "0x7f88f8369310": 7, "oper": [7, 13], "truediv": 7, "rational_to_numb": 7, "q": 7, "As": [7, 11], "abov": [7, 9, 11], "conversion_funct": 7, "No": [7, 8], "varieti": [8, 9], "them": [8, 9], "abstractli": 8, "usag": [8, 10], "multipli": 8, "two": [8, 9, 11], "Then": [8, 11], "0x7f8c4015e9d0": 8, "0x7f8c4015ea60": 8, "produc": [8, 9], "extern": 8, "old": 8, "builtin": [8, 12], "unfortun": [9, 11, 15], "limit": 9, "properli": 9, "challeng": [9, 11], "reason": [9, 11], "In": [9, 11, 12, 14, 15, 16], "section": 9, "collect": 9, "variou": 9, "pattern": 9, "plai": 9, "nice": 9, "At": 9, "moment": 9, "known": 9, "compliant": 9, "idea": 9, "scan": 9, "__all__": 9, "final": [9, 12], "pass": [9, 13], "sum": [9, 16], "python": [9, 11, 12, 15], "prior": 9, "11": [9, 12], "typing_extens": 9, "By": 9, "alwai": [9, 11, 15], "correct": 9, "diverg": 9, "normal": 9, "addit": [9, 14, 16], "contain": 9, "welcom": 10, "click": 10, "anyth": [11, 15], "state": 11, "clearli": 11, "base": 11, "posit": 11, "certainli": 11, "thei": [11, 15, 16], "decis": 11, "annot": 11, "thrown": 11, "illustr": 11, "differ": 11, "separ": 11, "asterisk": 11, "good": 11, "question": 11, "i": 11, "don": [11, 12, 16], "strong": 11, "answer": 11, "present": 11, "entir": 11, "would": [11, 16], "scenario": 11, "might": [11, 15], "confus": 11, "equival": 11, "wouldn": 11, "strang": 11, "switch": 11, "between": 11, "line": 11, "up": 11, "perhap": 11, "poor": 11, "go": 11, "wrong": 11, "sai": [11, 15], "becom": 11, "irrelev": 11, "And": 11, "written": 11, "matter": 11, "henc": 11, "sens": 11, "situat": 11, "choos": 11, "current": 11, "whole": 11, "system": [11, 15], "argu": 11, "somehow": 11, "incongru": 11, "therefor": [11, 15], "were": 11, "precis": [11, 12, 16], "spell": 11, "__getindex__": 12, "These": 12, "regard": 12, "It": 12, "0x7feb403d4d90": 12, "directli": 12, "automat": 12, "0x7feb6060e370": 12, "0x7feb801409d0": 12, "0x7feb5034be50": 12, "t1": [12, 15], "subtyp": [12, 15], "t2": [12, 15], "whenev": [12, 15], "certain": 12, "initialis": 12, "best": 12, "ntupl": 12, "satisfi": 12, "len": 12, "valueerror": 12, "incorrect": 12, "inter": 12, "simplic": 12, "refin": 12, "n_left": 12, "t_left": 12, "n_right": 12, "t_right": 12, "appropri": 12, "10": 12, "12": 12, "0x7fa9d84ccd00": 12, "0x7fa9780a7d30": 12, "convienc": 12, "quickli": 12, "0x7fd6b861b520": 12, "0x7fd6b00d6850": 12, "i_expect_thi": 12, "i_expect_that": 12, "arg0": 12, "arg1": 12, "arg2": 12, "bring": [12, 15], "algorithm": 12, "fast": 12, "slow": [12, 15], "slowli": 12, "liter": [12, 15], "fill": 12, "similar": 12, "recommend": [12, 15], "7": [12, 15], "support": [12, 15], "level": 13, "precend": 13, "power": 13, "element": [13, 16], "zeroel": 13, "specialisedel": 13, "mul_no_preced": 13, "zero": 13, "mul": 13, "specialised_el": 13, "0x7feb80140d00": 13, "0x7feb605abfd0": 13, "0x7feb6066a700": 13, "0x7feb3000f670": 13, "py": 14, "record": 14, "global": 14, "want": [14, 15, 16], "someon": 14, "accident": 14, "overwrit": 14, "other_packag": 14, "some_fil": 14, "happen": 14, "keep": 14, "privat": 14, "under": 15, "hood": 15, "beartyp": 15, "xs": 15, "although": 15, "parametr": 15, "incur": 15, "penalti": 15, "optim": 15, "necessari": 15, "oppos": 15, "invari": 15, "achiev": 15, "process": 15, "effici": 15, "depend": [15, 16], "On": 15, "hand": 15, "unfaith": 15, "less": 15, "add_5_faith": 15, "add_5_unfaith": 15, "timeit": 15, "585": 15, "ns": 15, "per": 15, "loop": 15, "std": 15, "dev": 15, "000": 15, "each": 15, "24": 15, "\u00b5s": 15, "68": 15, "9": 15, "100": 15, "establish": 15, "e": 15, "g": 15, "custom": 15, "detect": 15, "conserv": 15, "mymeta": 15, "ye": 15, "lot": 15, "exist": 15, "mai": 15, "behav": 15, "erron": 15, "eagertensor": 15, "tensorflow": 15, "framework": 15, "op": 15, "eager": 15, "tf": 15, "tensor": 15, "0x7fc2a89a5310": 15, "point": 15, "occur": 15, "access": 15, "circular": 15, "proxi": 15, "deliv": 15, "proxyint": 15, "specialint": 15, "understand": 16, "solv": 16, "suppos": 16, "special": 16, "scalar": 16, "scalar_typ": 16, "sctype": 16, "look": 16, "fine": 16, "until": 16, "document": 16, "int8": 16, "int16": 16, "int32": 16, "uint8": 16, "uint16": 16, "uint32": 16, "uint64": 16, "float16": 16, "float32": 16, "float64": 16, "float128": 16, "complex64": 16, "complex128": 16, "complex256": 16, "byte": 16, "void": 16, "while": 16, "accur": 16, "its": 16, "mani": 16, "obscur": 16, "messag": 16, "better": 16, "explicitli": 16, "monkeypatch": 16, "hurrai": 16, "omit": 16, "won": 16, "deactiv": 16}, "objects": {"plum": [[1, 0, 0, "-", "alias"], [1, 0, 0, "-", "autoreload"], [1, 0, 0, "-", "dispatcher"], [1, 0, 0, "-", "function"], [1, 0, 0, "-", "parametric"], [1, 0, 0, "-", "promotion"], [1, 0, 0, "-", "resolver"], [1, 0, 0, "-", "signature"], [1, 0, 0, "-", "type"], [1, 0, 0, "-", "util"]], "plum.alias": [[1, 1, 1, "", "activate_union_aliases"], [1, 1, 1, "", "deactivate_union_aliases"], [1, 1, 1, "", "set_union_alias"]], "plum.autoreload": [[1, 1, 1, "", "activate_autoreload"], [1, 1, 1, "", "deactivate_autoreload"]], "plum.dispatcher": [[1, 2, 1, "", "Dispatcher"], [1, 1, 1, "", "clear_all_cache"], [1, 5, 1, "", "dispatch"]], "plum.dispatcher.Dispatcher": [[1, 3, 1, "", "abstract"], [1, 4, 1, "", "classes"], [1, 3, 1, "", "clear_cache"], [1, 4, 1, "", "functions"], [1, 3, 1, "", "multi"]], "plum.function": [[1, 2, 1, "", "Function"]], "plum.function.Function": [[1, 3, 1, "", "clear_cache"], [1, 3, 1, "", "dispatch"], [1, 3, 1, "", "dispatch_multi"], [1, 3, 1, "", "invoke"], [1, 6, 1, "", "methods"], [1, 6, 1, "", "owner"], [1, 3, 1, "", "register"], [1, 3, 1, "", "resolve_method"]], "plum.parametric": [[1, 2, 1, "", "CovariantMeta"], [1, 2, 1, "", "Kind"], [1, 2, 1, "", "Val"], [1, 1, 1, "", "kind"], [1, 1, 1, "", "parametric"], [1, 1, 1, "", "type_parameter"]], "plum.promotion": [[1, 1, 1, "", "add_conversion_method"], [1, 1, 1, "", "add_promotion_rule"], [1, 1, 1, "", "conversion_method"], [1, 1, 1, "", "convert"], [1, 1, 1, "", "promote"]], "plum.resolver": [[1, 7, 1, "", "AmbiguousLookupError"], [1, 7, 1, "", "NotFoundLookupError"]], "plum.signature": [[1, 2, 1, "", "Signature"], [1, 1, 1, "", "append_default_args"], [1, 1, 1, "", "extract_signature"]], "plum.signature.Signature": [[1, 3, 1, "", "expand_varargs"], [1, 4, 1, "", "has_varargs"], [1, 4, 1, "", "implementation"], [1, 4, 1, "", "is_faithful"], [1, 3, 1, "", "match"], [1, 4, 1, "", "precedence"], [1, 4, 1, "", "return_type"], [1, 4, 1, "", "types"], [1, 4, 1, "", "varargs"]], "plum.type": [[1, 2, 1, "", "ModuleType"], [1, 2, 1, "", "PromisedType"], [1, 1, 1, "", "is_faithful"], [1, 1, 1, "", "resolve_type_hint"], [1, 5, 1, "", "type_mapping"]], "plum.type.ModuleType": [[1, 3, 1, "", "retrieve"]], "plum.util": [[1, 2, 1, "", "Comparable"], [1, 2, 1, "", "Missing"], [1, 4, 1, "", "TypeHint"], [1, 1, 1, "", "get_class"], [1, 1, 1, "", "get_context"], [1, 1, 1, "", "is_in_class"], [1, 1, 1, "", "multihash"], [1, 1, 1, "", "repr_short"], [1, 1, 1, "", "wrap_lambda"]], "plum.util.Comparable": [[1, 3, 1, "", "is_comparable"]]}, "objtypes": {"0": "py:module", "1": "py:function", "2": "py:class", "3": "py:method", "4": "py:attribute", "5": "py:data", "6": "py:property", "7": "py:exception"}, "objnames": {"0": ["py", "module", "Python module"], "1": ["py", "function", "Python function"], "2": ["py", "class", "Python class"], "3": ["py", "method", "Python method"], "4": ["py", "attribute", "Python attribute"], "5": ["py", "data", "Python data"], "6": ["py", "property", "Python property"], "7": ["py", "exception", "Python exception"]}, "titleterms": {"advanc": 0, "usag": [0, 3], "applic": 1, "program": 1, "interfac": 1, "type": [1, 6, 7, 15], "signatur": 1, "function": [1, 8, 14], "dispatch": [1, 6, 8, 11], "parametr": [1, 6, 12], "class": [1, 4, 6, 12], "promot": [1, 7], "convers": [1, 7], "union": [1, 16], "alias": [1, 16], "ipython": [1, 2], "autoreload": [1, 2], "other": [1, 6], "util": 1, "support": [2, 9, 11], "basic": 3, "decor": 4, "forward": 4, "refer": 4, "command": 5, "line": 5, "configur": 5, "option": 5, "plum_simple_doc": 5, "comparison": 6, "multipl": [6, 8], "implement": 6, "power": 6, "beartyp": 6, "design": 6, "goal": 6, "mimic": 6, "julia": 6, "s": 6, "system": 6, "care": 6, "synergi": 6, "With": [6, 7], "oop": 6, "featur": 6, "rich": 6, "return": 7, "convert": 7, "wai": 8, "abstract": 8, "definit": [8, 15], "extend": 8, "from": 8, "anoth": 8, "packag": 8, "directli": 8, "invok": 8, "method": [8, 13], "defin": 8, "onc": 8, "integr": 9, "linter": 9, "mypi": 9, "overload": 9, "plum": 10, "keyword": 11, "argument": 11, "default": 11, "why": 11, "doesn": 11, "t": 11, "fulli": 11, "construct": 12, "customis": 12, "kind": 12, "val": 12, "exampl": 12, "ndarrai": 12, "preced": 13, "scope": 14, "perform": 15, "faith": 15, "moduletyp": 15, "promisedtyp": 15}, "envversion": {"sphinx.domains.c": 2, "sphinx.domains.changeset": 1, "sphinx.domains.citation": 1, "sphinx.domains.cpp": 6, "sphinx.domains.index": 1, "sphinx.domains.javascript": 2, "sphinx.domains.math": 2, "sphinx.domains.python": 3, "sphinx.domains.rst": 2, "sphinx.domains.std": 2, "sphinx.ext.intersphinx": 1, "sphinx.ext.viewcode": 1, "sphinxcontrib.bibtex": 9, "sphinx": 56}})